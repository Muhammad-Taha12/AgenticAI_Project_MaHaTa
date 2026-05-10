"""Reworked module for narrative.storycraft.exporter.py"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import os
logger = logging.getLogger(__name__)

def persist_phase_one_outputs(story: Dict[str, Any], roster: Dict[str, Any], script: Dict[str, Any], tools_log: List[Dict[str, Any]], issues: List[str], run_status: str='success', destination_dir: Optional[Path]=None) -> Dict[str, str]:
    """Saves all Phase 1 artifacts and returns a path map.

    Args:
        story:      StoryOutput dict.
        roster:     CharacterRoster dict.
        script:     ScriptOutput dict.
        tools_log:  Accumulated tool-call log from all nodes.
        errors:     Error messages from the pipeline run.
        run_status: 'success' | 'partial' | 'failed'.
        output_dir: Override output directory (uses env / default if None).

    Returns:
        Dict mapping artifact name → absolute file path string.
    """
    out = destination_dir or _output_dir()
    target_paths: Dict[str, str] = {}
    target_paths['story'] = dump_json(story, out / 'story.json')
    target_paths['characters'] = dump_json(roster, out / 'characters.json')
    target_paths['script'] = dump_json(script, out / 'script.json')
    stage_two = build_phase2_handoff(story, roster, script)
    target_paths['phase2_audio_handoff'] = dump_json(stage_two, out / 'phase2_audio_handoff.json')
    stage_three = build_phase3_handoff(story, roster, script)
    target_paths['phase3_video_handoff'] = dump_json(stage_three, out / 'phase3_video_handoff.json')
    summary = {'run_status': run_status, 'timestamp': datetime.now().isoformat(), 'errors': issues, 'tools_log': tools_log, 'artifact_paths': target_paths, 'stats': {'scene_count': len(story.get('scenes', [])), 'character_count': len(roster.get('characters', [])), 'total_dialogue_lines': sum((len(s.get('dialogue', [])) for s in script.get('scenes', []))), 'estimated_total_seconds': story.get('total_estimated_duration_seconds', 0), 'total_audio_segments': stage_two['total_segments']}}
    target_paths['summary'] = dump_json(summary, out / 'summary.json')
    logger.info('Phase 1 artifacts saved to: %s', out)
    return target_paths

def dump_json(blob: Any, target_path: Path) -> str:
    with open(target_path, 'w', encoding='utf-8') as fh:
        json.dump(blob, fh, indent=2, ensure_ascii=False)
    logger.info('Saved artifact: %s', target_path)
    return str(target_path)

def build_phase3_handoff(story: Dict[str, Any], roster: Dict[str, Any], script: Dict[str, Any]) -> Dict[str, Any]:
    """Constructs phase3_video_handoff.json from Phase 1 outputs."""
    char_prompts: Dict[str, str] = {char['character_id']: char['appearance'].get('art_style_prompt', '') for char in roster.get('characters', [])}
    scene_chars: Dict[str, List[str]] = {}
    for char in roster.get('characters', []):
        for sid in char.get('scenes_appearing_in', []):
            scene_chars.setdefault(sid, []).append(char['character_id'])
    story_durations: Dict[str, int] = {(s.get('scene_key') or s.get('scene_id', '')): s.get('estimated_duration_seconds', 30) for s in story.get('scenes', [])}
    scene_visuals: List[Dict[str, Any]] = []
    for ss in script.get('scenes', []):
        sid = ss.get('scene_key') or ss.get('scene_id', '')
        scene_visuals.append({'scene_id': sid, 'visual_prompt': ss.get('visual_prompt', ''), 'negative_prompt': ss.get('negative_visual_prompt', 'blurry, low quality, distorted faces, watermark'), 'camera_movement': ss.get('camera_movement', 'ken_burns'), 'transition_in': ss.get('transition_in', 'fade_in'), 'transition_out': ss.get('transition_out', 'fade_out'), 'duration_seconds': ss.get('estimated_duration_seconds', story_durations.get(sid, 30)), 'character_ids_in_scene': scene_chars.get(sid, [])})
    return {'scenes': scene_visuals, 'character_appearance_prompts': char_prompts, 'global_art_style': roster.get('global_art_style', 'cinematic animation')}

def build_phase2_handoff(story: Dict[str, Any], roster: Dict[str, Any], script: Dict[str, Any]) -> Dict[str, Any]:
    """Constructs phase2_audio_handoff.json from Phase 1 outputs."""
    voice_configs: Dict[str, Any] = {char['character_id']: char['voice_config'] for char in roster.get('characters', [])}
    audio_segments: List[Dict[str, Any]] = []
    for i, scene_script in enumerate(script.get('scenes', [])):
        scene_key = scene_script.get('scene_key') or scene_script.get('scene_id', f'scene_{i+1:03d}')
        for line in scene_script.get('dialogue', []):
            audio_segments.append({'segment_id': f"{scene_key}_{line['line_id']}", 'scene_id': scene_key, 'character_id': line['character_id'], 'line_id': line['line_id'], 'text': line.get('copy_text') or line.get('text', ''), 'voice_config': voice_configs.get(line['character_id'], {}), 'timing_offset_seconds': line.get('timing_offset_seconds', 0.0), 'duration_hint_seconds': line.get('duration_hint_seconds', 3.0), 'emotion': line.get('emotion', 'neutral')})
    music_moods: Dict[str, str] = {(s.get('scene_key') or s.get('scene_id', '')): s.get('background_music_mood', 'neutral') for s in script.get('scenes', [])}
    return {'voice_configs': voice_configs, 'audio_segments': audio_segments, 'music_moods': music_moods, 'total_segments': len(audio_segments)}

def _output_dir() -> Path:
    base = os.environ.get('PHASE1_OUTPUT_DIR', 'data/outputs')
    run_dir = Path(base) / 'phase1' / datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
