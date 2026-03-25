# nodes/persist_node.py
# Terminal node — saves both conversation turns to Redis (or SQLite fallback) and seals metadata.

import logging
from datetime import datetime
from time import perf_counter

from config_loader import CONFIG
from nodes.state import AgentState
import re

from memory import save_turn, save_lead

logger = logging.getLogger(__name__)

_persona = CONFIG["persona"]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _extract_lead_data(text: str) -> dict:
    """Extract email / phone from any user message."""
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    data: dict = {}
    if emails:
        data["email"] = emails[0]
    if phones:
        data["phone"] = phones[0]
    return data


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

    # Save any contact info the visitor provided (from resume_node or direct message)
    lead_data = state.get("lead_data") or {}
    if not lead_data and user_msg:
        lead_data = _extract_lead_data(user_msg)
    if lead_data:
        save_lead(session_id, lead_data)

    elapsed = round(perf_counter() - t0, 3)
    meta    = state.get("metadata") or {}

    logger.debug(
        "persist_node | session=%s | route=%s | lead_captured=%s | %.3fs",
        session_id, meta.get("intake_route", "?"), bool(lead_data), elapsed,
    )

    return {
        **state,
        "lead_data": lead_data,
        "metadata": {
            **meta,
            "persist_seconds":        elapsed,
            "persist_lead_captured":  bool(lead_data),
            "finalized_at":           datetime.utcnow().isoformat(),
        },
    }
