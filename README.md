# FlyStream

FlyStream is an AI-assisted fly fishing advisor that recommends a focused fly box for a destination. Enter a location, and FlyStream maps it to a known fishing region, pulls local water context, searches a curated fly pattern database, and returns dry flies, nymphs, streamers, and junk flies that make sense for that trip.

The goal is to turn scattered fly fishing knowledge into a practical planning tool: part recommendation engine, part local knowledge base, and eventually a searchable fly fishing encyclopedia.

## What It Does

- Recommends a balanced fly box by category: dry, nymph, streamer, and junk.
- Maps user-entered destinations to curated fishing regions and nearby waters.
- Uses current report context where available to bias recommendations.
- Pulls from a structured fly pattern catalog instead of inventing fly names.
- Uses Claude as a verification/reranking step while preserving the curated catalog.
- Presents results in a clean React interface built for quick trip planning.

## How It Works

FlyStream has a React frontend and a FastAPI backend.

The frontend sends a destination to the backend:

```txt
POST /recommend
```

The backend workflow:

1. Normalizes the submitted location.
2. Maps the location to a curated region, such as the Northeast, Rocky Mountains, Colorado, or Great Lakes.
3. Selects representative local waters for that region.
4. Searches for recent fishing report context.
5. Extracts known fly mentions from those reports using aliases and canonical fly names.
6. Scores the curated fly catalog using lightweight keyword matching, region tags, hatch conditions, seasonality, and fly type.
7. Fills a quota-balanced fly box across dry flies, nymphs, streamers, and junk flies.
8. Optionally asks Claude to rerank the selected flies without adding or removing anything from the curated set.

The recommendation system is intentionally grounded in a local JSON catalog. That keeps results predictable, explainable, and easy to improve as more local knowledge is added.

## Tech Stack

- Frontend: React, Vite, CSS
- Backend: FastAPI, Python
- AI: Claude via LangChain Anthropic
- Search: lightweight in-memory ranking over curated JSON data
- Deployment: Vercel frontend, Render backend

## Project Structure

```txt
backend/
  agent.py              # Recommendation workflow
  main.py               # FastAPI routes and CORS config
  tools.py              # Fishing report search tool
  vector_store.py       # Lightweight catalog search/ranking
  data/
    fly_patterns.json   # Curated fly pattern database
    waters_by_region.json

frontend/
  src/
    main.jsx            # React app and API call
    ShaderBackground.jsx
    styles.css
    storage/            # UI images and logo
```

## Running Locally

### Backend

```bash
pip install -r backend/requirements.txt
```

Create `backend/.env`:

```txt
ANTHROPIC_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
CORS_ORIGINS=http://localhost:5173
```

Run the API:

```bash
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend uses `http://localhost:8000` by default. For a deployed backend, set:

```txt
VITE_API_BASE_URL=https://your-backend-url.onrender.com
```

## Deployment Notes

The app is designed to deploy as two services:

- Frontend on Vercel
- Backend on Render

Render environment variables:

```txt
PYTHON_VERSION=3.11.9
ANTHROPIC_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
CORS_ORIGINS=https://your-frontend-url.vercel.app
```

Render build command:

```bash
pip install -r requirements.txt
```

Render start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Vercel environment variable:

```txt
VITE_API_BASE_URL=https://your-backend-url.onrender.com
```

## Why The Search Is Lightweight

An earlier version used Chroma and sentence-transformer embeddings for vector search. That worked locally, but it was too memory-heavy for free-tier deployment. Since the curated fly catalog is currently small and structured, FlyStream now uses deterministic in-memory ranking over the JSON data.

That tradeoff makes the deployed app faster, cheaper, and easier to reason about while preserving the same recommendation workflow.

## Where It Is Headed

FlyStream is moving toward a richer fly fishing knowledge system, not just a one-shot recommender.

Planned improvements:

- Expand the curated fly pattern database with more regional patterns, aliases, sizes, hatch notes, and seasonal context.
- Add clickable fly cards with details like when to fish each pattern, how to rig it, common sizes, and why it was recommended.
- Add richer water profiles with conditions, seasonal timing, common hatches, access notes, and local tactics.
- Improve location coverage beyond the initial curated regions.
- Add better handling for unknown locations by combining curated fallbacks with report search.
- Add source links and confidence indicators so recommendations are easier to audit.
- Build toward a fly encyclopedia with local knowledge layered on top of structured pattern and water data.

## Current Status

FlyStream is a working deployed prototype. The core recommendation flow is live, the frontend is production-ready enough to demo, and the backend has been optimized for free-tier hosting. The next phase is improving depth: more data, richer explanations, and better local knowledge.