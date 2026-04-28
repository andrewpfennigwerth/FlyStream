# FlyStream
# AI Fly Fishing Advisor

## Tech Stack
- Backend: FastAPI, LangChain, Claude
- Frontend: React
- Deployment: Render + Vercel

## Setup
1. Install backend dependencies: `pip install -r backend/requirements.txt`
2. Add API keys to `backend/.env`
3. Optional: set `CORS_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app`
4. Run backend: `uvicorn backend.main:app --reload`
5. Install frontend dependencies: `cd frontend && npm install`
6. Run frontend: `npm run dev`

The frontend posts to `http://localhost:8000` by default. Set `VITE_API_BASE_URL` for a deployed API.