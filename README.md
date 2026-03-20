# Personal AI Agent

A personal AI agent that talks **as you**, built with LangGraph, Claude (Anthropic), FastAPI, and Streamlit.  
Everything about the persona, routing, memory, and UI is driven by `config.yaml` — no hardcoding anywhere.

---

## What It Does

- Answers questions **as you** — first-person, with opinions, tone, and context
- Remembers past conversation turns using SQLite
- Routes simple messages directly to Claude; complex/technical ones through a retrieval pipeline
- Serves a browser chat UI (Streamlit) and a Telegram bot from the same backend
- Ships with a full test suite and clean examples for config and secrets

---

## Quick Start

```bash
# 1. Copy and fill in your personal config + secrets
cp config.yaml.example config.yaml      # add your name, title, identity, etc.
cp .env.example .env                    # add your ANTHROPIC_API_KEY

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate               # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run everything
python main.py
```

Open **http://localhost:8501** in your browser.

---

## Project Structure

```
files/
│
├── main.py                 Entry point — starts backend + UI together
├── gateway.py              FastAPI server — HTTP layer, routes to MCP tools
├── mcp_server.py           MCP server — exposes chat/persona/memory tools
├── graph.py                LangGraph pipeline — wires all nodes together
│
├── nodes/                  Graph nodes (one responsibility each)
│   ├── state.py            AgentState TypedDict — shared state schema
│   ├── intake_node.py      Reads message, decides routing (direct or retrieve)
│   ├── context_node.py     Loads chat history, builds memory context
│   ├── retrieval_node.py   Fetches code/knowledge from Neo4j (optional)
│   ├── bchat_node.py       Single LLM call — produces the final response
│   └── persist_node.py     Saves both turns to SQLite memory
│
├── memory.py               SQLite helpers — load, save, clear conversations
├── prompt.py               Builds the Claude system prompt from config
├── config_loader.py        Loads config.yaml + expands ${ENV_VAR} refs
├── ui.py                   Streamlit chat UI
│
├── tests/
│   ├── test_nodes.py       Unit tests — every node in isolation
│   ├── test_graph.py       Integration tests — full pipeline end-to-end
│   └── test_api.py         API tests — FastAPI endpoints
│
├── config.yaml             Your personal config — gitignored (copy from example)
├── config.yaml.example     Documented template — committed, safe to share
├── .env                    Your API keys — gitignored (copy from example)
├── .env.example            Documented secrets template
├── requirements.txt        Python dependencies
└── .gitignore              What to keep out of git
```

---

## Why These Technologies

### LangGraph
Used for the agent pipeline instead of plain LangChain because it gives explicit control over the flow — each node has one job, edges are conditional, and the state is typed. Easy to add, remove, or replace a node without touching the rest of the pipeline.

### Claude (Anthropic)
Chosen for its strong instruction-following and persona consistency. The model ID lives in `config.yaml` so you can swap to any Claude model (Haiku, Sonnet, Opus) without touching code.

### FastAPI
Thin HTTP layer between the UI/Telegram and the agent. Async, fast, and auto-generates `/docs` for free. No business logic lives here — it just forwards requests to the MCP tools.

### MCP (Model Context Protocol)
Wraps the agent tools (`chat`, `get_persona`, `clear_memory`) in a standard protocol. This means the agent can be connected to any MCP-compatible client in the future, not just this UI.

### Streamlit
Zero-config browser UI. No frontend build step, no JavaScript. Good enough for a personal tool and fast to iterate on.

### SQLite
Built into Python — no server, no setup, no Docker dependency just for memory. The database file is created automatically on first run. Swap to Redis later if you need multi-instance support.

---

## Why `config.yaml` Is in `.gitignore`

`config.yaml` contains your **personal details** — your name, job title, location, identity prompt, opinions, and work history. Even though it holds no API keys, this information is yours and should not be pushed to a public repo.

Both files are gitignored for different reasons:

```
.env          → gitignored → API keys, tokens, passwords (security)
config.yaml   → gitignored → your personal persona and details (privacy)
```

`config.yaml.example` **is** committed — it's a fully documented blank template so anyone cloning the repo knows exactly what to fill in.

**Setup on a new machine:**
```bash
cp config.yaml.example config.yaml   # then fill in your details
cp .env.example .env                 # then fill in your API keys
```

---

## How the Pipeline Works

Every message flows through a 5-node LangGraph pipeline:

```
intake_node  →  context_node
                    │
                    ├─ keyword match → retrieval_node → bchat_node → persist_node
                    │
                    └─ direct ──────────────────────→ bchat_node → persist_node
```

| Node | What it does |
|---|---|
| `intake_node` | Reads the message, sets route (`direct` or `retrieve`) |
| `context_node` | Loads SQLite history, builds memory context, decides if tools needed |
| `retrieval_node` | Queries Neo4j for relevant code context (skipped if Neo4j is disabled) |
| `bchat_node` | Calls Claude with system prompt + memory + code context |
| `persist_node` | Writes both turns to SQLite so future messages have memory |

---

## Configuration

All settings live in `config.yaml`. The most common things to change:

```yaml
persona:
  name: "Your Full Name"     # shown in UI + injected into every prompt
  title: "Your Job Title"
  identity: |                # who Claude pretends to be
    You are ...

llm:
  model: "claude-sonnet-4-5" # swap model here — no code changes needed
  temperature: 0.7

memory:
  history_limit: 10          # how many past messages to remember

graph:
  routing:
    tool_keywords:            # words that trigger the retrieval path
      - "code"
      - "project"
```

Secrets (`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.) go in `.env` only.

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Optional Features

| Feature | How to enable |
|---|---|
| **Telegram bot** | Set `telegram.enabled: true` in config + `TELEGRAM_BOT_TOKEN` in `.env` |
| **Neo4j code graph** | Set `neo4j.enabled: true` in config + Neo4j credentials in `.env` |
| **LangSmith tracing** | Set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` in `.env` |
| **Wide UI layout** | Set `ui.layout: "wide"` in config |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Claude (Anthropic) | Strong persona consistency, config-swappable model |
| Agent pipeline | LangGraph | Explicit node/edge control, easy to extend |
| API server | FastAPI + Uvicorn | Async, lightweight, auto-docs |
| Agent protocol | MCP | Standard tool interface, future-compatible |
| Chat UI | Streamlit | Zero frontend setup, fast iteration |
| Memory | SQLite | Zero setup, built into Python |
| Code graph RAG | Neo4j (optional) | Structured traversal of code relationships |
| Observability | LangSmith (optional) | Trace every LLM call end-to-end |
| Messaging | Telegram Bot API (optional) | Chat from anywhere |

---

## Ideas & Contributions

This is intentionally kept simple. Some directions it could grow:

- **Redis memory** — swap SQLite for Redis for multi-instance deployments
- **More retrieval sources** — GitHub issues, Notion, LinkedIn profile
- **Streaming responses** — stream Claude output token-by-token to the UI
- **Voice interface** — add a Whisper transcription layer
- **Auth** — add a simple token check so only you can access the agent
- **Deployment** — Dockerfile + Railway / Render / Fly.io setup

Pull requests and issues are welcome.

---

## License

MIT — use it, fork it, make it your own.
