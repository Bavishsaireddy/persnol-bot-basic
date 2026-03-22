# nodes/bchat_node.py
# Single LLM call node — unified chat entry point for the Bavish agent.
# Works for both simple and tool-enriched paths:
#   - If state["code_context"] is present  → uses it (came from data_tool_node)
#   - If state["memory_context"] is present → uses it (loaded by orchestration_node)
# All LLM parameters come from config.yaml → llm.

import logging
import os
from time import perf_counter

import anthropic

from config_loader import CONFIG
from nodes.state import AgentState
from prompt import build_system_prompt

logger = logging.getLogger(__name__)

_llm = CONFIG["llm"]

_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def bchat_node(state: AgentState) -> AgentState:
    """
    Unified LLM call. Accepts whatever context is already in state and
    calls Claude once to produce the final response.
    """
    session_id   = state["session_id"]
    user_msg     = state["user_message"]
    memory_ctx   = state.get("memory_context",  "")
    code_ctx     = state.get("code_context",    "")
    profile_ctx  = state.get("profile_context", "")
    history_msgs = state.get("messages",         [])

    t0 = perf_counter()

    system_prompt = build_system_prompt(
        memory_context=memory_ctx,
        code_context=code_ctx,
        profile_context=profile_ctx,
    )

    messages = list(history_msgs)
    messages.append({"role": "user", "content": user_msg})

    response = _claude.messages.create(
        model=_llm["model"],
        max_tokens=_llm["max_tokens"],
        temperature=_llm["temperature"],
        system=system_prompt,
        messages=messages,
    )

    text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text]
    if not text_blocks:
        logger.error(
            "bchat_node | empty content from Claude | session=%s | stop_reason=%s",
            session_id, response.stop_reason,
        )
        raise RuntimeError(
            f"The model returned an empty response (stop_reason={response.stop_reason!r}). "
            "Please try again."
        )
    answer  = text_blocks[0]
    elapsed = round(perf_counter() - t0, 3)

    logger.debug(
        "bchat_node | session=%s | with_tools=%s | %.3fs | tokens=%s",
        session_id, bool(code_ctx), elapsed, response.usage,
    )

    return {
        **state,
        "response": answer,
        "metadata": {
            **(state.get("metadata") or {}),
            "bchat_node_seconds":    elapsed,
            "bchat_node_used_tools": bool(code_ctx),
            "bchat_node_used_profile": bool(profile_ctx),
            "bchat_node_tokens":     dict(response.usage),
        },
    }
