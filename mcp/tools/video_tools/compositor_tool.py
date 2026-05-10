"""compositor_tool.py — composite scene clips into a final MP4.

Uses MoviePy when available; falls back to a pure-FFmpeg concat when not.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.base_tool import ToolKernel

# ── Optional MoviePy import ──────────────────────────────────────────────────
try:
    import moviepy.config as _mpy_config
    _mpy_config.IMAGEMAGICK_BINARY = r'D:\ImageMagick-7.1.2-Q16\magick.exe'
    from moviepy.editor import (
        AudioFileClip, ColorClip, CompositeVideoClip, ImageClip,
        TextClip, VideoFileClip, concatenate_videoclips,
    )
    MOVIEPY_OK = True
except Exception:
    MOVIEPY_OK = False


# ── FFmpeg fallback ──────────────────────────────────────────────────────────

def _ffmpeg(*args: str) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, raising on non-zero exit."""
    cmd = ['ffmpeg', '-y', *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg error:\n{result.stderr[-2000:]}')
    return result


def _compose_with_ffmpeg(
    scene_sources: List[str],
    destination: str,
    story_headline: str = '',
    frame_rate: int = 24,
    frame_width: int = 1280,
    frame_height: int = 720,
) -> str:
    """Concatenate scene MP4s with FFmpeg concat demuxer (no re-encode)."""
    Path(destination).parent.mkdir(parents=True, exist_ok=True)

    valid = [p for p in scene_sources if os.path.exists(p)]
    if not valid:
        raise RuntimeError('No scene clips found — cannot composite.')

    print(f'  [compositor/ffmpeg] Concatenating {len(valid)} clips → {destination}')

    # Write a concat list file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                     delete=False, encoding='utf-8') as fh:
        list_path = fh.name
        for p in valid:
            # ffmpeg concat requires forward-slashes or escaped backslashes
            fh.write(f"file '{p.replace(chr(92), '/')}'\n")

    try:
        _ffmpeg(
            '-f', 'concat',
            '-safe', '0',
            '-i', list_path,
            '-c', 'copy',
            destination,
        )
    finally:
        os.unlink(list_path)

    print(f'  [compositor/ffmpeg] Done → {destination}')
    return destination


# ── MoviePy path ─────────────────────────────────────────────────────────────

def _compose_with_moviepy(
    scene_sources: List[str],
    destination: str,
    story_headline: str = '',
    transition_duration: float = 0.8,
    frame_rate: int = 24,
    frame_width: int = 1280,
    frame_height: int = 720,
    add_title_card: bool = True,
    add_end_card: bool = True,
) -> str:
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    clip_items = []

    if add_title_card and story_headline:
        print(f"  [compositor] Creating title card: '{story_headline}'")
        title_clip = ColorClip(
            size=(frame_width, frame_height), color=(10, 10, 20), duration=3.0
        ).set_fps(frame_rate)
        try:
            txt = TextClip(
                story_headline, fontsize=52, color='white',
                font='DejaVu-Sans-Bold',
                size=(frame_width - 120, None), method='caption',
            ).set_duration(3.0).set_position('center')
            title_clip = CompositeVideoClip([title_clip, txt]).set_fps(frame_rate)
        except Exception as exc:
            print(f'  [compositor] TextClip failed ({exc}), skipping title text.')
        clip_items.append(title_clip)

    loaded = []
    for p in scene_sources:
        if not os.path.exists(p):
            print(f'  [compositor] WARNING: clip not found: {p}')
            continue
        clip = VideoFileClip(p).set_fps(frame_rate)
        if clip.size != (frame_width, frame_height):
            clip = clip.resize((frame_width, frame_height))
        loaded.append(clip)
        print(f'  [compositor] Loaded {Path(p).name} ({clip.duration:.1f}s)')

    if not loaded:
        raise RuntimeError('No scene clips found — cannot composite.')
    clip_items.extend(loaded)

    if add_end_card:
        end_clip = ColorClip(
            size=(frame_width, frame_height), color=(10, 10, 20), duration=2.0
        ).set_fps(frame_rate)
        try:
            end_txt = TextClip(
                '— The End —', fontsize=46, color='white', font='DejaVu-Sans-Bold',
            ).set_duration(2.0).set_position('center')
            end_clip = CompositeVideoClip([end_clip, end_txt]).set_fps(frame_rate)
        except Exception:
            pass
        clip_items.append(end_clip)

    print(f'  [compositor] Concatenating {len(clip_items)} clips…')
    if transition_duration > 0 and len(clip_items) > 1:
        final = concatenate_videoclips(
            clip_items, method='compose',
            padding=-transition_duration, transition=None,
        )
    else:
        final = concatenate_videoclips(clip_items, method='compose')

    final = final.set_fps(frame_rate)
    print(f'  [compositor] Writing → {destination}')
    final.write_videofile(
        destination, fps=frame_rate, codec='libx264', preset='fast',
        audio_codec='aac', audio_bitrate='192k', threads=4, logger=None,
    )
    for c in loaded:
        c.close()
    return destination


# ── Public entry point ────────────────────────────────────────────────────────

def compose_with_moviepy(
    scene_sources: List[str],
    destination: str,
    story_headline: str = '',
    transition_duration: float = 0.8,
    frame_rate: int = 24,
    frame_width: int = 1280,
    frame_height: int = 720,
    add_title_card: bool = True,
    add_end_card: bool = True,
) -> str:
    """Composite scene clips. Uses MoviePy if available, FFmpeg otherwise."""
    if MOVIEPY_OK:
        return _compose_with_moviepy(
            scene_sources=scene_sources,
            destination=destination,
            story_headline=story_headline,
            transition_duration=transition_duration,
            frame_rate=frame_rate,
            frame_width=frame_width,
            frame_height=frame_height,
            add_title_card=add_title_card,
            add_end_card=add_end_card,
        )
    else:
        print('  [compositor] MoviePy unavailable — using FFmpeg concat fallback.')
        return _compose_with_ffmpeg(
            scene_sources=scene_sources,
            destination=destination,
            story_headline=story_headline,
            frame_rate=frame_rate,
            frame_width=frame_width,
            frame_height=frame_height,
        )


# ── MCP Tool wrapper ──────────────────────────────────────────────────────────

class SceneComposerTool(ToolKernel):
    """MCP tool: composite scene clips into final MP4."""
    name = 'compositor'
    description = 'Assembles scene clips with transitions into final_output.mp4.'

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(['scene_clip_paths', 'output_path'], kwargs)
        target_path = compose_with_moviepy(
            scene_sources=kwargs['scene_clip_paths'],
            destination=kwargs['output_path'],
            story_headline=kwargs.get('story_title', ''),
            transition_duration=kwargs.get('transition_duration', 0.8),
            frame_rate=kwargs.get('fps', 24),
            frame_width=kwargs.get('width', 1280),
            frame_height=kwargs.get('height', 720),
            add_title_card=kwargs.get('add_title_card', True),
            add_end_card=kwargs.get('add_end_card', True),
        )
        return {'success': True, 'output_path': target_path}
