"""Reworked module for contracts.schemas.handoffs.py"""
from __future__ import annotations
from shared.schemas.characters import VoiceConfig
from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional, Any

class SceneVisualSpec(BaseModel):
    model_config = {"populate_by_name": True}

    scene_key: str = Field(default='')
    visual_prompt: str
    negative_prompt: str
    camera_movement: str
    transition_in: str
    transition_out: str
    duration_s: int = Field(default=30)
    character_ids_in_scene: List[str] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # scene_id -> scene_key
            if not data.get('scene_key') and data.get('scene_id'):
                data['scene_key'] = data['scene_id']
            # duration_seconds -> duration_s
            if 'duration_s' not in data and 'duration_seconds' in data:
                data['duration_s'] = data['duration_seconds']
        return data

class Phase3VideoHandoff(BaseModel):
    scenes: List[SceneVisualSpec] = Field(description='Ordered visual specification for every scene')
    character_appearance_prompts: Dict[str, str] = Field(description='character_id → art_style_prompt for consistent character rendering')
    global_art_style: str = Field(description='Art style directive applied uniformly to all scene visuals')

class AudioSegment(BaseModel):
    model_config = {"populate_by_name": True}

    segment_id: str = Field(description="Unique segment key, e.g. 'scene_001_line_001'")
    scene_key: str = Field(default='')
    character_id: str
    line_id: str
    copy_text: str = Field(default='', description='Text to synthesise')
    voice_config: VoiceConfig
    timing_offset_seconds: float = Field(ge=0.0, default=0.0)
    duration_hint_seconds: float = Field(ge=0.1, default=3.0)
    emotion: str = Field(default='neutral')

    @model_validator(mode='before')
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # scene_id -> scene_key
            if not data.get('scene_key') and data.get('scene_id'):
                data['scene_key'] = data['scene_id']
            # text -> copy_text
            if not data.get('copy_text') and data.get('text'):
                data['copy_text'] = data['text']
        return data

class Phase2AudioHandoff(BaseModel):
    voice_configs: Dict[str, VoiceConfig] = Field(description='character_id → VoiceConfig map for fast lookup by the audio agent')
    audio_segments: List[AudioSegment] = Field(description='All audio segments ordered by scene then by timing offset')
    music_moods: Dict[str, str] = Field(description='scene_key → BGM mood keyword map')
    total_segments: int = Field(default=0)
