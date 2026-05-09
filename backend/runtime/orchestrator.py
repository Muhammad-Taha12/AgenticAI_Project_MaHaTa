from __future__ import annotations
from backend.runtime.ledger import RunLedger, PROJECT_ROOT
from pathlib import Path
from typing import Any, Dict
import asyncio
import json
import logging
import os
logger = logging.getLogger(__name__)
OUTPUTS_ROOT = PROJECT_ROOT / 'data' / 'outputs'

def read_json_blob(target_path: str | None) -> Any:
    if not target_path:
        return None
    slot = Path(target_path)
    if not slot.exists():
        return None
    with slot.open(encoding='utf-8') as fh:
        return json.load(fh)

class FlowRunner:

    def __init__(self, store: RunLedger):
        self.store = store

    async def run_pipeline(self, task_id: str, starting_stage: int=1) -> None:
        try:
            snapshot = self.store.get(task_id)
            if snapshot is None:
                raise KeyError(f'Unknown job_id: {task_id}')
            for stage_index in range(starting_stage, 4):
                await asyncio.to_thread(self._execute_phase, task_id, stage_index)
            self.store.update(task_id, status='completed', current_phase=None, progress=100, message='Pipeline completed')
        except Exception as exc:
            logger.exception('Pipeline job %s failed', task_id)
            self.store.update(task_id, status='failed', current_phase=None, message=str(exc), errors=[str(exc)])

    def _execute_phase(self, task_id: str, stage_index: int) -> None:
        stage_name = {1: 'Story', 2: 'Audio', 3: 'Video'}[stage_index]
        self.store.update(task_id, status='running', current_phase=stage_index, phases={str(stage_index): 'running'}, progress={1: 10, 2: 45, 3: 75}[stage_index], message=f'Phase {stage_index}: {stage_name} running')
        logger.info('Job %s: starting phase %s', task_id, stage_index)
        if stage_index == 1:
            outputs = self._run_phase1(task_id)
        elif stage_index == 2:
            outputs = self._run_phase2(task_id)
        elif stage_index == 3:
            outputs = self._run_phase3(task_id)
        else:
            raise ValueError(f'Unsupported phase: {stage_index}')
        self.store.update(task_id, phases={str(stage_index): 'completed'}, outputs=outputs, progress={1: 35, 2: 70, 3: 95}[stage_index], message=f'Phase {stage_index}: {stage_name} completed')
        logger.info('Job %s: completed phase %s', task_id, stage_index)

    def _run_phase1(self, task_id: str) -> Dict[str, Any]:
        from agents.story_agent.graph import build_phase_one_graph
        from agents.story_agent.handoff_export import persist_phase_one_outputs
        snapshot = self.store.get(task_id)
        if snapshot is None:
            raise KeyError(f'Unknown job_id: {task_id}')
        job_dir = self.store.job_dir(task_id)
        phase_one_dir = job_dir / 'phase1'
        phase_one_dir.mkdir(parents=True, exist_ok=True)
        graph = build_phase_one_graph()
        request_body = {'user_prompt': snapshot['prompt'], 'story_output': None, 'character_roster': None, 'script_output': None, 'errors': [], 'tools_log': [], 'retry_counts': {}}
        outcome = graph.invoke(request_body)
        issues = outcome.get('errors', [])
        if issues or not all((outcome.get(key) for key in ('story_output', 'character_roster', 'script_output'))):
            raise RuntimeError('; '.join(issues) or 'Phase 1 did not produce all outputs')
        artifact_paths = persist_phase_one_outputs(outcome['story_output'], outcome['character_roster'], outcome['script_output'], outcome.get('tools_log', []), issues, destination_dir=phase_one_dir)
        return {'phase1': {'output_dir': str(phase_one_dir), 'artifacts': artifact_paths, 'story': outcome['story_output'], 'characters': outcome['character_roster'], 'script': outcome['script_output']}}

    def _run_phase2(self, task_id: str) -> Dict[str, Any]:
        from agents.audio_agent.agent import execute_phase_two as phase2_agent
        snapshot = self.store.get(task_id)
        if snapshot is None:
            raise KeyError(f'Unknown job_id: {task_id}')
        handoff = snapshot.get('outputs', {}).get('phase1', {}).get('artifacts', {}).get('phase2_audio_handoff')
        if not handoff:
            raise RuntimeError('Phase 2 requires phase2_audio_handoff from Phase 1')
        phase_two_dir = self.store.job_dir(task_id) / 'phase2'
        outcome = phase2_agent(handoff, destination_dir=phase_two_dir)
        if not outcome.get('success'):
            raise RuntimeError('; '.join(outcome.get('errors', ['Phase 2 failed'])))
        return {'phase2': {'output_dir': str(phase_two_dir), 'timing_manifest': outcome['timing_manifest'], 'full_audio': outcome['full_audio'], 'summary': str(phase_two_dir / 'summary.json'), 'scene_count': outcome['scene_count'], 'segment_count': outcome['segment_count']}}

    def _run_phase3(self, task_id: str) -> Dict[str, Any]:
        from agents.video_agent.agent import RenderCoordinator
        snapshot = self.store.get(task_id)
        if snapshot is None:
            raise KeyError(f'Unknown job_id: {task_id}')
        outputs = snapshot.get('outputs', {})
        phase_one_dir = outputs.get('phase1', {}).get('output_dir')
        phase_two_dir = outputs.get('phase2', {}).get('output_dir')
        if not phase_one_dir or not phase_two_dir:
            raise RuntimeError('Phase 3 requires Phase 1 and Phase 2 outputs')
        phase_three_dir = self.store.job_dir(task_id) / 'phase3'
        agent = RenderCoordinator(phase_one_run_dir=phase_one_dir, phase_two_run_dir=phase_two_dir, destination_dir=str(phase_three_dir), burn_subs=os.environ.get('BURN_SUBTITLES', 'true').lower() != 'false', use_ollama=os.environ.get('USE_OLLAMA', 'false').lower() == 'true', images_per_scene=int(os.environ.get('IMAGES_PER_SCENE', '3')))
        outcome = agent.run()
        return {'phase3': {'output_dir': str(phase_three_dir), 'final_video': outcome['final_video'], 'subtitles': outcome.get('subtitles'), 'summary': str(phase_three_dir / 'summary.json'), 'scene_clips': outcome.get('scene_clips', [])}}