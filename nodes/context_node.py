# nodes/context_node.py
# Loads conversation history from SQLite and builds the memory context
# that bchat_node will inject into the system prompt.
# Also decides whether retrieval_node should run.
# All rules come from config.yaml — no hardcoding.

import logging
from time import perf_counter

from config_loader import CONFIG
from nodes.state import AgentState
from memory import load_history, build_memory_context

logger = logging.getLogger(__name__)

_tools_cfg = CONFIG["graph"]["tools"]
_routing   = CONFIG["graph"]["routing"]


def context_node(state: AgentState) -> AgentState:
    """
    1. Loads SQLite history → builds memory_context string.
    2. Sets needs_tools based on config keywords + tools.enabled flag.
    """
    session_id = state["session_id"]
    t0 = perf_counter()

    history        = load_history(session_id)
    memory_context = build_memory_context(history)
    turn_messages  = [{"role": m["role"], "content": m["content"]} for m in history]

    if not _tools_cfg.get("enabled", True):
        needs_tools = False
        reason      = "tools_disabled_in_config"
    else:
        msg         = (state.get("user_message") or "").lower()
        keywords    = [kw.lower() for kw in _routing.get("tool_keywords", [])]
        needs_tools = any(kw in msg for kw in keywords)
        reason      = "keyword_match" if needs_tools else "no_keyword"

    elapsed = round(perf_counter() - t0, 3)
    logger.debug(
        "context_node | session=%s | history=%d | needs_tools=%s | reason=%s | %.3fs",
        session_id, len(history), needs_tools, reason, elapsed,
    )

    return {
        **state,
        "memory_context": memory_context,
        "messages":       turn_messages,
        "needs_tools":    needs_tools,
        "metadata": {
            **(state.get("metadata") or {}),
            "context_history_turns": len(history),
            "context_needs_tools":   needs_tools,
            "context_reason":        reason,
            "context_seconds":       elapsed,
        },
    }
