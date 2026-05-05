from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.models import JobResponse, PipelineRequest, RunPhaseRequest
from backend.runtime.ledger import JOBS_ROOT, PROJECT_ROOT, RunLedger
from backend.runtime.orchestrator import FlowRunner, read_json_blob
from backend.stream.events import emit_job_updates
from backend.stream.presentation import assemble_result_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MEDIA_ROOT = PROJECT_ROOT / "data"
app = FastAPI(title="Agentic Video Pipeline API", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")

store = RunLedger()
runner = FlowRunner(store)


def _load_snapshot(task_id: str) -> dict[str, Any]:
    snapshot = store.get(task_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return snapshot


def _rewind_snapshot(snapshot: dict[str, Any], stage_index: int, brief: str | None) -> dict[str, Any]:
    if brief:
        snapshot["prompt"] = brief

    snapshot.update(
        {
            "status": "pending",
            "current_phase": None,
            "progress": {1: 0, 2: 35, 3: 70}[stage_index],
            "message": f"Phase {stage_index} queued again",
        }
    )
    snapshot["errors"] = []

    outputs = snapshot.setdefault("outputs", {})
    phase_markers = snapshot.setdefault("phases", {})
    for cursor in range(stage_index, 4):
        phase_markers[str(cursor)] = "pending"
        outputs.pop(f"phase{cursor}", None)

    return snapshot


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run-pipeline", response_model=JobResponse)
async def run_pipeline(request_body: PipelineRequest) -> JobResponse:
    job = store.create(request_body.prompt)
    asyncio.create_task(runner.run_pipeline(job["job_id"], starting_stage=1))
    return JobResponse(job_id=job["job_id"], status=job["status"])


@app.post("/run-phase/{stage_index}", response_model=JobResponse)
async def rerun_latest_phase(stage_index: int, request_body: RunPhaseRequest) -> JobResponse:
    if stage_index not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="stage_index must be 1, 2, or 3")
    if not JOBS_ROOT.exists():
        raise HTTPException(status_code=404, detail="No jobs exist yet")

    latest_snapshot_file = max(JOBS_ROOT.glob("*/state.json"), key=lambda p: p.stat().st_mtime, default=None)
    if latest_snapshot_file is None:
        raise HTTPException(status_code=404, detail="No jobs exist yet")

    snapshot = read_json_blob(str(latest_snapshot_file))
    if not snapshot:
        raise HTTPException(status_code=404, detail="Job not found")
    if snapshot["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot re-run while the latest job is running")

    snapshot = _rewind_snapshot(snapshot, stage_index, request_body.prompt)
    store.save(snapshot["job_id"], snapshot)
    asyncio.create_task(runner.run_pipeline(snapshot["job_id"], starting_stage=stage_index))
    return JobResponse(job_id=snapshot["job_id"], status=snapshot["status"])


@app.post("/run-phase/{task_id}/{stage_index}", response_model=JobResponse)
async def rerun_job_phase(task_id: str, stage_index: int, request_body: RunPhaseRequest) -> JobResponse:
    if stage_index not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="stage_index must be 1, 2, or 3")

    snapshot = _load_snapshot(task_id)
    if snapshot["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot re-run while job is running")

    snapshot = _rewind_snapshot(snapshot, stage_index, request_body.prompt)
    store.save(task_id, snapshot)
    asyncio.create_task(runner.run_pipeline(task_id, starting_stage=stage_index))
    return JobResponse(job_id=task_id, status=snapshot["status"])


@app.get("/status/{task_id}")
async def get_status(task_id: str) -> dict[str, Any]:
    return _load_snapshot(task_id)


@app.get("/result/{task_id}")
async def get_result(task_id: str) -> dict[str, Any]:
    return assemble_result_payload(_load_snapshot(task_id), MEDIA_ROOT)


@app.get("/events/{task_id}")
async def watch_events(task_id: str) -> StreamingResponse:
    _load_snapshot(task_id)
    return StreamingResponse(emit_job_updates(task_id, store), media_type="text/event-stream")
