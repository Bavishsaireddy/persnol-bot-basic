# nodes/persist_node.py
# Terminal node — saves both conversation turns to SQLite and seals metadata.

import logging
from datetime import datetime
from time import perf_counter

from config_loader import CONFIG
from nodes.state import AgentState
from memory import save_turn

logger = logging.getLogger(__name__)

_persona = CONFIG["persona"]


def persist_node(state: AgentState) -> AgentState:
    """
    1. Writes user message + assistant response to SQLite memory.
    2. Stamps final timing and timestamp into metadata.
    """
    session_id = state["session_id"]
    user_msg   = state.get("user_message", "")
    response   = state.get("response", "")

    t0 = perf_counter()

    if user_msg and response:
        save_turn(session_id, "user",      user_msg)
        save_turn(session_id, "assistant", response)

    elapsed = round(perf_counter() - t0, 3)
    meta    = state.get("metadata") or {}

    logger.debug(
        "persist_node | session=%s | route=%s | %.3fs",
        session_id, meta.get("intake_route", "?"), elapsed,
    )

    return {
        **state,
        "metadata": {
            **meta,
            "persist_seconds": elapsed,
            "finalized_at":    datetime.utcnow().isoformat(),
        },
    }
