"""Reworked module for narrative.cinematics.engine.py"""
from datetime import datetime
from pathlib import Path
from mcp.tools.video_tools.subtitle_tool import CaptionWriterTool
from mcp.tools.video_tools.ffmpeg_tool import FfmpegBridgeTool, attach_soundtrack, burn_subtitles, fade_video_clip, probe_audio_duration, stitch_video_clips, turn_image_into_clip
from mcp.tools.video_tools.compositor_tool import SceneComposerTool
from mcp.tools.vision_tools.image_gen_tool import StoryboardTool
from typing import Any, Dict, List, Optional
import json
import os
import shutil
import subprocess
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHOT_MOVES = {'wide': 'zoom_in', 'mid': 'pan_left', 'closeup': 'zoom_out', 'atmosphere': 'pan_right'}
MOVE_SEQUENCE = ['zoom_in', 'pan_left', 'zoom_out', 'pan_right', 'zoom_in']

def write_json(blob: Any, target_path: str):
    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(blob, f, indent=2, ensure_ascii=False)

def scene_audio_duration(scene_key: str, timing_manifest: List[Dict], phase_two_dir: str, scene_data: Dict, default: float=8.0) -> float:
    """
    Return scene audio duration from:
    1. Actual audio file length
    2. Timing manifest start/end_ms
    3. Phase 1 duration_seconds
    4. Default
    """
    audio = find_scene_audio(scene_key, timing_manifest, phase_two_dir)
    if audio:
        try:
            dur = probe_audio_duration(audio)
            return max(dur, 3.0)
        except Exception:
            pass
    entries = [e for e in timing_manifest if e.get('scene_id') == scene_key]
    if entries:
        start = min((e.get('start_ms', 0) for e in entries))
        end = max((e.get('end_ms', 0) for e in entries))
        if end > start:
            return max((end - start) / 1000.0, 3.0)
    p1 = scene_data.get('duration_seconds') or scene_data.get('duration_sec')
    if p1:
        return float(p1)
    return default

def read_json(target_path: str) -> Any:
    with open(target_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def optimize_final_render(input_path: str, destination: str) -> str:
    """Re-encode with CRF 18 (high quality) + slow preset for final delivery."""
    print(f'  [optimize] FFmpeg quality pass (CRF 18)…')
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vcodec', 'libx264', '-crf', '18', '-preset', 'slow', '-acodec', 'aac', '-b:a', '192k', '-movflags', '+faststart', destination]
    outcome = subprocess.run(cmd, capture_output=True, text=True)
    if outcome.returncode != 0:
        print(f'  [optimize] Warning: quality pass failed, using unoptimized video.')
        shutil.copy2(input_path, destination)
    return destination

def merge_scene_images(clip_sources: List[str], destination: str, total_duration: float, frame_rate: int=24, crossfade_sec: float=0.4) -> str:
    """
    Concatenate multiple silent image clips with xfade transitions using FFmpeg.
    Clips are trimmed so total == total_duration.
    Returns output_path.
    """
    n = len(clip_sources)
    if n == 1:
        shutil.copy2(clip_sources[0], destination)
        return destination
    clip_dur = total_duration / n
    inputs = []
    for p in clip_sources:
        inputs += ['-i', p]
    filter_parts = []
    start_offset = clip_dur - crossfade_sec
    prev_label = '0:v'
    for i in range(1, n):
        out_label = f'v{i}'
        xfade = f'[{prev_label}][{i}:v]xfade=transition=fade:duration={crossfade_sec}:offset={start_offset:.3f}[{out_label}]'
        filter_parts.append(xfade)
        prev_label = out_label
        start_offset += clip_dur - crossfade_sec
    filter_complex = '; '.join(filter_parts)
    final_label = f'v{n - 1}'
    cmd = ['ffmpeg', '-y'] + inputs + ['-filter_complex', filter_complex, '-map', f'[{final_label}]', '-t', str(total_duration), '-r', str(frame_rate), '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', destination]
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    outcome = subprocess.run(cmd, capture_output=True, text=True)
    if outcome.returncode != 0:
        print(f'  [xfade] xfade failed, using simple concat fallback.')
        return stitch_video_clips(clip_sources, destination)
    return destination

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Phase 3 — Video Agent')
    parser.add_argument('--phase1-dir', default=None)
    parser.add_argument('--phase2-dir', default=None)
    parser.add_argument('--output-dir', default=None)
    parser.add_argument('--no-subtitles', action='store_true')
    parser.add_argument('--no-ollama', action='store_true')
    parser.add_argument('--images-per-scene', type=int, default=3)
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=720)
    args = parser.parse_args()
    outputs_base = PROJECT_ROOT / 'data' / 'outputs'
    phase_one_dir = args.phase1_dir or os.environ.get('PHASE1_RUN_DIR') or latest_run_dir(str(outputs_base / 'phase1'))
    phase_two_dir = args.phase2_dir or os.environ.get('PHASE2_RUN_DIR') or latest_run_dir(str(outputs_base / 'phase2'))
    if not phase_one_dir:
        raise FileNotFoundError('Phase 1 output directory not found.')
    if not phase_two_dir:
        raise FileNotFoundError('Phase 2 output directory not found.')
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    destination_dir = args.output_dir or os.environ.get('PHASE3_OUTPUT_DIR') or str(outputs_base / 'phase3' / run_id)
    burn_subs = not args.no_subtitles and os.environ.get('BURN_SUBTITLES', 'true').lower() != 'false'
    use_ollama = not args.no_ollama and os.environ.get('USE_OLLAMA', 'false').lower() == 'true'
    images_per_scene = int(os.environ.get('IMAGES_PER_SCENE', str(args.images_per_scene)))
    print(f'Phase 1 dir      : {phase_one_dir}')
    print(f'Phase 2 dir      : {phase_two_dir}')
    print(f'Output dir       : {destination_dir}')
    print(f'Images per scene : {images_per_scene}')
    print(f'Burn subtitles   : {burn_subs}')
    print(f'Use Ollama       : {use_ollama}')
    agent = RenderCoordinator(phase1_run_dir=phase_one_dir, phase2_run_dir=phase_two_dir, output_dir=destination_dir, burn_subs=burn_subs, use_ollama=use_ollama, images_per_scene=images_per_scene, fps=args.fps, width=args.width, height=args.height)
    return agent.run()

def latest_run_dir(base_dir: str) -> Optional[str]:
    base = Path(base_dir)
    if not base.exists():
        return None
    dirs = [d for d in base.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return str(sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)[0])

def find_scene_audio(scene_key: str, timing_manifest: List[Dict], phase_two_dir: str) -> Optional[str]:
    """Find the mixed audio file for a scene."""
    for ext in ['.wav', '.mp3']:
        for pattern in [f'{scene_key}_mix{ext}', f'{scene_key}{ext}']:
            p = os.path.join(phase_two_dir, 'scenes', pattern)
            if os.path.exists(p):
                return p
    for entry in timing_manifest:
        if entry.get('scene_id') == scene_key:
            af = entry.get('audio_file', '')
            if not af:
                continue
            for candidate in [af, os.path.join(phase_two_dir, af), os.path.join(phase_two_dir, 'scenes', Path(af).name), os.path.join(phase_two_dir, 'segments', Path(af).name)]:
                if os.path.exists(candidate):
                    return candidate
    full = os.path.join(phase_two_dir, 'full_audio.wav')
    if os.path.exists(full):
        return full
    return None

class RenderCoordinator:
    """
    Phase 3 agent — upgraded pipeline:
    - Multiple images per scene
    - Audio-synced durations
    - Varied Ken Burns per image
    - Crossfade between images
    - Subtitle burn-in
    - FFmpeg quality optimization
    """

    def __init__(self, phase_one_run_dir: str, phase_two_run_dir: str, destination_dir: str, burn_subs: bool=True, use_ollama: bool=False, images_per_scene: int=3, frame_rate: int=24, frame_width: int=1280, frame_height: int=720):
        self.phase1_dir = Path(phase_one_run_dir)
        self.phase2_dir = Path(phase_two_run_dir)
        self.output_dir = Path(destination_dir)
        self.burn_subs = burn_subs
        self.use_ollama = use_ollama
        self.images_per_scene = images_per_scene
        self.fps = frame_rate
        self.width = frame_width
        self.height = frame_height
        for sub in ['images', 'clips', 'scenes']:
            (self.output_dir / sub).mkdir(parents=True, exist_ok=True)
        self.image_tool = StoryboardTool()
        self.ffmpeg_tool = FfmpegBridgeTool()
        self.compositor = SceneComposerTool()
        self.subtitles = CaptionWriterTool()

    def load_handoff_bundle(self) -> Dict:
        for name in ['phase3_video_handoff.json', 'script.json', 'story.json']:
            p = self.phase1_dir / name
            if p.exists():
                print(f'[VideoAgent] Phase 1 handoff: {p.name}')
                return read_json(str(p))
        raise FileNotFoundError(f'No Phase 1 handoff in {self.phase1_dir}')

    def _load_manifest(self) -> List[Dict]:
        p = self.phase2_dir / 'timing_manifest.json'
        if p.exists():
            blob = read_json(str(p))
            if isinstance(blob, list):
                return blob
            return blob.get('entries', blob.get('segments', blob.get('manifest', [])))
        print('[VideoAgent] WARNING: no timing_manifest.json found.')
        return []

    def process_scene(self, scene: Dict, idx: int, manifest: List[Dict]) -> Optional[str]:
        scene_key = scene.get('scene_id') or f'scene_{idx + 1:03d}'
        sid = scene_key.lower().replace(' ', '_')
        print(f'\n[VideoAgent] ── Scene {idx + 1}: {scene_key} ──')
        visual_prompt = scene.get('visual_prompt') or scene.get('visual_description') or scene.get('description', 'A cinematic scene')
        negative_prompt = scene.get('negative_prompt', '')
        tone = scene.get('tone') or scene.get('mood') or 'neutral'
        setting = scene.get('setting') or scene.get('location') or ''
        print(f'  [1/5] Generating {self.images_per_scene} images…')
        img_dir = str(self.output_dir / 'images' / sid)
        try:
            img_result = self.image_tool.execute(scene_id=scene_key, visual_prompt=visual_prompt, negative_prompt=negative_prompt, tone=tone, setting=setting, num_images=self.images_per_scene, output_dir=img_dir, width=self.width, height=self.height, use_pollinations=True)
            image_paths = img_result['image_paths']
        except Exception as e:
            print(f'  ERROR generating images: {e}')
            return None
        if not image_paths:
            print(f'  ERROR: No images generated for {scene_key}')
            return None
        total_dur = scene_audio_duration(scene_key, manifest, str(self.phase2_dir), scene)
        per_image_dur = total_dur / len(image_paths)
        print(f'  [2/5] Scene duration: {total_dur:.1f}s → {per_image_dur:.1f}s per image')
        print(f'  [3/5] Animating images with varied Ken Burns…')
        raw_clips = []
        for i, img_path in enumerate(image_paths):
            stem = Path(img_path).stem
            parts = stem.split('_')
            shot_name = parts[-1] if parts else 'wide'
            effect = SHOT_MOVES.get(shot_name, MOVE_SEQUENCE[i % len(MOVE_SEQUENCE)])
            raw_clip = str(self.output_dir / 'clips' / f'{sid}_{i + 1:02d}_raw.mp4')
            try:
                turn_image_into_clip(image_path=img_path, destination=raw_clip, duration_s=per_image_dur, effect=effect, frame_rate=self.fps, frame_width=self.width, frame_height=self.height)
                raw_clips.append(raw_clip)
                print(f'    ✓ Image {i + 1} → {effect} ({per_image_dur:.1f}s)')
            except Exception as e:
                print(f'    WARNING: Ken Burns failed for image {i + 1}: {e}')
        if not raw_clips:
            return None
        print(f'  [4/5] Crossfading {len(raw_clips)} image clips…')
        merged_clip = str(self.output_dir / 'clips' / f'{sid}_merged.mp4')
        try:
            merge_scene_images(clip_paths=raw_clips, output_path=merged_clip, total_duration=total_dur, fps=self.fps, crossfade_sec=0.35)
        except Exception as e:
            print(f'  WARNING: crossfade failed ({e}), using first clip.')
            merged_clip = raw_clips[0]
        source_audio = find_scene_audio(scene_key, manifest, str(self.phase2_dir))
        with_audio = str(self.output_dir / 'clips' / f'{sid}_audio.mp4')
        if source_audio:
            print(f'  [5/5] Muxing audio ({Path(source_audio).name})…')
            try:
                attach_soundtrack(merged_clip, source_audio, with_audio, total_dur)
            except Exception as e:
                print(f'  WARNING: audio mux failed ({e})')
                with_audio = merged_clip
        else:
            print(f'  [5/5] No audio — proceeding silent.')
            with_audio = merged_clip
        faded = str(self.output_dir / 'scenes' / f'{sid}_final.mp4')
        try:
            fade_video_clip(with_audio, faded, fade_in_sec=0.3, fade_out_sec=0.3)
        except Exception as e:
            print(f'  WARNING: fade failed ({e})')
            shutil.copy2(with_audio, faded)
        print(f'  ✓ Scene clip: {Path(faded).name} ({total_dur:.1f}s)')
        return faded

    def run(self) -> Dict:
        print('\n' + '=' * 60)
        print('  Phase 3 — Video Generation & Composition')
        print('=' * 60)
        handoff = self._load_handoff()
        manifest = self._load_manifest()
        scenes = handoff.get('scenes') or handoff.get('script', {}).get('scenes') or handoff.get('story', {}).get('scenes') or []
        headline = handoff.get('title') or handoff.get('story', {}).get('title') or 'Untitled Story'
        if not scenes:
            raise ValueError('No scenes in Phase 1 handoff.')
        print(f'\n  Story        : {headline}')
        print(f'  Scenes       : {len(scenes)}')
        print(f'  Images/scene : {self.images_per_scene}')
        print(f'  Manifest     : {len(manifest)} entries')
        print(f'  Output       : {self.output_dir}\n')
        scene_clips = []
        for i, scene in enumerate(scenes):
            clip = self.process_scene(scene, i, manifest)
            if clip:
                scene_clips.append(clip)
        if not scene_clips:
            raise RuntimeError('No scene clips produced.')
        srt_path = str(self.output_dir / 'subtitles.srt')
        if manifest:
            print(f'\n[VideoAgent] Building SRT subtitles…')
            self.subtitles.execute(timing_manifest=manifest, output_path=srt_path)
        else:
            srt_path = None
        print(f'\n[VideoAgent] Compositing {len(scene_clips)} scene clips…')
        raw_final = str(self.output_dir / 'final_raw.mp4')
        self.compositor.execute(scene_clip_paths=scene_clips, output_path=raw_final, story_title=headline, transition_duration=0.5, fps=self.fps, width=self.width, height=self.height, add_title_card=True, add_end_card=True)
        optimized = str(self.output_dir / 'final_output.mp4')
        optimize_final_render(raw_final, optimized)
        final_path = optimized
        if self.burn_subs and srt_path and os.path.exists(srt_path):
            print(f'\n[VideoAgent] Burning subtitles…')
            subtitled = str(self.output_dir / 'final_output_subtitled.mp4')
            try:
                burn_subtitles(optimized, srt_path, subtitled)
                final_path = subtitled
                print(f'  ✓ Subtitled video: {subtitled}')
            except Exception as e:
                print(f'  WARNING: subtitle burn failed: {e}')
        summary = {'phase': 3, 'run_id': self.output_dir.name, 'story_title': headline, 'scenes_processed': len(scene_clips), 'total_scenes': len(scenes), 'images_per_scene': self.images_per_scene, 'final_video': final_path, 'subtitles': srt_path, 'scene_clips': scene_clips, 'output_dir': str(self.output_dir), 'status': 'success'}
        write_json(summary, str(self.output_dir / 'summary.json'))
        print('\n' + '=' * 60)
        print(f'  ✅  Phase 3 Complete!')
        print(f'      Final video : {final_path}')
        print(f'      Output dir  : {self.output_dir}')
        print('=' * 60 + '\n')
        return summary
sys.path.insert(0, str(PROJECT_ROOT))
if __name__ == '__main__':
    main()
