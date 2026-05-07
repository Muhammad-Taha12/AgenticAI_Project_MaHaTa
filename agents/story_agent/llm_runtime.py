"""LLM runtime — local Ollama backend"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from mcp.base_tool import ToolKernel
from langchain_ollama import ChatOllama
from typing import Any, List
import json
import logging

logger = logging.getLogger(__name__)


def resolve_llm(temperature: float = 0.7) -> ChatOllama:
    """Return a configured ChatOllama instance.

    Reads LOCAL_MODEL (default: llama3.2) and OLLAMA_BASE_URL
    (default: http://localhost:11434) from the environment.
    """
    import os

    model = os.environ.get("LOCAL_MODEL", "llama3.2")
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(model=model, temperature=temperature, base_url=base_url)


def cycle_tool_execution(
    llm: ChatOllama,
    tools: List[ToolKernel],
    messages: List[Any],
    max_iterations: int = 6,
) -> List[Any]:
    """Run an LLM + tool-calling loop until the model stops calling tools
    or max_iterations is reached.

    Args:
        llm:            A ChatOllama instance (no tools pre-bound).
        tools:          List of LangChain tool objects to make available.
        messages:       Initial message list (system + human).
        max_iterations: Safety cap on tool-call rounds.

    Returns:
        Updated messages list including all AI responses and ToolMessages.
    """
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    for iteration in range(max_iterations):
        response: AIMessage = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            logger.debug("Tool loop finished after %d iteration(s).", iteration + 1)
            break

        for tc in response.tool_calls:
            tool_name: str = tc["name"]
            tool_args: dict = tc["args"]
            logger.debug("Tool call: %s(%s)", tool_name, tool_args)
            try:
                raw_result = tool_map[tool_name].invoke(tool_args)
                result_str = (
                    json.dumps(raw_result)
                    if isinstance(raw_result, dict)
                    else str(raw_result)
                )
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})
                logger.warning("Tool '%s' raised: %s", tool_name, exc)

            messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"])
            )

    return messages
