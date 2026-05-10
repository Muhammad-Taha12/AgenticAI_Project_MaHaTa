from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from shared.schemas.characters import CharacterRoster
from shared.schemas.pipeline_state import Phase1State
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agents.story_agent.helpers.cast_checks import check_cast_consistency
from agents.story_agent.llm_runtime import resolve_llm, cycle_tool_execution
from typing import Any, Dict, List
import json
import logging
logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = 'You are a character designer and casting director for animated films.\n\nGiven a story structure, create a complete character roster with:\n- Unique character_ids (char_001, char_002, …)\n- Rich visual appearance descriptions suitable for AI image generation\n- Voice configurations for TTS synthesis (gender, age_range, tone, speed, emotion_baseline, accent, tts_style_tags)\n- Consistent personalities that serve the narrative\n- A global_art_style that will be applied uniformly to ALL scene visuals\n\nGuidelines:\n- The protagonist (char_001) must appear in most scenes.\n- Voice configs must be distinct enough for listeners to tell characters apart.\n- art_style_prompt inside each character\'s appearance should be a self-contained\n  fragment that can be appended to any scene prompt (e.g. "young woman with red curly hair,\n  wearing a blue astronaut suit, determined expression").\n- global_art_style examples: "Studio Ghibli-style watercolour anime",\n  "3D Pixar-style CGI", "2D flat-design cartoon", "hand-drawn ink-wash illustration".\n\nAvailable tool:\n• check_consistency — call this with your character_ids and scene-character map to\n  verify every character appears in at least one scene and no scene references an\n  undefined character.\n'

def cast_node(snapshot: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates CharacterRoster from state['story_output']."""
    if not snapshot.get('story_output'):
        return {'character_roster': None, 'errors': ['character_agent: story_output is missing — cannot generate characters.'], 'tools_log': []}
    story = snapshot['story_output']
    scene_keys = [s['scene_key'] for s in story.get('scenes', [])]
    logger.info("Character agent: designing roster for story '%s'", story.get('headline', ''))
    tools = [check_cast_consistency]
    tools_log: List[Dict[str, Any]] = []
    story_context = json.dumps(story, indent=2)
    messages: List[Any] = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=f'Design the full character roster for this story:\n\n{story_context}\n\nScene IDs present: {scene_keys}\n\nFor each character specify which scene_ids they appear in. Then call check_consistency to validate your assignments.')]
    try:
        llm = resolve_llm(temperature=0.7)
        messages = cycle_tool_execution(llm, tools, messages)
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append({'node': 'character_agent', 'tool': tc['name'], 'args': tc['args']})
        structured_llm = resolve_llm(temperature=0).with_structured_output(CharacterRoster)
        roster: CharacterRoster = structured_llm.invoke(messages + [HumanMessage(content="Now produce the final CharacterRoster JSON. Ensure character_ids are 'char_001', 'char_002', etc. Every scene_key in scenes_appearing_in must match a scene_key from the story exactly (use scene_key values like 'scene_001'). Include global_art_style.")])
        logger.info("Character agent done: %d characters, art style: '%s'", len(roster.characters), roster.global_art_style)
        return {'character_roster': roster.model_dump(), 'tools_log': tools_log, 'errors': []}
    except Exception as exc:
        logger.error('Character agent failed: %s', exc)
        return {'character_roster': None, 'tools_log': tools_log, 'errors': [f'character_agent error: {exc}']}
