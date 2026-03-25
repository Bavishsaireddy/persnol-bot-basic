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
        needs_tools   = False
        needs_profile = False
        needs_resume  = False
        reason        = "tools_disabled_in_config"
    else:
        # Trust the routing decision already made by intake_node
        route         = state.get("route")
        needs_tools   = route == "retrieve"
        needs_profile = route == "profile"
        needs_resume  = route == "resume"
        reason        = f"intake_route_{route or 'direct'}"

    elapsed = round(perf_counter() - t0, 3)
    logger.debug(
        "context_node | session=%s | history=%d | needs_tools=%s | needs_profile=%s | needs_resume=%s | reason=%s | %.3fs",
        session_id, len(history), needs_tools, needs_profile, needs_resume, reason, elapsed,
    )

    return {
        **state,
        "memory_context": memory_context,
        "messages":       turn_messages,
        "needs_tools":    needs_tools,
        "needs_profile":  needs_profile,
        "needs_resume":   needs_resume,
        "metadata": {
            **(state.get("metadata") or {}),
            "context_history_turns":  len(history),
            "context_needs_tools":    needs_tools,
            "context_needs_profile":  needs_profile,
            "context_needs_resume":   needs_resume,
            "context_reason":         reason,
            "context_seconds":        elapsed,
        },
    }
