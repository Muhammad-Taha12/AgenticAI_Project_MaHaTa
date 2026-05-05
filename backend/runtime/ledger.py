"""Reworked module for backend.runtime.job_store.py"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from state_manager.state_manager import LedgerManager
from typing import Any, Dict, Optional
import uuid
PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_ROOT = PROJECT_ROOT / 'data' / 'jobs'

def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'

class RunLedger:
    """Simple JSON-backed storage for dashboard jobs and replay state."""

    def __init__(self, root: Path=JOBS_ROOT):
        self.root = root
        self.state_manager = LedgerManager()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, brief: str) -> Dict[str, Any]:
        task_id = uuid.uuid4().hex
        now = utc_now()
        snapshot = {'job_id': task_id, 'prompt': brief, 'status': 'pending', 'current_phase': None, 'phases': {'1': 'pending', '2': 'pending', '3': 'pending'}, 'progress': 0, 'message': 'Job queued', 'errors': [], 'outputs': {}, 'created_at': now, 'updated_at': now}
        self.save(task_id, snapshot)
        return snapshot

    def job_dir(self, task_id: str) -> Path:
        return self.root / task_id

    def state_path(self, task_id: str) -> Path:
        return self.job_dir(task_id) / 'state.json'

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        target_path = self.state_path(task_id)
        return self.state_manager.load(target_path)

    def save(self, task_id: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        snapshot['updated_at'] = utc_now()
        target_path = self.state_path(task_id)
        return self.state_manager.save(target_path, snapshot)

    def update(self, task_id: str, **changes: Any) -> Dict[str, Any]:
        snapshot = self.get(task_id)
        if snapshot is None:
            raise KeyError(f'Unknown job_id: {task_id}')
        for key, value in changes.items():
            if key == 'outputs':
                snapshot.setdefault('outputs', {}).update(value)
            elif key == 'phases':
                snapshot.setdefault('phases', {}).update(value)
            elif key == 'errors':
                snapshot.setdefault('errors', []).extend(value)
            else:
                snapshot[key] = value
        return self.save(task_id, snapshot)
