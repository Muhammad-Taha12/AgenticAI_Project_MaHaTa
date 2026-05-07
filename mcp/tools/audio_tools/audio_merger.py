"""Reworked module for toolkit.audio.mixer.py"""
from __future__ import annotations
from pathlib import Path
from mcp.tools.audio_tools.tts_tool import SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS
from typing import Dict, Iterable, List
import wave

def mix_audio_layers(layers: Iterable[Dict[str, float | str]], destination: str | Path, duration_s: float | None=None) -> Dict[str, float | str]:
    """Overlay WAV tracks by their start offsets and write a mixed WAV file."""
    layer_items = list(layers)
    if not layer_items:
        duration_s = duration_s or 1.0
        pcm_samples = [0] * int(duration_s * SAMPLE_RATE)
        _write_wav(destination, pcm_samples)
        return {'audio_file': str(destination), 'duration_seconds': duration_s}
    loaded_clips: List[tuple[list[int], int]] = []
    total_samples = int((duration_s or 0) * SAMPLE_RATE)
    for layer in layer_items:
        blob = _read_wav(str(layer['audio_file']))
        start_offset = int(float(layer.get('start_seconds', 0.0)) * SAMPLE_RATE)
        loaded_clips.append((blob, start_offset))
        total_samples = max(total_samples, start_offset + len(blob))
    mix = [0] * max(total_samples, 1)
    for blob, start_offset in loaded_clips:
        for idx, sample in enumerate(blob):
            slot = start_offset + idx
            if slot >= len(mix):
                break
            mix[slot] = max(-32768, min(32767, mix[slot] + sample))
    _write_wav(destination, mix)
    return {'audio_file': str(destination), 'duration_seconds': len(mix) / SAMPLE_RATE}

def concat_audio_files(input_paths: Iterable[str | Path], destination: str | Path) -> Dict[str, float | str]:
    pcm_samples: list[int] = []
    for target_path in input_paths:
        pcm_samples.extend(_read_wav(target_path))
    if not pcm_samples:
        pcm_samples = [0] * SAMPLE_RATE
    _write_wav(destination, pcm_samples)
    return {'audio_file': str(destination), 'duration_seconds': len(pcm_samples) / SAMPLE_RATE}

def _write_wav(target_path: str | Path, pcm_samples: list[int]) -> None:
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target_path), 'wb') as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b''.join((sample.to_bytes(2, 'little', signed=True) for sample in pcm_samples)))

def _read_wav(target_path: str | Path) -> list[int]:
    with wave.open(str(target_path), 'rb') as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        framerate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if sample_width != SAMPLE_WIDTH:
        raise ValueError(f'Unsupported sample width for {target_path}: {sample_width}')
    frame_size = sample_width * channels
    mono: list[int] = []
    for frame_start in range(0, len(raw), frame_size):
        channel_values = [int.from_bytes(raw[frame_start + channel * sample_width:frame_start + (channel + 1) * sample_width], 'little', signed=True) for channel in range(channels)]
        mono.append(int(sum(channel_values) / max(1, len(channel_values))))
    if framerate == SAMPLE_RATE:
        return mono
    if not mono:
        return []
    target_len = max(1, int(len(mono) * SAMPLE_RATE / framerate))
    resampled: list[int] = []
    for index in range(target_len):
        source_offset = index * framerate / SAMPLE_RATE
        left = int(source_offset)
        right = min(left + 1, len(mono) - 1)
        frac = source_offset - left
        value = int(mono[left] * (1 - frac) + mono[right] * frac)
        resampled.append(value)
    return resampled
