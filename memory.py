# memory.py
# Dual-backend memory layer — SQLite (local) or Redis (production).
# Switch via config.yaml → memory.backend: "sqlite" | "redis"
# All config comes from config.yaml → memory.

import json
import logging
import os
import sqlite3
from datetime import datetime

from config_loader import CONFIG

logger = logging.getLogger(__name__)

_mem     = CONFIG["memory"]
_persona = CONFIG["persona"]
BACKEND  = _mem.get("backend", "sqlite")


# ══════════════════════════════════════════════════════════════
#  Redis backend
# ══════════════════════════════════════════════════════════════

def _redis_client():
    import redis
    url = os.getenv("REDIS_URL", _mem.get("redis_url", "redis://localhost:6379"))
    return redis.from_url(url, decode_responses=True)

def _redis_key(session_id: str) -> str:
    app_name = CONFIG.get("app", {}).get("name", "agent")
    return f"{app_name}:session:{session_id}:history"

def _redis_load(session_id: str) -> list[dict]:
    r    = _redis_client()
    key  = _redis_key(session_id)
    raw  = r.lrange(key, 0, _mem["history_limit"] - 1)
    msgs = [json.loads(item) for item in raw]
    return list(reversed(msgs))

def _redis_save(session_id: str, role: str, content: str) -> None:
    r   = _redis_client()
    key = _redis_key(session_id)
    r.lpush(key, json.dumps({
        "role":    role,
        "content": content,
        "ts":      datetime.utcnow().isoformat(),
    }))
    ttl = _mem.get("redis_ttl_seconds", 86400 * 7)
    r.expire(key, ttl)

def _redis_clear(session_id: str) -> None:
    _redis_client().delete(_redis_key(session_id))
    logger.info("Redis memory cleared for session: %s", session_id)


# ══════════════════════════════════════════════════════════════
#  SQLite backend
# ══════════════════════════════════════════════════════════════

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

def _sqlite_load(session_id: str) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversations "
            "WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, _mem["history_limit"]),
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def _sqlite_save(session_id: str, role: str, content: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO conversations (session_id, role, content, ts) VALUES (?,?,?,?)",
            (session_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()

def _sqlite_clear(session_id: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
        conn.commit()
    logger.info("SQLite memory cleared for session: %s", session_id)


# ══════════════════════════════════════════════════════════════
#  Public API — backend-agnostic
# ══════════════════════════════════════════════════════════════

def load_history(session_id: str) -> list[dict]:
    """Return the last history_limit turns for this session, oldest first."""
    if BACKEND == "redis":
        return _redis_load(session_id)
    return _sqlite_load(session_id)


def save_turn(session_id: str, role: str, content: str) -> None:
    """Append one turn to the conversation log."""
    if BACKEND == "redis":
        _redis_save(session_id, role, content)
    else:
        _sqlite_save(session_id, role, content)


def clear_session(session_id: str) -> None:
    """Delete all history for a session."""
    if BACKEND == "redis":
        _redis_clear(session_id)
    else:
        _sqlite_clear(session_id)


# ══════════════════════════════════════════════════════════════
#  Lead capture — stores visitor contact info
# ══════════════════════════════════════════════════════════════

def _redis_lead_key(session_id: str) -> str:
    app_name = CONFIG.get("app", {}).get("name", "agent")
    return f"{app_name}:leads:{session_id}"

def _redis_save_lead(session_id: str, lead_data: dict) -> None:
    r   = _redis_client()
    key = _redis_lead_key(session_id)
    payload = {**lead_data, "ts": datetime.utcnow().isoformat(), "session_id": session_id}
    r.hset(key, mapping={k: str(v) for k, v in payload.items()})
    ttl = _mem.get("redis_ttl_seconds", 86400 * 7)
    r.expire(key, ttl)
    logger.info("Redis lead saved | session=%s | fields=%s", session_id, list(lead_data.keys()))

def _sqlite_save_lead(session_id: str, lead_data: dict) -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                email      TEXT,
                phone      TEXT,
                ts         TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO leads (session_id, email, phone, ts) VALUES (?,?,?,?)",
            (
                session_id,
                lead_data.get("email"),
                lead_data.get("phone"),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    logger.info("SQLite lead saved | session=%s | fields=%s", session_id, list(lead_data.keys()))


def save_lead(session_id: str, lead_data: dict) -> None:
    """Persist visitor contact info (email, phone, etc.) extracted from their message."""
    if not lead_data:
        return
    if BACKEND == "redis":
        _redis_save_lead(session_id, lead_data)
    else:
        _sqlite_save_lead(session_id, lead_data)


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
