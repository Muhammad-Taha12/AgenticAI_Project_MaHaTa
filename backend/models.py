from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, Literal, Optional
JobStatus = Literal['pending', 'running', 'completed', 'failed']
PhaseStatus = Literal['pending', 'running', 'completed', 'failed', 'skipped']

class RunPhaseRequest(BaseModel):
    prompt: Optional[str] = Field(default=None, min_length=3)

class PipelineRequest(BaseModel):
    prompt: str = Field(min_length=3)

class JobState(BaseModel):
    job_id: str
    prompt: str
    status: JobStatus = 'pending'
    active_stage: Optional[int] = None
    phases: Dict[str, PhaseStatus]
    progress: int = 0
    status_note: str = ''
    issues: list[str] = Field(default_factory=list)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
