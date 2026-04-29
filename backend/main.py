import os
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .agent import recommend_flies
except ImportError:  # Allows `uvicorn main:app` from the backend directory.
    from agent import recommend_flies

load_dotenv()

app = FastAPI(title="FlyStream Backend")

DEFAULT_CORS_ORIGINS = ["http://localhost:5173"]
RATE_LIMIT_WINDOW_SECONDS = 300
RATE_LIMIT_MAX_REQUESTS = 10
_request_log = defaultdict(deque)


def get_cors_origins():
    configured_origins = os.getenv("CORS_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    return origins or DEFAULT_CORS_ORIGINS


class RecommendationRequest(BaseModel):
    location: str = Field(..., min_length=1, max_length=120, examples=["Farmington, CT"])


def check_rate_limit(client_id: str):
    now = time.time()
    request_times = _request_log[client_id]
    while request_times and now - request_times[0] > RATE_LIMIT_WINDOW_SECONDS:
        request_times.popleft()
    if len(request_times) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a few minutes and try again.",
        )
    request_times.append(now)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

@app.get("/")
def read_root():
    return {"message": "FlyStream API is running"}

@app.post("/recommend")
def get_recommendations(payload: RecommendationRequest, request: Request):
    client_id = request.client.host if request.client else "unknown"
    check_rate_limit(client_id)

    location = payload.location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Location is required.")

    try:
        result = recommend_flies(location)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Recommendation service failed. Please try again later.",
        ) from exc
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result