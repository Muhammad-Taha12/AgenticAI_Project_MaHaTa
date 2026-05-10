"""agent.py — Edit Agent entry point.

Public API
----------
apply_edit(job_dir, phase1_dir, instruction, story, characters, script)
    → EditResult

undo_edit(job_dir, phase1_dir)
    → UndoResult

get_history(job_dir)
    → list[dict]

can_undo(job_dir)
    → bool
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.edit_agent.executor import apply_intent
from agents.edit_agent.intent_classifier import EditIntent, classify_edit
from agents.edit_agent import planner

logger = logging.getLogger(__name__)


class EditResult:
    """Result of a single apply_edit call."""

    def __init__(
        self,
        success: bool,
        rerun_from_phase: int,
        patches_applied: int,
        files_modified: List[str],
        rationale: str,
        snapshot_version: str,
        error: Optional[str] = None,
    ):
        self.success = success
        self.rerun_from_phase = rerun_from_phase
        self.patches_applied = patches_applied
        self.files_modified = files_modified
        self.rationale = rationale
        self.snapshot_version = snapshot_version
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "rerun_from_phase": self.rerun_from_phase,
            "patches_applied": self.patches_applied,
            "files_modified": self.files_modified,
            "rationale": self.rationale,
            "snapshot_version": self.snapshot_version,
            "error": self.error,
        }


class UndoResult:
    def __init__(self, success: bool, restored_version: Optional[str], error: Optional[str] = None):
        self.success = success
        self.restored_version = restored_version
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "restored_version": self.restored_version,
            "error": self.error,
        }


def apply_edit(
    job_dir: Path,
    phase1_dir: Path,
    instruction: str,
    story: Optional[Dict[str, Any]] = None,
    characters: Optional[Dict[str, Any]] = None,
    script: Optional[Dict[str, Any]] = None,
) -> EditResult:
    """Classify the instruction, snapshot current state, apply patches.

    The caller is responsible for re-running the pipeline from
    result.rerun_from_phase after this returns.
    """
    logger.info("[EditAgent] Instruction: %r", instruction)

    try:
        intent: EditIntent = classify_edit(instruction, story, characters, script)
    except Exception as exc:
        logger.exception("[EditAgent] Classification failed")
        return EditResult(
            success=False,
            rerun_from_phase=1,
            patches_applied=0,
            files_modified=[],
            rationale="",
            snapshot_version="",
            error=f"Classification failed: {exc}",
        )

    # Snapshot before any mutation so we can undo
    version = planner.take_snapshot(
        job_dir=job_dir,
        phase1_dir=phase1_dir,
        instruction=instruction,
        intent_summary=f"{intent.kind} → phase {intent.rerun_from_phase}: {intent.rationale}",
    )
    logger.info("[EditAgent] Snapshot taken: version %s", version)

    try:
        result = apply_intent(intent, phase1_dir)
    except Exception as exc:
        logger.exception("[EditAgent] Execution failed")
        return EditResult(
            success=False,
            rerun_from_phase=intent.rerun_from_phase,
            patches_applied=0,
            files_modified=[],
            rationale=intent.rationale,
            snapshot_version=version,
            error=f"Patch execution failed: {exc}",
        )

    logger.info(
        "[EditAgent] Applied %d patch(es) to %s; re-run from phase %d",
        result["patches_applied"], result["files_modified"], result["rerun_from_phase"],
    )
    return EditResult(
        success=True,
        rerun_from_phase=result["rerun_from_phase"],
        patches_applied=result["patches_applied"],
        files_modified=result["files_modified"],
        rationale=result["rationale"],
        snapshot_version=version,
    )


def undo_edit(job_dir: Path, phase1_dir: Path) -> UndoResult:
    """Restore the most recent snapshot, discarding the current phase 1 artifacts."""
    if not planner.can_undo(job_dir):
        return UndoResult(success=False, restored_version=None, error="Nothing to undo.")

    meta = planner.undo(job_dir, phase1_dir)
    if meta is None:
        return UndoResult(success=False, restored_version=None, error="Undo failed unexpectedly.")

    logger.info("[EditAgent] Undone to version %s (%r)", meta.get("version"), meta.get("instruction"))
    return UndoResult(success=True, restored_version=meta.get("version"))


def get_history(job_dir: Path) -> List[Dict[str, Any]]:
    """Return the full edit history for this job, oldest first."""
    return planner.list_history(job_dir)


def can_undo(job_dir: Path) -> bool:
    return planner.can_undo(job_dir)
