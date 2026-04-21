from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FlyStream Backend")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FlyStream API is running"}

@app.post("/recommend")
def get_recommendations(location: str):
    # Placeholder — we'll build the agent here
    return {
        "location": location,
        "recommendations": [{"fly_name": "Test Fly", "type": "dry"}],
        "message": "Agent not implemented yet"
    }