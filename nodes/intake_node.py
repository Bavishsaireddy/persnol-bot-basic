# nodes/intake_node.py
# Entry point of the pipeline. Reads the incoming message and decides
# which route to take (direct / retrieve / profile).
# All routing rules come from config.yaml — no hardcoding.

import logging
from nodes.state import AgentState
from config_loader import CONFIG

logger = logging.getLogger(__name__)

_routing  = CONFIG["graph"]["routing"]
_github   = CONFIG.get("github",   {})
_linkedin = CONFIG.get("linkedin", {})


def _profile_keywords() -> list[str]:
    """Combines profile keywords from github + linkedin config sections."""
    kws: list[str] = []
    if _github.get("enabled", False):
        kws += [k.lower() for k in _github.get("profile_keywords", [])]
    if _linkedin.get("enabled", False):
        kws += [k.lower() for k in _linkedin.get("profile_keywords", [])]
    return list(dict.fromkeys(kws))  # deduplicate, preserve order


_PROFILE_KEYWORDS = _profile_keywords()


def intake_node(state: AgentState) -> AgentState:
    """
    Analyses the incoming message and sets state["route"].

    Priority (all rules from config.yaml):
      1. Message contains a profile keyword  → "profile"
      2. Message contains a tool keyword     → "retrieve"
      3. Short message, no keywords          → "direct"
      4. Fallback                            → default_route from config
    """
    msg      = (state.get("user_message") or "").lower()
    max_len  = _routing["simple_msg_max_chars"]
    keywords = [kw.lower() for kw in _routing.get("tool_keywords", [])]
    default  = _routing.get("default_route", "direct")

    has_profile = any(kw in msg for kw in _PROFILE_KEYWORDS)
    has_keyword = any(kw in msg for kw in keywords)

    if has_profile:
        route = "profile"
    elif has_keyword:
        route = "retrieve"
    elif len(msg) <= max_len:
        route = "direct"
    else:
        route = default

    logger.debug(
        "intake_node | session=%s | len=%d | profile=%s | keyword=%s → route=%s",
        state.get("session_id"), len(msg), has_profile, has_keyword, route,
    )

    return {
        **state,
        "route":    route,
        "metadata": {**(state.get("metadata") or {}), "intake_route": route},
    }
