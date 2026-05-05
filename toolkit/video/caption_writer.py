"""Reworked module for toolkit.video.subtitles.py"""
from pathlib import Path
from toolkit.interface import ToolKernel
from typing import Any, Dict, List
import json
import os
import sys

def format_srt_timestamp(ms: int) -> str:
    """Convert milliseconds to SRT timestamp: HH:MM:SS,mmm"""
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def compile_srt_track(timing_manifest: List[Dict], destination: str) -> str:
    """
    timing_manifest entries expected shape:
      { scene_id, audio_file, start_ms, end_ms, text?, character? }
    """
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    lines = []
    idx = 1
    for entry in timing_manifest:
        start_tick = int(entry.get('start_ms', 0))
        end_tick = int(entry.get('end_ms', start_tick + 2000))
        copy_text = entry.get('text', entry.get('dialogue', '')).strip()
        character = entry.get('character', '')
        if not copy_text:
            continue
        label = f'{character}: {copy_text}' if character else copy_text
        lines.append(str(idx))
        lines.append(f'{format_srt_timestamp(start_tick)} --> {format_srt_timestamp(end_tick)}')
        lines.append(label)
        lines.append('')
        idx += 1
    with open(destination, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return destination

class CaptionWriterTool(ToolKernel):
    name = 'subtitles'
    description = 'Generates SRT subtitle file from timing manifest.'

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(['timing_manifest', 'output_path'], kwargs)
        target_path = compile_srt_track(kwargs['timing_manifest'], kwargs['output_path'])
        return {'success': True, 'output_path': target_path}
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
