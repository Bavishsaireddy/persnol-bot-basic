# memory.py
# Shared SQLite memory layer — imported by both mcp_server.py and the graph nodes.
# Keeping this separate breaks the circular-import chain between mcp_server ↔ nodes.
# All config comes from config.yaml → memory.

import logging
import sqlite3
from datetime import datetime

from config_loader import CONFIG

logger = logging.getLogger(__name__)

_mem     = CONFIG["memory"]
_persona = CONFIG["persona"]


# ── DB connection ─────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_mem["db_path"])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            ts         TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_session ON conversations (session_id, id)"
    )
    conn.commit()
    return conn


# ── Read ──────────────────────────────────────────────────────

def load_history(session_id: str) -> list[dict]:
    """Return the last history_limit turns for this session, oldest first."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations "
            "WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, _mem["history_limit"]),
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]


def build_memory_context(history: list[dict]) -> str:
    """Summarise the last context_window turns into a compact string."""
    if not history:
        return ""
    window  = _mem["context_window"]
    preview = _mem["content_preview_chars"]
    lines   = []
    for msg in history[-window:]:
        label = "You asked" if msg["role"] == "user" else f"{_persona['name']} said"
        lines.append(f"{label}: {msg['content'][:preview]}")
    return "\n".join(lines)


# ── Write ─────────────────────────────────────────────────────

def save_turn(session_id: str, role: str, content: str) -> None:
    """Append one turn to the conversation log."""
    with _db() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, ts) VALUES (?,?,?,?)",
            (session_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()


def clear_session(session_id: str) -> None:
    """Delete all history for a session."""
    with _db() as conn:
        conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
        conn.commit()
    logger.info("Memory cleared for session: %s", session_id)
