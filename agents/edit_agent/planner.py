"""planner.py — snapshot management and undo stack.

Every edit creates a versioned snapshot of the phase 1 artifact directory
before mutating it.  Undo restores the most recent snapshot.

Snapshot layout (inside the job directory):
  <job_dir>/
    phase1/          ← live artifacts
    edit_history/
      001/
        story.json
        characters.json
        script.json
        meta.json    ← {instruction, timestamp, edit_number, intent_summary}
      002/
        ...
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_HISTORY_DIR = "edit_history"
_ARTIFACTS = ("story.json", "characters.json", "script.json")


def _history_root(job_dir: Path) -> Path:
    p = job_dir / _HISTORY_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _next_version(history_root: Path) -> str:
    existing = sorted(d.name for d in history_root.iterdir() if d.is_dir() and d.name.isdigit())
    return f"{(int(existing[-1]) + 1) if existing else 1:03d}"


def _read_meta(version_dir: Path) -> Dict[str, Any]:
    meta_path = version_dir / "meta.json"
    if not meta_path.exists():
        return {}
    with meta_path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ── Public API ────────────────────────────────────────────────────────────────

def take_snapshot(
    job_dir: Path,
    phase1_dir: Path,
    instruction: str,
    intent_summary: str,
) -> str:
    """Copy current phase 1 artifacts into a new versioned snapshot.

    Returns the version string (e.g. '003').
    """
    history_root = _history_root(job_dir)
    version = _next_version(history_root)
    version_dir = history_root / version
    version_dir.mkdir(parents=True, exist_ok=True)

    for artifact in _ARTIFACTS:
        src = phase1_dir / artifact
        if src.exists():
            shutil.copy2(src, version_dir / artifact)

    meta = {
        "version": version,
        "instruction": instruction,
        "intent_summary": intent_summary,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    with (version_dir / "meta.json").open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    return version


def undo(job_dir: Path, phase1_dir: Path) -> Optional[Dict[str, Any]]:
    """Restore the most recent snapshot into phase1_dir.

    Returns the meta dict of the snapshot that was restored, or None if
    there's nothing to undo.
    """
    history_root = _history_root(job_dir)
    versions = sorted(d for d in history_root.iterdir() if d.is_dir() and d.name.isdigit())
    if not versions:
        return None

    latest = versions[-1]
    meta = _read_meta(latest)

    for artifact in _ARTIFACTS:
        src = latest / artifact
        if src.exists():
            shutil.copy2(src, phase1_dir / artifact)

    # Remove the snapshot we just restored (it's now "current")
    shutil.rmtree(latest)

    return meta


def list_history(job_dir: Path) -> List[Dict[str, Any]]:
    """Return all edit snapshots ordered oldest-first."""
    history_root = _history_root(job_dir)
    if not history_root.exists():
        return []
    versions = sorted(d for d in history_root.iterdir() if d.is_dir() and d.name.isdigit())
    return [_read_meta(v) for v in versions]


def can_undo(job_dir: Path) -> bool:
    """Return True if there is at least one snapshot available to undo."""
    history_root = _history_root(job_dir)
    if not history_root.exists():
        return False
    return any(d.is_dir() and d.name.isdigit() for d in history_root.iterdir())
