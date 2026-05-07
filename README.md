# Agentic Project — Local Model Edition

An agentic media pipeline with a FastAPI backend, a Vite/React frontend, and a modular set of agent, tool, contract, and runtime packages.

All LLM inference runs **locally via [Ollama](https://ollama.com)** — no cloud API keys required.  
Images are generated via Pollinations AI (free, no key needed).  
Audio is synthesised with edge-tts (fully offline).

## What this project does

- Starts a new pipeline run from a prompt
- Tracks the current job state and phase progress
- Supports rerunning a specific phase for an existing job
- Streams job updates over Server-Sent Events
- Serves generated media artifacts through the backend
- Provides a browser UI for launching and monitoring runs

## Project layout

- `backend/` — FastAPI application, routes, streaming, runtime orchestration
- `agents/` — agent logic and phase pipelines
- `mcp/` — shared tool adapters and helpers
- `shared/` — schemas and constants
- `state_manager/` — persistence and snapshot helpers

## Requirements

- Python 3.11+
- Node.js 22+
- npm
- FFmpeg installed on the system
- [Ollama](https://ollama.com) installed and running

## Ollama setup (one-time)

1. Install Ollama: https://ollama.com/download

2. Pull a model (choose one):

```bash
ollama pull llama3.2        # recommended default (~2 GB)
ollama pull mistral         # good alternative
ollama pull qwen2.5         # strong multilingual option
```

3. Start the Ollama server (it runs automatically after install on most platforms):

```bash
ollama serve
```

## Environment setup

Copy `.env.example` to `.env` and adjust if needed:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `LOCAL_MODEL` | `llama3.2` | Ollama model name to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `PHASE1_OUTPUT_DIR` | `outputs` | Where Phase 1 artifacts are written |
| `PHASE2_OUTPUT_DIR` | `outputs/phase2output` | Where Phase 2 audio is written |

## Run with Docker

```bash
docker compose up --build
```

Then open:

- Frontend: `http://localhost:5173`
- Backend health check: `http://localhost:8000/health`

> **Note:** When using Docker you need to point `OLLAMA_BASE_URL` at your host machine.  
> On Linux/Mac: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

## Run the backend locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## Run the frontend locally

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173`.

## Run Phase 1 (story generation) standalone

```bash
python -m agents.story_agent.agent "A lonely robot discovers music in an abandoned city"
```

## Main API endpoints

- `GET /health` — basic service check
- `POST /run-pipeline` — start a full pipeline from a prompt
- `POST /run-phase/{stage_index}` — rerun the latest job from a chosen stage
- `GET /status/{task_id}` — fetch the current job snapshot
- `GET /result/{task_id}` — fetch the final assembled result
- `GET /events/{task_id}` — stream job updates as SSE

## Model recommendations

| Use case | Recommended model |
|---|---|
| Fast iteration / low RAM | `llama3.2` (3B) |
| Higher quality stories | `llama3.1:8b` or `mistral` |
| Best quality (needs 16 GB RAM) | `llama3.1:70b` via `ollama pull llama3.1:70b` |

## Notes

- Structured output (JSON mode) is handled automatically by `langchain-ollama`.
- Tool calling requires a model that supports it (llama3.2, mistral, qwen2.5 all do).
- The pipeline expects Ollama to be running before a run starts.
