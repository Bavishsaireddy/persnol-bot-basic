# nodes/context_node.py
# Loads conversation history from Redis (or SQLite fallback) and builds
# the memory context that bchat_node will inject into the system prompt.
# Routing decision is read from state["route"] set by intake_node.
# All rules come from config.yaml — no hardcoding.

import logging
from time import perf_counter

from config_loader import CONFIG
from nodes.state import AgentState
from memory import load_history, build_memory_context

logger = logging.getLogger(__name__)

_tools_cfg = CONFIG["graph"]["tools"]


def context_node(state: AgentState) -> AgentState:
    """
    1. Loads Redis history → builds memory_context string.
    2. Sets needs_tools by reading state["route"] set by intake_node — no
       duplicate keyword scan here.
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
        # Trust the routing decision already made by intake_node
        needs_tools = state.get("route") == "retrieve"
        reason      = "intake_route_retrieve" if needs_tools else "intake_route_direct"

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
