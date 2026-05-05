"""Reworked module for runtime_state.manager.py"""
from __future__ import annotations
from pathlib import Path
from state_manager.storage import DiskStateStore
from typing import Any, Dict, Optional

class LedgerManager:
    """Thin facade around JSON state persistence."""

    def __init__(self, storage: JsonStateStorage | None=None):
        self.storage = storage or DiskStateStore()

    def load(self, target_path: Path) -> Optional[Dict[str, Any]]:
        return self.storage.read(target_path)

    def save(self, target_path: Path, request_body: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.write(target_path, request_body)
