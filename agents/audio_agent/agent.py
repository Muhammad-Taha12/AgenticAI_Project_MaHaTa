from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from shared.schemas.handoffs import Phase2AudioHandoff
from datetime import datetime
from pathlib import Path
from pydantic import ValidationError
from mcp.tools.audio_tools.audio_merger import concat_audio_files, mix_audio_layers
from mcp.tools.audio_tools.bgm_tool import compose_bed_track
from mcp.tools.audio_tools.tts_tool import speak_segment
from typing import Any, Dict, Iterable
import json
import os
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / 'data' / 'outputs' / 'phase2'

def load_handoff_bundle(handoff: str | Path | Dict[str, Any] | Phase2AudioHandoff) -> Phase2AudioHandoff:
    if isinstance(handoff, Phase2AudioHandoff):
        return handoff
    if isinstance(handoff, (str, Path)):
        with Path(handoff).open(encoding='utf-8') as fh:
            return Phase2AudioHandoff.model_validate(json.load(fh))
    return Phase2AudioHandoff.model_validate(handoff)

def execute_phase_two(handoff: str | Path | Dict[str, Any] | Phase2AudioHandoff, destination_dir: str | Path | None=None, include_bgm: bool=True) -> Dict[str, Any]:
    """Run Phase 2 audio generation from a Phase 1 audio handoff.

    The default implementation is fully offline and deterministic. It creates
    one WAV per dialogue segment, one optional BGM pad per scene, scene mixes,
    a combined audio track, and a timing manifest for Phase 3.
    """
    try:
        audio_handoff = load_handoff_bundle(handoff)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return {'success': False, 'errors': [f'Invalid Phase 2 handoff: {exc}']}
    configured_output_root = Path(os.environ.get('PHASE2_OUTPUT_DIR', DEFAULT_OUTPUT_ROOT))
    run_dir = Path(destination_dir) if destination_dir else configured_output_root / clockstamp()
    segments_dir = run_dir / 'segments'
    bgm_dir = run_dir / 'bgm'
    scenes_dir = run_dir / 'scenes'
    speech_entries: list[Dict[str, Any]] = []
    timeline_entries: list[Dict[str, Any]] = []
    raw_segments = [segment.model_dump() for segment in audio_handoff.audio_segments]
    for segment in raw_segments:
        tts_output = speak_segment(segment, segments_dir)
        start_tick = int(float(segment['timing_offset_seconds']) * 1000)
        span_ms = int(float(tts_output['duration_seconds']) * 1000)
        end_tick = start_tick + span_ms
        segment_record = {'segment_id': segment['segment_id'], 'scene_id': segment.get('scene_key') or segment.get('scene_id', ''), 'character_id': segment['character_id'], 'line_id': segment['line_id'], 'text': segment.get('copy_text') or segment.get('text', ''), 'emotion': segment['emotion'], 'audio_file': tts_output['audio_file'], 'start_ms': start_tick, 'end_ms': end_tick, 'duration_ms': span_ms, 'provider': tts_output['provider']}
        speech_entries.append(segment_record)
        timeline_entries.append(segment_record)
    scene_mix_entries: list[Dict[str, Any]] = []
    music_entries: list[Dict[str, Any]] = []
    for scene_key in collect_scene_keys(raw_segments):
        scene_segments = [item for item in speech_entries if item.get('scene_id') == scene_key]
        scene_duration = max((item['end_ms'] for item in scene_segments), default=1000) / 1000.0 + 0.5
        layers: list[Dict[str, Any]] = [{'audio_file': item['audio_file'], 'start_seconds': item['start_ms'] / 1000.0} for item in scene_segments]
        if include_bgm:
            bgm = compose_bed_track(scene_key=scene_key, mood=audio_handoff.music_moods.get(scene_key, 'neutral'), duration_s=scene_duration, destination_dir=bgm_dir)
            music_entries.append(bgm)
            layers.insert(0, {'audio_file': bgm['audio_file'], 'start_seconds': 0.0})
        scene_mix = mix_audio_layers(layers=layers, destination=scenes_dir / f'{scene_key}_mix.wav', duration_s=scene_duration)
        scene_mix_entries.append({'scene_id': scene_key, **scene_mix})
    full_audio = concat_audio_files([layer['audio_file'] for layer in scene_mix_entries], run_dir / 'full_audio.wav')
    manifest = {'phase': 'phase2_audio', 'run_status': 'success', 'output_dir': str(run_dir), 'segments': timeline_entries, 'scene_mix_rows': scene_mix_entries, 'music_rows': music_entries, 'full_audio': full_audio, 'total_segments': len(timeline_entries), 'total_duration_ms': int(float(full_audio['duration_seconds']) * 1000)}
    summary = {'success': True, 'output_dir': str(run_dir), 'timing_manifest': str(run_dir / 'timing_manifest.json'), 'full_audio': full_audio['audio_file'], 'scene_count': len(scene_mix_entries), 'segment_count': len(timeline_entries), 'providers': {'tts': sorted({segment['provider'] for segment in speech_entries}), 'bgm': 'offline_procedural_bgm' if include_bgm else 'disabled'}}
    dump_json(run_dir / 'timing_manifest.json', manifest)
    dump_json(run_dir / 'summary.json', summary)
    return {**summary, 'manifest': manifest, 'errors': []}

def dump_json(target_path: Path, request_body: Any) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open('w', encoding='utf-8') as fh:
        json.dump(request_body, fh, indent=2, ensure_ascii=False)

def collect_scene_keys(segments: Iterable[Dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for segment in segments:
        scene_key = segment.get('scene_key') or segment.get('scene_id', '')
        if scene_key not in ordered:
            ordered.append(scene_key)
    return ordered

def clockstamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')
if __name__ == '__main__':
    default_handoff = PROJECT_ROOT / 'data' / 'outputs' / 'phase1' / '20260502_173240' / 'phase2_audio_handoff.json'
    handoff_path = Path(os.environ.get('PHASE2_HANDOFF_PATH', default_handoff))
    outcome = execute_phase_two(handoff_path)
    print(json.dumps({k: v for k, v in outcome.items() if k != 'manifest'}, indent=2))
