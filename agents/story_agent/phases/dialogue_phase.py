from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from shared.schemas.pipeline_state import Phase1State
from shared.schemas.scripts import ScriptOutput
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agents.story_agent.helpers.dialogue_checks import infer_emotion_profile, compose_visual_prompt, check_duration_budget
from agents.story_agent.helpers.plot_checks import estimate_story_duration
from agents.story_agent.llm_runtime import resolve_llm, cycle_tool_execution
from typing import Any, Dict, List
import json
import logging
logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = "You are a professional screenplay writer specialising in animated short films.\n\nGiven a story structure and character roster, write a complete scene-by-scene script with:\n- Natural, character-appropriate dialogue (2–5 lines per scene)\n- Precise timing_offset_seconds for each line (cumulative from scene start)\n- Detailed visual_prompt for image generation (incorporating characters + setting + art style)\n- camera_movement, transition_in, transition_out, background_music_mood per scene\n- estimated_duration_seconds consistent with the story's estimates\n\nAvailable tools (use each at least once):\n• build_visual_prompt  — call for each scene to build a production-quality image prompt\n• analyze_emotions     — call for each dialogue line to get the TTS emotion tag\n• validate_duration    — call per scene to check dialogue fits the target duration\n• estimate_duration    — call to verify overall pacing\n\nImportant:\n- visual_prompt must embed the global_art_style from the character roster.\n- All scene_key values in ScriptOutput.scenes must exactly match scene_key values in StoryOutput.\n- All character_ids in dialogue lines must exactly match character_ids in CharacterRoster.\n- line_ids use format 'line_001', 'line_002', etc. (reset per scene).\n"

def dialogue_node(snapshot: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates ScriptOutput from story + character roster."""
    if not snapshot.get('story_output') or not snapshot.get('character_roster'):
        return {'script_output': None, 'errors': ['script_agent: story_output or character_roster is missing — cannot write script.'], 'tools_log': []}
    story = snapshot['story_output']
    roster = snapshot['character_roster']
    logger.info("Script agent: writing script for '%s'", story.get('headline', ''))
    tools = [compose_visual_prompt, infer_emotion_profile, check_duration_budget, estimate_story_duration]
    tools_log: List[Dict[str, Any]] = []
    context = json.dumps({'story': story, 'characters': roster}, indent=2)
    messages: List[Any] = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=f'Write the complete script for this story and character roster:\n\n{context}\n\nFor EACH scene:\n1. Call build_visual_prompt → use the result as visual_prompt.\n2. Write 2–5 dialogue lines.\n3. Call analyze_emotions for each line → use the result as the emotion tag.\n4. Call validate_duration → adjust if dialogue is too long.\n\nAfter processing all scenes, I will ask for the final structured output.')]
    try:
        llm = resolve_llm(temperature=0.7)
        messages = cycle_tool_execution(llm, tools, messages, max_iterations=10)
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append({'node': 'script_agent', 'tool': tc['name'], 'args': tc['args']})
        structured_llm = resolve_llm(temperature=0).with_structured_output(ScriptOutput)
        script: ScriptOutput = structured_llm.invoke(messages + [HumanMessage(content="Now produce the final ScriptOutput JSON. Include one SceneScript for EVERY scene in the story. Use scene_key (not scene_id) to match the story exactly — e.g. 'scene_001'. character_ids in dialogue must match the roster exactly. line_ids use format 'line_001', 'line_002', … (reset per scene). The dialogue text field is called copy_text.")])
        total_lines = sum((len(s.dialogue) for s in script.scenes))
        logger.info('Script agent done: %d scenes, %d total dialogue lines', len(script.scenes), total_lines)
        return {'script_output': script.model_dump(), 'tools_log': tools_log, 'errors': []}
    except Exception as exc:
        logger.error('Script agent failed: %s', exc)
        return {'script_output': None, 'tools_log': tools_log, 'errors': [f'script_agent error: {exc}']}
