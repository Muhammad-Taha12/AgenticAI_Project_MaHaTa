"""intent_classifier.py — classify a natural-language edit instruction.

Avoids with_structured_output (Ollama rejects complex nested schemas).
Instead, prompts for raw JSON and parses + validates manually.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.story_agent.llm_runtime import resolve_llm

logger = logging.getLogger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────────

EditKind = Literal["field_patch", "scene_rewrite", "character_patch", "full_rerun"]


class PatchOp(BaseModel):
    target_file: Literal["story", "characters", "script"]
    json_path: str
    new_value: Any
    description: str


class EditIntent(BaseModel):
    kind: EditKind
    primary_phase: int = Field(ge=1, le=3)
    rerun_from_phase: int = Field(ge=1, le=3)
    patches: List[PatchOp] = Field(default_factory=list)
    scene_keys: List[str] = Field(default_factory=list)
    character_ids: List[str] = Field(default_factory=list)
    rationale: str


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an edit-intent classifier for an AI video pipeline.

The pipeline has three phases:
  Phase 1 – story / character / script JSON files
  Phase 2 – audio rendering (voice, music)
  Phase 3 – video rendering (images, final MP4)

A user gives a natural-language edit instruction. Respond with a single JSON
object — no markdown, no explanation, just the raw JSON object.

The JSON must have exactly these keys:

{
  "kind": one of "field_patch" | "scene_rewrite" | "character_patch" | "full_rerun",
  "primary_phase": 1 | 2 | 3,
  "rerun_from_phase": 1 | 2 | 3,
  "patches": [ ... ],
  "scene_keys": [ ... ],
  "character_ids": [ ... ],
  "rationale": "one sentence"
}

Rules for rerun_from_phase:
- Editing story structure or any script/dialogue → rerun from 1
- Editing voice or audio only → rerun from 2
- Editing visual style only → rerun from 3

Rules for patches (only for field_patch / character_patch):
Each patch object must have:
  "target_file": "story" | "characters" | "script"
  "json_path": dot-separated path, e.g. "scenes.2.tone" or "characters.0.name"
  "new_value": the replacement value
  "description": brief description

For scene_rewrite and full_rerun, patches must be an empty array [].

Examples:
- "make scene 2 darker" → kind=field_patch, rerun_from_phase=3,
  patches=[{target_file:story, json_path:scenes.1.tone, new_value:"dark", description:"darken scene 2 tone"}]
- "rename char_001 to Elena" → kind=character_patch, rerun_from_phase=2,
  patches=[{target_file:characters, json_path:characters.0.name, new_value:"Elena", description:"rename protagonist"}]
- "rewrite the whole story" → kind=full_rerun, rerun_from_phase=1, patches=[]
"""


# ── Extraction helpers ────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Pull the first {...} block out of an LLM response."""
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find outermost braces
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("Unbalanced braces in response")


def _coerce_intent(raw: Dict[str, Any]) -> EditIntent:
    """Parse and validate the raw dict, filling safe defaults for missing fields."""
    kind = raw.get("kind", "full_rerun")
    if kind not in ("field_patch", "scene_rewrite", "character_patch", "full_rerun"):
        kind = "full_rerun"

    primary_phase = int(raw.get("primary_phase", 1))
    rerun_from = int(raw.get("rerun_from_phase", 1))
    primary_phase = max(1, min(3, primary_phase))
    rerun_from = max(1, min(3, rerun_from))

    patches: List[PatchOp] = []
    for p in raw.get("patches") or []:
        try:
            patches.append(PatchOp(
                target_file=p["target_file"],
                json_path=p["json_path"],
                new_value=p["new_value"],
                description=p.get("description", ""),
            ))
        except Exception as exc:
            logger.warning("Skipping malformed patch op: %s — %s", p, exc)

    return EditIntent(
        kind=kind,
        primary_phase=primary_phase,
        rerun_from_phase=rerun_from,
        patches=patches,
        scene_keys=raw.get("scene_keys") or [],
        character_ids=raw.get("character_ids") or [],
        rationale=raw.get("rationale") or "Edit applied.",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def classify_edit(
    instruction: str,
    story: Optional[Dict[str, Any]],
    characters: Optional[Dict[str, Any]],
    script: Optional[Dict[str, Any]],
) -> EditIntent:
    """Classify a natural-language edit instruction into a structured EditIntent."""
    llm = resolve_llm(temperature=0.0)

    context_parts: List[str] = []
    if story:
        context_parts.append(f"STORY:\n{json.dumps(_slim_story(story), indent=2)}")
    if characters:
        context_parts.append(f"CHARACTERS:\n{json.dumps(_slim_characters(characters), indent=2)}")
    if script:
        context_parts.append(f"SCRIPT (excerpt):\n{json.dumps(_slim_script(script), indent=2)}")
    context = "\n\n".join(context_parts) or "No prior outputs available."

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"Current pipeline state:\n\n{context}\n\n"
            f"Edit instruction: {instruction}\n\n"
            "Reply with the JSON object only."
        )),
    ]

    response = llm.invoke(messages)
    raw_text: str = response.content if hasattr(response, "content") else str(response)
    logger.debug("Raw classifier response: %s", raw_text[:500])

    try:
        json_str = _extract_json(raw_text)
        raw_dict = json.loads(json_str)
        intent = _coerce_intent(raw_dict)
    except Exception as exc:
        logger.warning("Failed to parse classifier JSON (%s) — defaulting to full_rerun. Raw: %s", exc, raw_text[:300])
        intent = EditIntent(
            kind="full_rerun",
            primary_phase=1,
            rerun_from_phase=1,
            patches=[],
            scene_keys=[],
            character_ids=[],
            rationale=f"Could not parse edit intent — re-running from phase 1. ({exc})",
        )

    logger.info("Edit classified: kind=%s rerun_from_phase=%d rationale=%r",
                intent.kind, intent.rerun_from_phase, intent.rationale)
    return intent


# ── Context slimmers ──────────────────────────────────────────────────────────

def _slim_story(story: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "headline": story.get("headline"),
        "genre": story.get("genre"),
        "scenes": [
            {
                "index": i,
                "scene_key": s.get("scene_key"),
                "tone": s.get("tone"),
                "setting": s.get("setting"),
                "summary": s.get("summary"),
            }
            for i, s in enumerate(story.get("scenes") or [])
        ],
    }


def _slim_characters(chars: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "characters": [
            {
                "index": i,
                "character_id": c.get("character_id"),
                "name": c.get("name"),
                "role": c.get("role"),
                "voice_gender": c.get("voice_config", {}).get("gender"),
                "voice_tone": c.get("voice_config", {}).get("tone"),
            }
            for i, c in enumerate(chars.get("characters") or [])
        ],
    }


def _slim_script(script: Dict[str, Any]) -> Dict[str, Any]:
    scenes = []
    for scene in (script.get("scenes") or [])[:3]:
        lines = [
            {"character_id": ln.get("character_id"), "copy_text": ln.get("copy_text", "")[:80]}
            for ln in (scene.get("dialogue") or [])[:3]
        ]
        scenes.append({"scene_key": scene.get("scene_key"), "lines": lines})
    return {"scenes": scenes}