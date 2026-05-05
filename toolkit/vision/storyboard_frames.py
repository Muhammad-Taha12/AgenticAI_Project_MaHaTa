"""Reworked module for toolkit.vision.image_generation.py"""
from pathlib import Path
from toolkit.interface import ToolKernel
from typing import Any, Dict, List, Optional
import hashlib
import io
import random
import requests
import sys
import urllib.parse
SHOT_TYPES = [{'name': 'wide', 'suffix': 'wide establishing shot, full environment visible, epic scale, expansive view'}, {'name': 'mid', 'suffix': 'medium shot, character prominently in frame, cinematic composition, eye level'}, {'name': 'closeup', 'suffix': 'close-up shot, dramatic detail focus, shallow depth of field, emotional intensity'}, {'name': 'atmosphere', 'suffix': 'atmospheric wide shot, mood lighting, environmental storytelling, cinematic color grade'}]
MOOD_PALETTES = {'happy': [(255, 220, 100), (255, 140, 30)], 'sad': [(60, 80, 120), (40, 60, 100)], 'mysterious': [(30, 10, 60), (20, 40, 70)], 'tense': [(180, 30, 30), (80, 10, 10)], 'peaceful': [(80, 160, 200), (140, 210, 240)], 'exciting': [(220, 80, 30), (240, 160, 60)], 'adventurous': [(60, 140, 60), (80, 160, 80)], 'neutral': [(100, 120, 140), (120, 140, 160)], 'default': [(50, 80, 130), (70, 100, 150)]}

def generate_story_frames(scene_key: str, visual_prompt: str, negative_prompt: str, tone: str, setting: str, num_images: int, destination_dir: str, frame_width: int=1280, frame_height: int=720, use_pollinations: bool=True) -> List[str]:
    """
    Generate `num_images` PNG files for one scene.
    Each image uses a different shot type (wide → mid → closeup → atmosphere).
    Returns list of saved PNG paths.
    """
    Path(destination_dir).mkdir(parents=True, exist_ok=True)
    target_paths = []
    base_seed = _seed_from_text(scene_key + visual_prompt)
    shots = [SHOT_TYPES[i % len(SHOT_TYPES)] for i in range(num_images)]
    for i, shot in enumerate(shots):
        shot_name = shot['name']
        out_path = str(Path(destination_dir) / f'{scene_key}_{i + 1:02d}_{shot_name}.png')
        print(f'    [image_gen] {scene_key} — image {i + 1}/{num_images} ({shot_name})…')
        img = None
        if use_pollinations:
            brief = _build_shot_prompt(visual_prompt, shot)
            seed = (base_seed + i * 1337) % 99999
            img = _fetch_pollinations(brief, frame_width, frame_height, seed)
        if img is None:
            img = _pil_fallback(scene_key, shot_name, tone, frame_width, frame_height)
        img.save(out_path, 'PNG')
        target_paths.append(out_path)
        print(f'    [image_gen] ✓ {Path(out_path).name}')
    return target_paths

def _seed_from_text(copy_text: str) -> int:
    return int(hashlib.md5(copy_text.encode()).hexdigest(), 16) % 99999

def _pil_fallback(scene_key: str, shot_name: str, tone: str, frame_width: int, frame_height: int) -> 'Image.Image':
    """Generate a simple gradient placeholder image."""
    print(f'    [image_gen] PIL fallback for {scene_key}/{shot_name}')
    rng = random.Random(_seed_from_text(scene_key + shot_name))
    palette = MOOD_PALETTES.get(tone.lower(), MOOD_PALETTES['default'])
    top, bot = (palette[0], palette[-1])
    img = Image.new('RGB', (frame_width, frame_height))
    draw = ImageDraw.Draw(img)
    for y in range(frame_height):
        t = y / frame_height
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        draw.line([(0, y), (frame_width, y)], fill=(r, g, b))
    combined = (scene_key + tone).lower()
    if any((w in combined for w in ['mars', 'space', 'star', 'night', 'dark'])):
        for _ in range(150):
            x = rng.randint(0, frame_width)
            y = rng.randint(0, frame_height // 2)
            draw.ellipse([x - 1, y - 1, x + 2, y + 2], fill=(255, 255, 240))
    vignette = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(60):
        vd.rectangle([i, i, frame_width - i, frame_height - i], outline=(0, 0, 0, int(i * 2)))
    img = Image.alpha_composite(img.convert('RGBA'), vignette).convert('RGB')
    img = ImageEnhance.Contrast(img).enhance(1.1)
    return img

def _fetch_pollinations(brief: str, frame_width: int, frame_height: int, seed: int, retries: int=2) -> Optional['Image.Image']:
    """Fetch one image from Pollinations AI (FLUX model). No API key needed."""
    encoded = urllib.parse.quote(brief)
    url = f'https://image.pollinations.ai/prompt/{encoded}?width={min(frame_width, 1280)}&height={min(frame_height, 720)}&model=flux&seed={seed}&nologo=true&enhance=true'
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 200:
                ct = resp.headers.get('content-type', '')
                if 'image' not in ct:
                    print(f'    [image_gen] Non-image response (attempt {attempt + 1})')
                    continue
                img = Image.open(io.BytesIO(resp.content)).convert('RGB')
                if img.size != (frame_width, frame_height):
                    img = img.resize((frame_width, frame_height), Image.LANCZOS)
                return img
            else:
                print(f'    [image_gen] Pollinations HTTP {resp.status_code} (attempt {attempt + 1})')
        except requests.exceptions.Timeout:
            print(f'    [image_gen] Timeout (attempt {attempt + 1})')
        except Exception as e:
            print(f'    [image_gen] Error: {e} (attempt {attempt + 1})')
    return None

def _build_shot_prompt(base_prompt: str, shot: Dict) -> str:
    """Append shot-type framing to the base visual prompt."""
    return f"{base_prompt}, {shot['suffix']}"

class StoryboardTool(ToolKernel):
    """
    MCP tool: generate multiple cinematic images per scene.
    Returns list of PNG paths (wide / mid / closeup / atmosphere).
    """
    name = 'image_generation'
    description = 'Generates multiple cinematic images per scene (wide/mid/closeup) using Pollinations AI FLUX model. Falls back to PIL gradient.'

    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_inputs(['scene_id', 'visual_prompt', 'output_dir'], kwargs)
        target_paths = generate_story_frames(scene_id=kwargs['scene_id'], visual_prompt=kwargs['visual_prompt'], negative_prompt=kwargs.get('negative_prompt', ''), tone=kwargs.get('tone', 'neutral'), setting=kwargs.get('setting', ''), num_images=kwargs.get('num_images', 3), output_dir=kwargs['output_dir'], width=kwargs.get('width', 1280), height=kwargs.get('height', 720), use_pollinations=kwargs.get('use_pollinations', True))
        return {'success': True, 'scene_id': kwargs['scene_id'], 'image_paths': target_paths, 'count': len(target_paths)}
try:
    from PIL import Image, ImageDraw, ImageEnhance
    import numpy as np
    PIL_OK = True
except ImportError:
    PIL_OK = False
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
if __name__ == '__main__':
    tool = StoryboardTool()
    outcome = tool.execute(scene_id='scene_001', visual_prompt='3D Pixar-style CGI, A desolate dusty Martian landscape with red rocks and Olympus Mons in the distance, astronaut Ava in silver suit', negative_prompt='blurry, low quality, watermark, deformed', tone='mysterious', setting='Mars surface', num_images=3, output_dir='/tmp/phase3_test_images', use_pollinations=True)
    print(outcome)
