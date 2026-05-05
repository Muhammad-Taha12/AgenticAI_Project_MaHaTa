"""Reworked module for toolkit.video.ffmpeg_tool.py"""
from pathlib import Path
from toolkit.interface import ToolKernel
from typing import Any, Dict, List, Optional
import json
import os
import subprocess
import sys

def turn_image_into_clip(image_path: str, destination: str, duration_s: float, effect: str='zoom_in', frame_rate: int=24, frame_width: int=1280, frame_height: int=720) -> str:
    """
    Animate a still image with a Ken Burns effect and output an MP4 clip.
    No audio is embedded here — audio is added in a later step.
    """
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    frames = int(duration_s * frame_rate)
    zoom_speed = 0.0008
    if effect == 'zoom_in':
        vf = f"zoompan=z='min(zoom+{zoom_speed},1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={frame_width}x{frame_height}:fps={frame_rate}"
    elif effect == 'zoom_out':
        vf = f"zoompan=z='if(lte(zoom,1.0),1.3,max(1.0,zoom-{zoom_speed}))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={frame_width}x{frame_height}:fps={frame_rate}"
    elif effect == 'pan_left':
        vf = f"zoompan=z=1.1:x='if(gte(x,iw-iw/zoom),iw-iw/zoom,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={frame_width}x{frame_height}:fps={frame_rate}"
    elif effect == 'pan_right':
        vf = f"zoompan=z=1.1:x='max(0,x-1)':y='ih/2-(ih/zoom/2)':d={frames}:s={frame_width}x{frame_height}:fps={frame_rate}"
    else:
        vf = f'scale={frame_width}:{frame_height},setsar=1'
    cmd = ['ffmpeg', '-y', '-loop', '1', '-i', image_path, '-vf', vf, '-t', str(duration_s), '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', destination]
    _run(cmd, 'ken_burns')
    return destination

def stitch_video_clips(clip_sources: List[str], destination: str, frame_width: int=1280, frame_height: int=720) -> str:
    """
    Concatenate multiple MP4 clips into one final video using concat demuxer.
    All clips must have the same resolution and codec.
    """
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    list_file = Path(destination).parent / '_concat_list.txt'
    with open(list_file, 'w') as f:
        for p in clip_sources:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', destination]
    _run(cmd, 'concat')
    list_file.unlink(missing_ok=True)
    return destination

def probe_audio_duration(source_audio: str) -> float:
    """Return duration in seconds of an audio file."""
    probe = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', source_audio], capture_output=True, text=True)
    info = json.loads(probe.stdout)
    return float(info['format']['duration'])

def fade_video_clip(source_video: str, destination: str, fade_in_sec: float=0.5, fade_out_sec: float=0.5) -> str:
    """Apply fade-in and fade-out to a clip."""
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', source_video], capture_output=True, text=True)
    info = json.loads(probe.stdout)
    dur = float(info['format']['duration'])
    fade_out_start = max(0, dur - fade_out_sec)
    vf = f'fade=t=in:st=0:d={fade_in_sec},fade=t=out:st={fade_out_start:.3f}:d={fade_out_sec}'
    af = f'afade=t=in:st=0:d={fade_in_sec},afade=t=out:st={fade_out_start:.3f}:d={fade_out_sec}'
    cmd = ['ffmpeg', '-y', '-i', source_video, '-vf', vf, '-af', af, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '192k', destination]
    _run(cmd, 'fade')
    return destination

def burn_subtitles(source_video: str, srt_path: str, destination: str) -> str:
    """Burn SRT subtitles into video."""
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-i', source_video, '-vf', f"subtitles={srt_path}:force_style='FontSize=22,PrimaryColour=&Hffffff&'", '-c:a', 'copy', destination]
    _run(cmd, 'subtitles')
    return destination

def attach_soundtrack(source_video: str, source_audio: str, destination: str, video_duration: Optional[float]=None) -> str:
    """
    Mux audio into video. Audio is trimmed/padded to match video duration.
    """
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    if video_duration is None:
        probe = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', source_video], capture_output=True, text=True)
        info = json.loads(probe.stdout)
        video_duration = float(info['format']['duration'])
    cmd = ['ffmpeg', '-y', '-i', source_video, '-i', source_audio, '-map', '0:v:0', '-map', '1:a:0', '-shortest', '-t', str(video_duration), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', destination]
    _run(cmd, 'add_audio')
    return destination

def _run(cmd: List[str], label: str='ffmpeg') -> subprocess.CompletedProcess:
    """Run an ffmpeg command, raising on failure."""
    print(f"  [{label}] Running: {' '.join(cmd[:8])} …")
    outcome = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if outcome.returncode != 0:
        raise RuntimeError(f'[{label}] FFmpeg failed (rc={outcome.returncode}):\n{outcome.stderr[-800:]}')
    return outcome

class FfmpegBridgeTool(ToolKernel):
    """MCP tool: general FFmpeg operations for Phase 3."""
    name = 'ffmpeg_tool'
    description = 'Applies Ken Burns animation, audio muxing, fades, and concatenation.'

    def execute(self, **kwargs) -> Dict[str, Any]:
        operation = kwargs.get('operation')
        if not operation:
            raise ValueError('operation is required (ken_burns|add_audio|fade|concat|subtitles)')
        if operation == 'ken_burns':
            self.validate_inputs(['image_path', 'output_path', 'duration_sec'], kwargs)
            target_path = turn_image_into_clip(image_path=kwargs['image_path'], output_path=kwargs['output_path'], duration_sec=float(kwargs['duration_sec']), effect=kwargs.get('effect', 'zoom_in'), fps=kwargs.get('fps', 24), width=kwargs.get('width', 1280), height=kwargs.get('height', 720))
            return {'success': True, 'output_path': target_path}
        elif operation == 'add_audio':
            self.validate_inputs(['video_path', 'audio_path', 'output_path'], kwargs)
            target_path = attach_soundtrack(kwargs['video_path'], kwargs['audio_path'], kwargs['output_path'], kwargs.get('video_duration'))
            return {'success': True, 'output_path': target_path}
        elif operation == 'fade':
            self.validate_inputs(['video_path', 'output_path'], kwargs)
            target_path = fade_video_clip(kwargs['video_path'], kwargs['output_path'], kwargs.get('fade_in_sec', 0.5), kwargs.get('fade_out_sec', 0.5))
            return {'success': True, 'output_path': target_path}
        elif operation == 'concat':
            self.validate_inputs(['clip_paths', 'output_path'], kwargs)
            target_path = stitch_video_clips(kwargs['clip_paths'], kwargs['output_path'], kwargs.get('width', 1280), kwargs.get('height', 720))
            return {'success': True, 'output_path': target_path}
        elif operation == 'subtitles':
            self.validate_inputs(['video_path', 'srt_path', 'output_path'], kwargs)
            target_path = burn_subtitles(kwargs['video_path'], kwargs['srt_path'], kwargs['output_path'])
            return {'success': True, 'output_path': target_path}
        else:
            raise ValueError(f'Unknown operation: {operation}')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
