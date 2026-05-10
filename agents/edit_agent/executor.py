"""executor.py — apply an EditIntent to the on-disk phase artifacts.

For field_patch / character_patch edits this directly mutates the JSON files
so the orchestrator can re-run from the correct phase without re-invoking the LLM.

For scene_rewrite and full_rerun the executor just signals that a full re-run
of the target phase is required; the orchestrator handles the rest.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from agents.edit_agent.intent_classifier import EditIntent, PatchOp

logger = logging.getLogger(__name__)


# ── JSON-path helpers ─────────────────────────────────────────────────────────

def _resolve_path(data: Any, parts: List[str]) -> Any:
    """Walk a dot-split path, treating numeric segments as list indices."""
    node = data
    for part in parts:
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def _set_path(data: Any, parts: List[str], value: Any) -> None:
    """Set value at the given dot-split path in-place."""
    node = data
    for part in parts[:-1]:
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    final = parts[-1]
    if isinstance(node, list):
        node[int(final)] = value
    else:
        node[final] = value


# ── File helpers ──────────────────────────────────────────────────────────────

def _load(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _dump(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ── Main executor ─────────────────────────────────────────────────────────────

_FILE_MAP = {
    "story": "story.json",
    "characters": "characters.json",
    "script": "script.json",
}


def apply_intent(intent: EditIntent, phase1_dir: Path) -> Dict[str, Any]:
    """Apply the EditIntent to the phase 1 artifact files.

    Returns a summary dict:
      {
        "patches_applied": int,
        "files_modified": list[str],
        "rerun_from_phase": int,
        "rationale": str,
      }
    """
    if intent.kind in ("full_rerun", "scene_rewrite"):
        # No file mutation — just signal re-run from the target phase.
        logger.info("Edit kind '%s': no patch applied, signalling re-run from phase %d",
                    intent.kind, intent.rerun_from_phase)
        return {
            "patches_applied": 0,
            "files_modified": [],
            "rerun_from_phase": intent.rerun_from_phase,
            "rationale": intent.rationale,
        }

    # field_patch or character_patch — mutate JSON files directly
    files_modified: List[str] = []
    patches_applied = 0

    for op in intent.patches:
        filename = _FILE_MAP.get(op.target_file)
        if not filename:
            logger.warning("Unknown target_file '%s' in patch op, skipping.", op.target_file)
            continue

        target_path = phase1_dir / filename
        if not target_path.exists():
            logger.warning("Patch target %s not found on disk, skipping.", target_path)
            continue

        try:
            data = _load(target_path)
            parts = op.json_path.split(".")
            old_value = _resolve_path(data, parts)
            _set_path(data, parts, op.new_value)
            _dump(target_path, data)
            logger.info(
                "Patched %s @ %s: %r → %r",
                filename, op.json_path, old_value, op.new_value,
            )
            patches_applied += 1
            if filename not in files_modified:
                files_modified.append(filename)
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Could not apply patch to %s @ %s: %s", filename, op.json_path, exc)

    return {
        "patches_applied": patches_applied,
        "files_modified": files_modified,
        "rerun_from_phase": intent.rerun_from_phase,
        "rationale": intent.rationale,
    }
