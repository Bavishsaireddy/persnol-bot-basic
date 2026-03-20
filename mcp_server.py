# mcp_server.py
# MCP Server — exposes tools (chat, get_persona, clear_memory) over the MCP protocol.
# All LLM logic lives in the graph pipeline (graph.py → nodes/).
# Memory helpers live in memory.py. Prompt builder lives in prompt.py.

import logging
import os

import anthropic
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from config_loader import CONFIG
from memory import load_history, save_turn, clear_session, build_memory_context
from prompt import build_system_prompt

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────
_app     = CONFIG["app"]
_persona = CONFIG["persona"]
_llm     = CONFIG["llm"]
_mem     = CONFIG["memory"]
_neo4j   = CONFIG["neo4j"]

# ── MCP server ────────────────────────────────────────────────
app = Server(_app["name"])


# ── Tool definitions ──────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="chat",
            description=f"Talk to {_persona['name']}'s AI agent",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Unique session identifier"},
                    "message":    {"type": "string", "description": "The user's message"},
                },
                "required": ["session_id", "message"],
            },
        ),
        types.Tool(
            name="get_persona",
            description=f"Returns {_persona['name']}'s current persona and LLM config",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="clear_memory",
            description="Clear conversation history for a session",
            inputSchema={
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        ),
    ]


# ── Tool handlers ─────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    if name == "chat":
        session_id = arguments["session_id"]
        user_msg   = arguments["message"]

        # Deferred import keeps graph/nodes free of mcp_server dependency
        from graph import compiled_graph
        import asyncio

        # Run synchronous LangGraph pipeline in a thread so the async
        # event loop is never blocked while Claude is generating.
        result = await asyncio.to_thread(
            compiled_graph.invoke,
            {
                "session_id":   session_id,
                "user_message": user_msg,
                "messages":     [],
                "metadata":     {},
            },
        )
        answer = result.get("response", "")

        logger.debug(
            "chat | session=%s | route=%s",
            session_id,
            result.get("metadata", {}).get("intake_route", "?"),
        )
        return [types.TextContent(type="text", text=answer)]

    if name == "get_persona":
        return [types.TextContent(
            type="text",
            text=yaml.dump(
                {"persona": _persona, "llm": _llm},
                default_flow_style=False,
                allow_unicode=True,
            ),
        )]

    if name == "clear_memory":
        session_id = arguments["session_id"]
        clear_session(session_id)
        return [types.TextContent(type="text", text=f"Memory cleared for {session_id}")]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Standalone entry point ────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    print(f"Starting {_persona['name']} MCP Server  [{_app['version']}]")
    print(f"LLM    : {_llm['provider']} / {_llm['model']}")
    print(f"Memory : {_mem['backend']} → {_mem['db_path']}")
    print(f"Neo4j  : {'enabled' if _neo4j.get('enabled') else 'disabled'}")
    asyncio.run(stdio_server(app))
