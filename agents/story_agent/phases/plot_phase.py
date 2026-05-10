from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from shared.schemas.pipeline_state import Phase1State
from shared.schemas.stories import StoryOutput
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from agents.story_agent.helpers.plot_checks import check_story_arc, estimate_story_duration
from agents.story_agent.llm_runtime import resolve_llm, cycle_tool_execution
from typing import Any, Dict, List
import logging
logger = logging.getLogger(__name__)
_SYSTEM_PROMPT = 'You are a master creative story architect specialising in short animated films.\n\nYour task: transform a user prompt into a detailed story structure for a 2–5 minute animated short.\n\nRequirements:\n- 4–6 distinct scenes with vivid settings and emotional tones\n- A clear narrative arc: intro → rising_action → climax → (falling_action) → resolution\n- Cohesive themes woven throughout\n- Total estimated duration 90–300 seconds\n\nAvailable tools:\n• validate_story_arc  — call this to verify your arc before finalising\n• estimate_duration   — call this to sense-check the video length\n\nWorkflow:\n1. Draft your story outline mentally.\n2. Call validate_story_arc with your planned arc positions.\n3. Call estimate_duration with your scene count and expected dialogue density.\n4. Adjust if needed, then wait for the structured-output request.\n'

def plot_node(snapshot: Phase1State) -> Dict[str, Any]:
    """LangGraph node: generates StoryOutput from state['user_prompt']."""
    logger.info("Story agent: generating story for prompt: '%s...'", snapshot['user_prompt'][:60])
    tools = [check_story_arc, estimate_story_duration]
    tools_log: List[Dict[str, Any]] = []
    messages: List[Any] = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=f'''Create a complete story structure for this prompt:\n\n"{snapshot['user_prompt']}"\n\nFirst use validate_story_arc and estimate_duration to validate your plan, then I will ask you for the final structured output.''')]
    try:
        llm = resolve_llm(temperature=0.7)
        messages = cycle_tool_execution(llm, tools, messages)
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_log.append({'node': 'story_agent', 'tool': tc['name'], 'args': tc['args']})
        structured_llm = resolve_llm(temperature=0).with_structured_output(StoryOutput)
        story: StoryOutput = structured_llm.invoke(messages + [HumanMessage(content="Now produce the final structured StoryOutput JSON. Use scene_key like 'scene_001', 'scene_002', etc. (the field is called scene_key, not scene_id). Every scene must have arc_position, tone, setting, summary, and estimated_duration_seconds. The story title field is called 'headline'.")])
        logger.info("Story agent done: '%s' — %d scenes, ~%ds", story.headline, len(story.scenes), story.total_estimated_duration_seconds)
        return {'story_output': story.model_dump(), 'tools_log': tools_log, 'errors': []}
    except Exception as exc:
        logger.error('Story agent failed: %s', exc)
        return {'story_output': None, 'tools_log': tools_log, 'errors': [f'story_agent error: {exc}']}
