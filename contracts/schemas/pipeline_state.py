"""Reworked module for contracts.schemas.pipeline_state.py"""
from __future__ import annotations
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator

class Phase1State(TypedDict):
    user_prompt: str
    story_output: Optional[Dict[str, Any]]
    character_roster: Optional[Dict[str, Any]]
    script_output: Optional[Dict[str, Any]]
    issues: Annotated[List[str], operator.add]
    tools_log: Annotated[List[Dict[str, Any]], operator.add]
    retry_counts: Dict[str, int]
