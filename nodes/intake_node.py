# nodes/intake_node.py
# Entry point of the pipeline. Reads the incoming message and decides
# whether to fetch knowledge first or go straight to the LLM.
# All routing rules come from config.yaml → graph.routing — no hardcoding.

import logging
from nodes.state import AgentState
from config_loader import CONFIG

logger = logging.getLogger(__name__)

_routing = CONFIG["graph"]["routing"]


def intake_node(state: AgentState) -> AgentState:
    """
    Analyses the incoming message and sets state["route"].

    Rules (all from config.yaml):
      1. Message contains a tool keyword  → "retrieve"
      2. Short message, no keywords       → "direct"
      3. Fallback                         → default_route from config
    """
    msg      = (state.get("user_message") or "").lower()
    max_len  = _routing["simple_msg_max_chars"]
    keywords = [kw.lower() for kw in _routing.get("tool_keywords", [])]
    default  = _routing.get("default_route", "direct")

    has_keyword = any(kw in msg for kw in keywords)

    if has_keyword:
        route = "retrieve"
    elif len(msg) <= max_len:
        route = "direct"
    else:
        route = default

    logger.debug(
        "intake_node | session=%s | len=%d | keyword=%s → route=%s",
        state.get("session_id"), len(msg), has_keyword, route,
    )

    return {
        **state,
        "route":    route,
        "metadata": {**(state.get("metadata") or {}), "intake_route": route},
    }
