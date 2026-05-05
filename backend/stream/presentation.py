"""Reworked module for backend.api.presentation.py"""
from __future__ import annotations
from backend.runtime.orchestrator import read_json_blob
from pathlib import Path
from typing import Any

def to_media_url(target_path: str | None, media_root: Path) -> str | None:
    if not target_path:
        return None
    slot = Path(target_path).resolve()
    try:
        relative = slot.relative_to(media_root.resolve())
    except ValueError:
        return None
    return f'/media/{relative.as_posix()}'

def assemble_result_payload(snapshot: dict[str, Any], media_root: Path) -> dict[str, Any]:
    outputs = snapshot.get('outputs', {})
    phase_one = outputs.get('phase1', {})
    phase_two = outputs.get('phase2', {})
    phase_three = outputs.get('phase3', {})
    artifacts = phase_one.get('artifacts', {})
    return {'job': snapshot, 'preview': {'story': read_json_blob(artifacts.get('story')), 'characters': read_json_blob(artifacts.get('characters')), 'script': read_json_blob(artifacts.get('script')), 'timing_manifest': read_json_blob(phase_two.get('timing_manifest')), 'phase3_summary': read_json_blob(phase_three.get('summary'))}, 'assets': {'audio': phase_two.get('full_audio'), 'audio_url': to_media_url(phase_two.get('full_audio'), media_root), 'video': phase_three.get('final_video'), 'video_url': to_media_url(phase_three.get('final_video'), media_root), 'download_url': to_media_url(phase_three.get('final_video'), media_root)}}
