# Personal AI Agent — Bavish Reddy Kangari

A personal AI agent that talks **as you**, built with LangGraph, Claude (Anthropic), FastAPI, and Streamlit.  
Everything about the persona, routing, memory, and UI is driven by `config.yaml` — no hardcoding anywhere.

---

## What It Does

- Answers questions **as you** — first-person, human tone, with real opinions
- Remembers past conversation turns using **Redis** (auto-expires after 7 days)
- Routes simple messages directly to Claude; technical ones through a retrieval pipeline
- Serves a **terminal-style browser chat UI** (Streamlit) and a Telegram bot from the same backend
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

# 4. Start Redis (required for memory)
brew install redis && brew services start redis   # macOS
# or: docker run -d -p 6379:6379 redis            # Docker

# 5. Run everything
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
│   ├── context_node.py     Loads Redis history, builds memory context
│   ├── retrieval_node.py   Fetches code/knowledge from Neo4j (optional)
│   ├── bchat_node.py       Single LLM call — produces the final response
│   └── persist_node.py     Saves both turns to Redis memory
│
├── memory.py               Dual-backend memory — Redis (prod) or SQLite (local fallback)
├── prompt.py               Builds the Claude system prompt from config
├── config_loader.py        Loads config.yaml + expands ${ENV_VAR} refs
├── ui.py                   Streamlit terminal-style chat UI
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
Most AI agents are written as a single long function — prompt in, answer out. That breaks down fast when you need routing, memory, and optional tool calls in the same pipeline. LangGraph solves this by turning the agent into an explicit directed graph where each node does exactly one thing.

In this project the graph looks like:
```
intake_node → context_node → (optional) retrieval_node → bchat_node → persist_node
```
Each node reads from a shared typed state (`AgentState`) and returns a partial update. The edge between `context_node` and the rest is conditional — it checks `state["needs_tools"]` to decide whether to detour through Neo4j retrieval or go straight to Claude. This means adding a new data source, changing routing logic, or inserting a new step never touches any other node. Plain LangChain chains don't give you this — they're linear and hard to fork.

### Claude (Anthropic)
Claude was chosen over GPT for one specific reason: **persona consistency**. When you instruct Claude to be a specific person with specific opinions, it stays in character across long conversations without drifting into "as an AI" disclaimers. The system prompt defines not just what Bavish knows but *how he speaks* — with different tones for recruiters, engineers, and casual visitors. Claude respects those tone rules reliably.

The model is set in `config.yaml → llm.model`, so switching from `claude-sonnet-4-5` to `claude-haiku-3-5` (cheaper, faster) or `claude-opus-4` (more capable) requires zero code changes. Temperature is set to `0.9` — higher than typical defaults to produce more natural, conversational replies rather than stiff formal ones.

### FastAPI
FastAPI sits as a thin HTTP gateway between the outside world (browser, Telegram) and the MCP server. It does three things: accepts requests, validates them with Pydantic, and forwards them to the right MCP tool. No business logic lives here.

A critical detail: the LangGraph pipeline (`compiled_graph.invoke()`) is a synchronous blocking call — it runs Claude and waits for the full response. If called directly inside an async FastAPI handler, it would freeze the entire event loop for the duration of every Claude request, making the server unresponsive to all other requests. The fix is `await asyncio.to_thread(compiled_graph.invoke, ...)` — this runs the blocking pipeline in a thread pool so the event loop stays free.

### MCP (Model Context Protocol)
MCP is an open protocol by Anthropic that standardises how applications expose tools to LLMs. Instead of writing custom tool-calling code tied to one framework, you define tools once as MCP handlers and any MCP-compatible client can use them.

In this project MCP wraps three tools: `chat` (runs the full LangGraph pipeline), `get_persona` (returns the persona config as YAML), and `clear_memory` (wipes a session from Redis). The gateway calls these tools over in-process function calls right now, but because they're MCP-compliant, they could be exposed to Claude Desktop, Cursor, or any future MCP client without rewriting anything.

### Neo4j (Code Graph RAG)
This is the most architecturally interesting component. Standard RAG (Retrieval-Augmented Generation) stores documents as vectors and finds them by semantic similarity — good for prose, poor for code. Code has a fundamentally different structure: functions call other functions, classes inherit from other classes, modules import each other. A vector database loses all of that structure.

Neo4j is a graph database. The idea here is to index your actual codebase as a graph — each function/class is a node, each `CALLS` or `IMPORTS` relationship is an edge. When someone asks "how did you implement the RAG pipeline?", the retrieval node:

1. Uses Claude to extract entity names from the question (`["rag_pipeline", "retrieval_node"]`)
2. Traverses the Neo4j graph up to `max_hops: 3` hops deep following `CALLS` edges
3. Returns the full dependency chain: which functions call which, in which files, with their signatures

This gives Claude actual structural knowledge of the codebase — not just fuzzy semantic matches. It's currently disabled (`neo4j.enabled: false`) because the graph needs to be built first by indexing a codebase, but the full retrieval logic is wired and ready to activate.

### Redis
Redis is used as the conversation memory backend. Every message pair (user + assistant) is stored as a JSON-encoded entry in a Redis list, keyed by session ID (`{app.name}:session:{id}:history`). The `LPUSH` + `LRANGE` pattern means the most recent messages are always at the front of the list — loading the last 10 turns is an O(1) operation regardless of how long a conversation has been going.

The key production advantage over SQLite: Redis supports automatic key expiry via `EXPIRE`. Sessions are set to expire after 7 days (`redis_ttl_seconds: 604800`) — no manual cleanup needed, no unbounded database growth. For deployment, just swap `REDIS_URL` in `.env` to point to Upstash, Redis Cloud, or any hosted provider — the code doesn't change.

### Streamlit
Streamlit was chosen for the UI because it requires zero frontend build infrastructure — no webpack, no React, no TypeScript compilation. A Python file is the entire frontend.

The UI is styled to look like a macOS terminal window: traffic-light dots in the title bar, monospace font throughout, `❯` prompt prefix on every user message, green text for replies. The chat history renders as HTML inside the terminal card, and the input field is fused to the bottom of that card — so the entire experience feels like one continuous terminal session rather than a typical chat bubble UI. All visual details (colors, fonts, layout) are in CSS injected via `st.markdown(unsafe_allow_html=True)`, not in any external stylesheet.

### LangSmith
LangSmith provides observability for the LangGraph pipeline. When `LANGCHAIN_TRACING_V2=true` is set, every run is traced — you can see exactly which node ran, what state it received, what it returned, how long each step took, and how many tokens Claude used. This is invaluable for debugging routing decisions ("why did this message go through retrieval when it shouldn't have?") and for monitoring costs over time. Traces appear at `smith.langchain.com → Projects → bavish-bot`.

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
                    ├─ route=retrieve → retrieval_node → bchat_node → persist_node
                    │
                    └─ route=direct  ──────────────────→ bchat_node → persist_node
```

| Node | What it does |
|---|---|
| `intake_node` | Reads the message, sets `route` to `direct` or `retrieve` based on keywords |
| `context_node` | Loads Redis history, builds memory context, reads `route` from `intake_node` |
| `retrieval_node` | Queries Neo4j for relevant code context (skipped if Neo4j is disabled) |
| `bchat_node` | Calls Claude with system prompt + memory + optional code context |
| `persist_node` | Writes both turns to Redis so future messages have memory |

**Routing note:** `intake_node` is the single owner of routing decisions. `context_node` reads `state["route"]` — it does not re-scan keywords.

---

## Configuration

All settings live in `config.yaml`. The most common things to change:

```yaml
persona:
  name: "Your Full Name"       # shown in UI + injected into every prompt
  title: "Your Job Title"
  identity: |                  # sets Claude's personality and speaking style
    You are a real person, not a bot...

llm:
  model: "claude-sonnet-4-5"   # swap model here — no code changes needed
  max_tokens: 2048             # controls max reply length
  temperature: 0.9             # higher = more natural, conversational

memory:
  backend: "redis"             # redis | sqlite
  redis_ttl_seconds: 604800    # sessions auto-expire after 7 days
  history_limit: 10            # how many past messages to load per session

graph:
  routing:
    tool_keywords:             # words that trigger the retrieval path
      - "code"
      - "project"
      - "github"
```

Secrets (`ANTHROPIC_API_KEY`, `REDIS_URL`, `TELEGRAM_BOT_TOKEN`, etc.) go in `.env` only.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from console.anthropic.com |
| `REDIS_URL` | Yes (for Redis backend) | e.g. `redis://localhost:6379` or hosted URL |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Optional | Set `true` to enable tracing |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |
| `TELEGRAM_BOT_TOKEN` | Optional | From @BotFather on Telegram |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Optional | Only when `neo4j.enabled: true` |

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
| **LangSmith tracing** | Set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` in `.env` — view runs at smith.langchain.com |
| **SQLite fallback** | Set `memory.backend: "sqlite"` — no Redis needed, good for local dev |
| **Wide UI layout** | Set `ui.layout: "wide"` in config |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Claude (Anthropic) | Strong persona consistency, config-swappable model |
| Agent pipeline | LangGraph | Explicit node/edge control, typed state, easy to extend |
| API server | FastAPI + Uvicorn | Async, lightweight, auto-docs, non-blocking LLM calls |
| Agent protocol | MCP | Standard tool interface, future-compatible |
| Chat UI | Streamlit (terminal theme) | Zero frontend setup, custom dark terminal aesthetic |
| Memory | Redis (primary) | Fast, TTL-based auto-expiry, production-ready |
| Memory fallback | SQLite | Zero setup for local dev, built into Python |
| Code graph RAG | Neo4j (optional) | Structured traversal of code relationships |
| Observability | LangSmith (optional) | Trace every LLM call end-to-end |
| Messaging | Telegram Bot API (optional) | Chat from anywhere |

---

## Deployment

When deploying to a server (Railway, Render, Fly.io, etc.):

1. Set all environment variables in your hosting platform's dashboard
2. Point `REDIS_URL` to a hosted Redis (Upstash free tier works great)
3. Set `server.reload: false` in `config.yaml`
4. Set `ui.headless: true` in `config.yaml`
5. For Telegram, register the webhook: `GET /register-webhook?url=https://your-domain.com`

---

## Ideas for Future Improvements

- **Streaming responses** — stream Claude output token-by-token to the UI
- **Config validation** — Pydantic model to validate `config.yaml` on startup
- **Rate limiting** — protect the `/chat` endpoint from abuse
- **More retrieval sources** — GitHub issues, Notion, LinkedIn profile
- **Voice interface** — add a Whisper transcription layer
- **Auth** — simple token check so only you can access the agent

---

## License

MIT — use it, fork it, make it your own.
