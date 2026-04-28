import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .agent import recommend_flies
except ImportError:  # Allows `uvicorn main:app` from the backend directory.
    from agent import recommend_flies

load_dotenv()

app = FastAPI(title="FlyStream Backend")

DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]


def get_cors_origins():
    configured_origins = os.getenv("CORS_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    return origins or DEFAULT_CORS_ORIGINS


class RecommendationRequest(BaseModel):
    location: str = Field(..., min_length=1, examples=["Farmington, CT"])


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FlyStream API is running"}

@app.post("/recommend")
def get_recommendations(request: RecommendationRequest):
    location = request.location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Location is required.")

    result = recommend_flies(location)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result