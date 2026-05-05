"""Reworked module for narrative.storycraft.runner.py"""
from __future__ import annotations
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional
import json
import logging
import os
import sys
logger = logging.getLogger(__name__)

def execute_phase_one(user_prompt: str, save_artifacts: bool=True, destination_dir: Optional[str]=None) -> Dict[str, Any]:
    """Run the complete Phase 1 pipeline: Story → Character → Script.

    Args:
        user_prompt:    Free-form story idea from the user.
        save_artifacts: Write JSON artifacts to disk (default True).
        output_dir:     Override PHASE1_OUTPUT_DIR env var.

    Returns:
        dict with keys:
          story, characters, script      — dicts from each agent
          phase2_handoff, phase3_handoff — dicts ready for downstream phases
          artifact_paths                 — map of name → file path
          errors                         — list of error strings
          tools_log                      — list of tool-call records
          success                        — bool
    """
    if not user_prompt or not user_prompt.strip():
        return build_error_payload('user_prompt must not be empty.')
    if not os.environ.get('GOOGLE_API_KEY'):
        return build_error_payload('GOOGLE_API_KEY is not set. Add it to your .env file.')
    if destination_dir:
        os.environ['PHASE1_OUTPUT_DIR'] = destination_dir
    logger.info("Phase 1 started — prompt: '%s...'", user_prompt[:80])
    from shared.schemas.pipeline_state import Phase1State
    from agents.story_agent.graph import build_phase_one_graph
    from agents.story_agent.handoff_export import persist_phase_one_outputs
    initial_state: Phase1State = {'user_prompt': user_prompt.strip(), 'story_output': None, 'character_roster': None, 'script_output': None, 'errors': [], 'tools_log': [], 'retry_counts': {}}
    try:
        graph = build_phase_one_graph()
        final_state: Phase1State = graph.invoke(initial_state)
    except Exception as exc:
        logger.error('Pipeline graph execution failed: %s', exc)
        return build_error_payload(f'Pipeline execution error: {exc}')
    story = final_state.get('story_output')
    roster = final_state.get('character_roster')
    script = final_state.get('script_output')
    issues: List[str] = final_state.get('errors', [])
    tools_log: List[Dict[str, Any]] = final_state.get('tools_log', [])
    success = bool(story and roster and script and (not issues))
    artifact_paths: Dict[str, str] = {}
    phase2_handoff: Optional[Dict[str, Any]] = None
    phase3_handoff: Optional[Dict[str, Any]] = None
    if save_artifacts and story and roster and script:
        artifact_paths = persist_phase_one_outputs(story=story, roster=roster, script=script, tools_log=tools_log, errors=issues, run_status='success' if success else 'partial')
        if 'phase2_audio_handoff' in artifact_paths:
            with open(artifact_paths['phase2_audio_handoff'], encoding='utf-8') as fh:
                phase2_handoff = json.load(fh)
        if 'phase3_video_handoff' in artifact_paths:
            with open(artifact_paths['phase3_video_handoff'], encoding='utf-8') as fh:
                phase3_handoff = json.load(fh)
    if success:
        logger.info("Phase 1 complete — story: '%s', %d scenes, %d characters, %d dialogue lines", story.get('title', 'Untitled'), len(story.get('scenes', [])), len(roster.get('characters', [])), sum((len(s.get('dialogue', [])) for s in script.get('scenes', []))))
    else:
        logger.warning('Phase 1 finished with errors: %s', issues)
    return {'story': story, 'characters': roster, 'script': script, 'phase2_handoff': phase2_handoff, 'phase3_handoff': phase3_handoff, 'artifact_paths': artifact_paths, 'errors': issues, 'tools_log': tools_log, 'success': success}

def build_error_payload(status_note: str) -> Dict[str, Any]:
    logger.error(status_note)
    return {'story': None, 'characters': None, 'script': None, 'phase2_handoff': None, 'phase3_handoff': None, 'artifact_paths': {}, 'errors': [status_note], 'tools_log': [], 'success': False}
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
if __name__ == '__main__':
    brief = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'A detective finds a hidden treasure'
    outcome = execute_phase_one(brief)
    if outcome['success']:
        story = outcome['story']
        chars = outcome['characters']
        script = outcome['script']
        print('\n[OK] Phase 1 complete!')
        print(f"  Story  : {story['title']} ({story['genre']})")
        print(f"  Premise: {story['premise']}")
        print(f"  Scenes : {len(story['scenes'])}  (~{story['total_estimated_duration_seconds']}s)")
        print(f"  Cast   : {len(chars['characters'])} characters")
        print(f"  Lines  : {sum((len(s['dialogue']) for s in script['scenes']))} dialogue lines")
        print(f"  Art    : {chars['global_art_style']}")
        print(f"\n  Artifacts → {outcome['artifact_paths'].get('summary', 'N/A')}")
    else:
        print(f"\n[FAILED] Phase 1 failed: {outcome['errors']}", file=sys.stderr)
        sys.exit(1)
