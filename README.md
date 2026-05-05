# Agentic Project

An agentic media pipeline with a FastAPI backend, a Vite/React frontend, and a modular set of agent, tool, contract, and runtime packages.

The project is split into separate layers so the backend orchestration, agent logic, shared schemas, and UI can be developed independently.

## What this project does

- Starts a new pipeline run from a prompt
- Tracks the current job state and phase progress
- Supports rerunning a specific phase for an existing job
- Streams job updates over Server-Sent Events
- Serves generated media artifacts through the backend
- Provides a browser UI for launching and monitoring runs

## Project layout

- `backend/` — FastAPI application, routes, streaming, runtime orchestration
- `frontend/` — React UI and build files
- `narrative/` — agent logic and phase pipelines
- `toolkit/` — shared tool adapters and helpers
- `contracts/` — shared schemas and constants
- `runtime_state/` — persistence and snapshot helpers
- `data/` — job state and generated outputs

## Requirements

- Python 3.11+
- Node.js 22+
- npm
- FFmpeg installed on the system, or available through the backend Docker image

## Environment setup

Create a `.env` file in the project root based on `.env.example`.

Important variables:

- `GOOGLE_API_KEY` — required for the Gemini-backed stages
- `PHASE1_MODEL` — model used by the first-stage agent flow

## Run with Docker

This is the easiest way to start the whole stack.

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000/health`

## Run the backend locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`.

## Run the frontend locally

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173`.

## Main API endpoints

- `GET /health` — basic service check
- `POST /run-pipeline` — start a full pipeline from a prompt
- `POST /run-phase/{stage_index}` — rerun the latest job from a chosen stage
- `POST /run-phase/{task_id}/{stage_index}` — rerun a specific job from a chosen stage
- `GET /status/{task_id}` — fetch the current job snapshot
- `GET /result/{task_id}` — fetch the final assembled result
- `GET /events/{task_id}` — stream job updates as SSE

## Generated files

Runtime jobs and outputs are stored under `data/`. These files are created automatically during execution and are not meant to be edited by hand.

## Notes

- Keep the backend and frontend running in separate terminals when developing locally.
- If you change backend ports, update the frontend API base URL accordingly.
- The pipeline expects its environment variables to be present before a run starts.
