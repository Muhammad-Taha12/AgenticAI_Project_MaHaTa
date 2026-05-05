"""Reworked module for narrative.storycraft.helpers.dialogue_tools.py"""
from langchain_core.tools import tool
from typing import List

@tool
def infer_emotion_profile(dialogue_text: str, scene_tone: str, character_role: str) -> dict:
    """Suggests the most appropriate TTS emotion tag for a dialogue line.

    Args:
        dialogue_text: The line of dialogue to analyse.
        scene_tone: Dominant tone of the containing scene.
        character_role: The character's narrative role (protagonist, antagonist, etc.).

    Returns:
        dict with suggested_emotion, intensity, confidence, alternatives.
    """
    text_lower = dialogue_text.lower()
    keyword_emotions = {'excited': ['amazing', 'wonderful', 'incredible', 'fantastic', 'yes!', 'great', 'awesome'], 'sad': ['sorry', 'lost', 'miss', 'goodbye', 'never', 'alone', 'tears', 'cry'], 'angry': ['how dare', 'never', 'stop it', 'enough', 'furious', 'unacceptable', 'no!'], 'fearful': ['afraid', 'scared', 'danger', 'run', 'help me', 'please', 'terror'], 'curious': ['what', 'why', 'how', 'wonder', 'interesting', 'tell me', 'explain'], 'calm': ['alright', 'okay', 'fine', 'understand', 'trust', 'together', 'will be'], 'determined': ['must', 'have to', "won't give up", 'promise', 'fight', 'i will']}
    scores = {emotion: sum((1 for kw in keywords if kw in text_lower)) for emotion, keywords in keyword_emotions.items()}
    best_emotion = max(scores, key=scores.get) if any(scores.values()) else None
    tone_defaults = {'tense': 'fearful', 'heartwarming': 'calm', 'mysterious': 'curious', 'epic': 'determined', 'sad': 'sad', 'excited': 'excited', 'peaceful': 'calm', 'hopeful': 'calm'}
    if not best_emotion or scores.get(best_emotion, 0) == 0:
        best_emotion = tone_defaults.get(scene_tone.lower(), 'neutral')
        confidence = 'inferred_from_scene_tone'
    else:
        confidence = 'keyword_match'
    score_val = scores.get(best_emotion, 0)
    intensity = 'high' if score_val >= 2 else 'medium' if score_val == 1 else 'low'
    alternatives = [k for k, v in sorted(scores.items(), key=lambda x: -x[1]) if k != best_emotion][:3]
    return {'suggested_emotion': best_emotion, 'intensity': intensity, 'confidence': confidence, 'alternatives': alternatives}

@tool
def compose_visual_prompt(scene_setting: str, scene_tone: str, characters_present: List[str], character_descriptions: List[str], art_style: str='cinematic animation') -> dict:
    """Builds an enhanced image-generation prompt for a scene.

    Args:
        scene_setting: Where and when the scene takes place.
        scene_tone: Emotional tone of the scene (e.g. 'tense', 'heartwarming').
        characters_present: Names of characters visible in the scene.
        character_descriptions: Matching visual descriptions for each character.
        art_style: Overall art style directive (default 'cinematic animation').

    Returns:
        dict with visual_prompt, negative_prompt, lighting_note.
    """
    tone_lighting_map = {'tense': 'dramatic shadows, high-contrast side-lighting', 'heartwarming': 'warm golden-hour glow, soft bokeh', 'mysterious': 'cool blue-green fog, dim atmospheric light', 'epic': 'sweeping panoramic vista, dramatic storm-lit sky', 'peaceful': 'soft diffused daylight, pastel palette', 'sad': 'overcast sky, desaturated muted tones', 'excited': 'bright vibrant colours, dynamic Dutch-angle', 'hopeful': 'rays of sunlight breaking through clouds'}
    lighting = tone_lighting_map.get(scene_tone.lower(), 'natural cinematic lighting')
    char_fragment = ''
    if characters_present and character_descriptions:
        pairs = [f'{name} ({desc})' for name, desc in zip(characters_present, character_descriptions)]
        char_fragment = ', '.join(pairs) + ', '
    brief = f'{art_style}, {scene_setting}, {char_fragment}{lighting}, highly detailed, 4K resolution, professional animation studio quality, wide establishing shot'
    negative = 'blurry, low quality, distorted faces, watermark, text overlay, extra limbs, deformed, ugly, oversaturated, duplicate characters'
    return {'visual_prompt': brief, 'negative_prompt': negative, 'lighting_note': lighting, 'style_applied': art_style}

@tool
def check_duration_budget(dialogue_lines: List[str], target_duration_seconds: int) -> dict:
    """Validates that dialogue lines will fit within the target scene duration.

    Args:
        dialogue_lines: List of dialogue text strings for the scene.
        target_duration_seconds: Intended scene length in seconds.

    Returns:
        dict with fits (bool), estimated_seconds, total_words, suggestion.
    """
    words_per_minute = 130
    total_words = sum((len(line.split()) for line in dialogue_lines))
    speech_seconds = total_words / words_per_minute * 60
    pause_seconds = len(dialogue_lines) * 1.5
    estimated_seconds = round(speech_seconds + pause_seconds, 1)
    fits = estimated_seconds <= target_duration_seconds
    over_by = round(estimated_seconds - target_duration_seconds, 1)
    return {'fits': fits, 'estimated_seconds': estimated_seconds, 'target_seconds': target_duration_seconds, 'total_words': total_words, 'suggestion': f'Dialogue fits comfortably ({estimated_seconds}s / {target_duration_seconds}s).' if fits else f'Dialogue exceeds target by {over_by}s. Consider trimming {len(dialogue_lines)} lines or increasing scene duration.'}
