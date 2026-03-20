# gateway.py
# Thin FastAPI layer — routes HTTP requests to the MCP server.
# No persona logic, no LLM calls, no hardcoding.

import logging
import os

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from config_loader import CONFIG
from mcp_server import call_tool

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config aliases ────────────────────────────────────────────
_app      = CONFIG["app"]
_server   = CONFIG["server"]
_persona  = CONFIG["persona"]
_telegram = CONFIG["telegram"]
_llm      = CONFIG["llm"]

# ── Telegram credentials (from .env) ─────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_ENABLED = _telegram.get("enabled", False)

# ── FastAPI app ───────────────────────────────────────────────
app = FastAPI(
    title=f"{_app['name']} gateway",
    version=_app["version"],
    description=f"HTTP gateway for {_persona['name']}'s AI agent",
)


# ── MCP bridge ───────────────────────────────────────────────

async def _mcp(tool: str, arguments: dict) -> str:
    try:
        results = await call_tool(tool, arguments)
        if not results:
            raise ValueError("MCP returned an empty result")
        return results[0].text
    except Exception as exc:
        logger.error("MCP call failed — tool=%s error=%s", tool, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Chat endpoint ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    response = await _mcp("chat", {"session_id": req.session_id, "message": req.message})
    return {"response": response}


# ── Clear memory endpoint ─────────────────────────────────────

class ClearMemoryRequest(BaseModel):
    session_id: str

@app.post("/clear-memory")
async def clear_memory_endpoint(req: ClearMemoryRequest):
    result = await _mcp("clear_memory", {"session_id": req.session_id})
    return {"result": result}


# ── Persona endpoint ──────────────────────────────────────────

@app.get("/persona")
async def get_persona():
    result = await _mcp("get_persona", {})
    return {"persona": result}


# ── Telegram webhook ──────────────────────────────────────────

@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not TELEGRAM_ENABLED:
        return {"ok": False, "reason": "telegram_disabled"}
    if not TELEGRAM_TOKEN:
        return {"ok": False, "reason": "missing_telegram_token"}

    data    = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text    = message.get("text", "").strip()

    if not chat_id or not text:
        return {"ok": True}

    if any(text.startswith(cmd) for cmd in _telegram.get("commands", [])):
        await _send_telegram(chat_id, _telegram["start_message"])
        return {"ok": True}

    prefix     = _telegram.get("session_prefix", "telegram")
    session_id = f"{prefix}-{chat_id}"
    response   = await _mcp("chat", {"session_id": session_id, "message": text})
    await _send_telegram(chat_id, response)
    return {"ok": True}


async def _send_telegram(chat_id: int, text: str) -> None:
    if not TELEGRAM_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not set")
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": _telegram.get("parse_mode", "Markdown"),
            },
        )


# ── Register Telegram webhook ─────────────────────────────────

@app.get("/register-webhook")
async def register_webhook(url: str):
    if not TELEGRAM_ENABLED:
        return {"ok": False, "reason": "telegram_disabled"}
    if not TELEGRAM_TOKEN:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not set")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": f"{url.rstrip('/')}/webhook"},
        )
    return resp.json()


# ── Health ────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "status":  "running",
        "agent":   _persona["name"],
        "model":   _llm["model"],
        "version": _app["version"],
    }


# ── Standalone entry point ────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "gateway:app",
        host=_server["host"],
        port=_server["port"],
        reload=_server["reload"],
        log_level=_server["log_level"],
    )
