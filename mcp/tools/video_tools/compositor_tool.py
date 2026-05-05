"""Reworked module for toolkit.video.compositor.py"""
from pathlib import Path
from mcp.base_tool import ToolKernel
from typing import Any, Dict, List, Optional
import json
import moviepy.config as mpy_config
import os
import sys
mpy_config.IMAGEMAGICK_BINARY = 'D:\\ImageMagick-7.1.2-Q16\\magick.exe'

def compose_with_moviepy(scene_sources: List[str], destination: str, story_headline: str='', transition_duration: float=0.8, frame_rate: int=24, frame_width: int=1280, frame_height: int=720, add_title_card: bool=True, add_end_card: bool=True) -> str:
    """
    Load per-scene MP4s, add crossfade transitions, and export final_output.mp4.
    """
    if not MOVIEPY_OK:
        raise RuntimeError('MoviePy not installed.')
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    clip_items = []
    if add_title_card and story_headline:
        print(f"  [compositor] Creating title card: '{story_headline}'")
        title_clip = ColorClip(size=(frame_width, frame_height), color=(10, 10, 20), duration=3.0).set_fps(frame_rate)
        try:
            txt = TextClip(story_headline, fontsize=52, color='white', font='DejaVu-Sans-Bold', size=(frame_width - 120, None), method='caption').set_duration(3.0).set_position('center')
            title_clip = CompositeVideoClip([title_clip, txt]).set_fps(frame_rate)
        except Exception as e:
            print(f'  [compositor] TextClip failed ({e}), skipping title text.')
        clip_items.append(title_clip)
    loaded_clips = []
    for p in scene_sources:
        if not os.path.exists(p):
            print(f'  [compositor] WARNING: clip not found: {p}')
            continue
        clip = VideoFileClip(p).set_fps(frame_rate)
        if clip.size != (frame_width, frame_height):
            clip = clip.resize((frame_width, frame_height))
        loaded_clips.append(clip)
        print(f'  [compositor] Loaded {Path(p).name} ({clip.duration:.1f}s)')
    if not loaded_clips:
        raise RuntimeError('No scene clips found — cannot composite.')
    clip_items.extend(loaded_clips)
    if add_end_card:
        end_clip = ColorClip(size=(frame_width, frame_height), color=(10, 10, 20), duration=2.0).set_fps(frame_rate)
        try:
            end_txt = TextClip('— The End —', fontsize=46, color='white', font='DejaVu-Sans-Bold').set_duration(2.0).set_position('center')
            end_clip = CompositeVideoClip([end_clip, end_txt]).set_fps(frame_rate)
        except Exception:
            pass
        clip_items.append(end_clip)
    print(f'  [compositor] Concatenating {len(clip_items)} clips with {transition_duration}s crossfades…')
    if transition_duration > 0 and len(clip_items) > 1:
        final = concatenate_videoclips(clip_items, method='compose', padding=-transition_duration, transition=None)
    else:
        final = concatenate_videoclips(clip_items, method='compose')
    final = final.set_fps(frame_rate)
    print(f'  [compositor] Writing final video → {destination}')
    final.write_videofile(destination, fps=frame_rate, codec='libx264', preset='fast', audio_codec='aac', audio_bitrate='192k', threads=4, logger=None)
    for c in loaded_clips:
        c.close()
    return destination

def build_title_card(headline: str, duration: float=3.0, frame_width: int=1280, frame_height: int=720, frame_rate: int=24, destination: str=None) -> 'VideoFileClip':
    """Create a simple dark title card with white text."""
    bg = ColorClip(size=(frame_width, frame_height), color=(10, 10, 20), duration=duration)
    try:
        txt = TextClip(headline, fontsize=52, color='white', font='DejaVu-Sans-Bold', size=(frame_width - 100, None), method='caption').set_duration(duration).set_position('center')
        card = CompositeVideoClip([bg, txt]).set_fps(frame_rate)
    except Exception:
        card = bg.set_fps(frame_rate)
    if destination:
        card.write_videofile(destination, fps=frame_rate, codec='libx264', preset='fast', audio=False, logger=None)
    return card

class SceneComposerTool(ToolKernel):
    """MCP tool: composite scene clips into final MP4 using MoviePy."""
    name = 'compositor'
    description = 'Assembles scene clips with transitions into final_output.mp4.'

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(['scene_clip_paths', 'output_path'], kwargs)
        target_path = compose_with_moviepy(scene_clip_paths=kwargs['scene_clip_paths'], output_path=kwargs['output_path'], story_title=kwargs.get('story_title', ''), transition_duration=kwargs.get('transition_duration', 0.8), fps=kwargs.get('fps', 24), width=kwargs.get('width', 1280), height=kwargs.get('height', 720), add_title_card=kwargs.get('add_title_card', True), add_end_card=kwargs.get('add_end_card', True))
        return {'success': True, 'output_path': target_path}
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from moviepy.editor import VideoFileClip, ImageClip, ColorClip, TextClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
    MOVIEPY_OK = True
except ImportError:
    MOVIEPY_OK = False
