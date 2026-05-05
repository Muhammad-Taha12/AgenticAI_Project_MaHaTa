"""Reworked module for narrative.storycraft.graph.py"""
from __future__ import annotations
from shared.schemas.pipeline_state import Phase1State
from langgraph.graph import END, StateGraph
from agents.story_agent.phases.cast_phase import cast_node
from agents.story_agent.phases.dialogue_phase import dialogue_node
from agents.story_agent.phases.plot_phase import plot_node
import logging
logger = logging.getLogger(__name__)

def route_plot(snapshot: Phase1State) -> str:
    if snapshot.get('story_output') is None:
        logger.error('Story generation failed — terminating pipeline.')
        return END
    return 'character_agent'

def route_cast(snapshot: Phase1State) -> str:
    if snapshot.get('character_roster') is None:
        logger.error('Character generation failed — terminating pipeline.')
        return END
    return 'script_agent'

def build_phase_one_graph():
    """Builds and compiles the Phase 1 LangGraph StateGraph.

    Returns:
        A compiled LangGraph runnable that accepts a Phase1State dict
        and returns the final Phase1State dict.
    """
    graph = StateGraph(Phase1State)
    graph.add_node('story_agent', plot_node)
    graph.add_node('character_agent', cast_node)
    graph.add_node('script_agent', dialogue_node)
    graph.set_entry_point('story_agent')
    graph.add_conditional_edges('story_agent', route_plot, {'character_agent': 'character_agent', END: END})
    graph.add_conditional_edges('character_agent', route_cast, {'script_agent': 'script_agent', END: END})
    graph.add_edge('script_agent', END)
    return graph.compile()
