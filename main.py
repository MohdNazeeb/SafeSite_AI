# app/main.py
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
import models
from database import engine
from auth import router as auth_router
from deps import get_current_user
from s3_client import upload_fileobj_to_s3, AWS_BUCKET_NAME, AWS_REGION
from fastapi.middleware.cors import CORSMiddleware

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SafeSite AI Backend")

# allow local dev origins (add others if needed)
origins = [
    "http://localhost",
    "http://localhost:3000",   # React (CRA)
    "http://localhost:5173",   # Vite default
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # or ["*"] for hackathon quick test (not recommended for prod)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "Welcome to SafeSite AI!"}


@app.get("/protected")
def protected_route(current_user = Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}. This is protected."}

@app.post("/raw-videos")
# , current_user = Depends(get_current_user)
async def upload_video(file: UploadFile = File(...)):
    # Basic validation
    if file.content_type.split("/")[0] != "video":
        raise HTTPException(status_code=400, detail="Uploaded file must be a video")

    # Create unique key
    from datetime import datetime
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    # key = f"uploads/{current_user.username}/{filename}"
    key=f"raw-videos/{filename}"


    # Try uploading to S3 (if configured)
    try:
        upload_fileobj_to_s3(file.file, AWS_BUCKET_NAME, key)
    except RuntimeError:
        # Fallback behavior: return info (or you can stream to local storage)
        raise HTTPException(status_code=500, detail="AWS not configured. Set AWS_ACCESS_KEY and AWS_SECRET_KEY in .env")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"
    return {"message": "Upload successful", "file_name": filename, "file_url": file_url}
