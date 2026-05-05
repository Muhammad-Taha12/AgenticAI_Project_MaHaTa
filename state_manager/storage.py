"""Reworked module for runtime_state.storage.py"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json

class DiskStateStore:
    """Small JSON file storage used by the Phase 4 job system."""

    def read(self, target_path: Path) -> Optional[Dict[str, Any]]:
        if not target_path.exists():
            return None
        with target_path.open(encoding='utf-8') as fh:
            return json.load(fh)

    def write(self, target_path: Path, request_body: Dict[str, Any]) -> Dict[str, Any]:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open('w', encoding='utf-8') as fh:
            json.dump(request_body, fh, indent=2, ensure_ascii=False)
        return request_body
