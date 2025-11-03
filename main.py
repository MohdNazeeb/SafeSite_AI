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
from fastapi.middleware.cors import CORSMiddleware

origins = [
    # "https://safesite-ai-neon.vercel.app",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",  # ✅ Added this line
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # You can also set ["*"] for testing
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
async def upload_video(file: UploadFile = File(...), current_user = Depends(get_current_user)):
    # Basic validation
    if file.content_type.split("/")[0] != "video":
        raise HTTPException(status_code=400, detail="Uploaded file must be a video")

    # Create unique key
    from datetime import datetime
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    # key = f"uploads/{current_user.username}/{filename}"
    key=f"raw-videos/{current_user.username}/{filename}"


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


from fastapi import APIRouter, HTTPException
import requests

router = APIRouter()

@router.get("/analytics")
async def get_analytics():
    """
    Analytics endpoint — fetches processed safety data from AWS Lambda URL
    and computes real-time detection insights.
    """
    try:
        # 1️⃣ Fetch processed data from your Lambda endpoint
        response = requests.get("https://09vprol3o9.execute-api.ap-south-1.amazonaws.com/prod/outliers")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch processed data from AWS")

        data = response.json()


        detections = data.get("detections", [])

        # 2️⃣ Compute analytics dynamically
        total_detections = len(detections)
        if total_detections == 0:
            return {"message": "No detections available"}

        # Accuracy & confidence metrics
        avg_confidence = sum(d["confidence"] for d in detections) / total_detections
        safety_alerts = sum(1 for d in detections if d.get("alert", False))

        # Detection accuracy = 1 - (alerts / total)
        detection_accuracy = round(1 - (safety_alerts / total_detections), 2)

        # Count detections by label/category
        category_counts = {}
        for d in detections:
            label = d["label"]
            category_counts[label] = category_counts.get(label, 0) + 1

        detections_by_category = [{"name": k, "count": v} for k, v in category_counts.items()]

        # Simulated accuracy trend (optional)
        accuracy_trend = [
            {"time": "9AM", "acc": detection_accuracy - 0.03},
            {"time": "10AM", "acc": detection_accuracy - 0.02},
            {"time": "11AM", "acc": detection_accuracy - 0.01},
            {"time": "12PM", "acc": detection_accuracy},
        ]

        # 3️⃣ Construct the final analytics payload
        analytics_data = {
            "detection_accuracy": detection_accuracy,
            "total_detections": total_detections,
            "safety_alerts": safety_alerts,
            "avg_confidence": round(avg_confidence, 2),
            "detections_by_category": detections_by_category,
            "accuracy_trend": accuracy_trend,
        }

        return analytics_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analytics: {str(e)}")


app.include_router(router=router)
