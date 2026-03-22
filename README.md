# Personal AI Agent — Bavish Reddy Kangari

A personal AI agent that talks **as you**, built with LangGraph, Claude (Anthropic), FastAPI, and Streamlit.
Everything — persona, routing, memory, knowledge, and UI — is driven by `config.yaml`. No hardcoding anywhere.

---

## What It Does

- Answers questions **as you** — first-person, human tone, with real opinions and context
- Fetches your **live GitHub repos and profile** when asked about your code or projects
- Answers from your **LinkedIn profile** (experience, education, skills) stored in config
- Loads any **knowledge files** you drop in the `knowledge/` folder — SOPs, bios, FAQs, project writeups
- Remembers past conversation turns using **Redis** (auto-expires after 7 days)
- Routes messages intelligently — simple greetings go direct to Claude; technical or profile questions go through dedicated retrieval nodes
- Serves a **terminal-style browser chat UI** (Streamlit) and a **Telegram bot** from the same backend
- Ships with a full test suite and clean examples for config and secrets

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd files

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up config and secrets
cp config.yaml.example config.yaml    # fill in your name, persona, GitHub username, LinkedIn details
cp .env.example .env                  # add your ANTHROPIC_API_KEY

# 5. Start Redis (required for memory)
brew install redis && brew services start redis    # macOS
# or: docker run -d -p 6379:6379 redis             # Docker

# 6. Run everything
python main.py
```

Open **http://localhost:8501** in your browser.

---

## Project Structure

```
files/
│
├── main.py                  Entry point — starts FastAPI backend + Streamlit UI together
├── gateway.py               FastAPI server — HTTP layer, routes to MCP tools
├── mcp_server.py            MCP server — exposes chat / persona / memory tools
├── graph.py                 LangGraph pipeline — wires all 6 nodes together
│
├── nodes/                   Graph nodes (one responsibility each)
│   ├── state.py             AgentState TypedDict — shared state schema
│   ├── intake_node.py       Reads message, decides routing (direct / retrieve / profile)
│   ├── context_node.py      Loads Redis history, builds memory context
│   ├── retrieval_node.py    Fetches code context from Neo4j (optional)
│   ├── profile_node.py      Fetches live GitHub data + formats LinkedIn from config
│   ├── bchat_node.py        Single LLM call — produces the final response
│   └── persist_node.py      Saves both turns to Redis memory
│
├── knowledge/               Drop any .md or .txt file here — loaded into the system prompt
│   ├── about-me.md          Your background, personality, what you're looking for
│   └── sop-recruiter.md     How the bot handles recruiter conversations
│
├── memory.py                Dual-backend memory — Redis (prod) or SQLite (local fallback)
├── prompt.py                Builds the Claude system prompt from persona + knowledge config
├── config_loader.py         Loads config.yaml and expands ${ENV_VAR} references
├── ui.py                    Streamlit terminal-style chat UI
│
├── tests/
│   ├── test_nodes.py        Unit tests — every node in isolation
│   ├── test_graph.py        Integration tests — full pipeline end-to-end
│   └── test_api.py          API tests — FastAPI endpoints
│
├── config.yaml              Your personal config — gitignored (copy from example)
├── config.yaml.example      Fully documented template — safe to commit
├── .env                     Your API keys — gitignored (copy from example)
├── .env.example             Documented secrets template
├── requirements.txt         Python dependencies
└── .gitignore               Keeps config.yaml, .env, and knowledge/ out of git
```

---

## How the Pipeline Works

Every message flows through a 6-node LangGraph pipeline:

```
START
  └─► intake_node
            └─► context_node
                      │
                      ├─ route=profile  → profile_node   → bchat_node → persist_node → END
                      │
                      ├─ route=retrieve → retrieval_node → bchat_node → persist_node → END
                      │
                      └─ route=direct   ──────────────── → bchat_node → persist_node → END
```

| Node | What it does |
|---|---|
| `intake_node` | Reads the message, sets `route` to `profile`, `retrieve`, or `direct` based on keywords |
| `context_node` | Loads Redis history, builds memory context, translates route into `needs_profile` / `needs_tools` flags |
| `profile_node` | Calls GitHub API for live repo data; formats LinkedIn from `config.yaml` |
| `retrieval_node` | Queries Neo4j for relevant code context (only when `neo4j.enabled: true`) |
| `bchat_node` | Calls Claude with system prompt + memory + whatever context the active node produced |
| `persist_node` | Writes both turns to Redis so future messages have memory |

**Routing priority:** profile keywords beat tool keywords. `intake_node` is the single owner of all routing decisions — `context_node` just reads what intake already decided.

---

## Knowledge System

The bot answers from three stacked knowledge sources, all injected into the system prompt:

### 1. `config.yaml → persona`
Core identity — name, title, location, stack, opinions, tone rules. This is what makes the bot sound like you.

### 2. `config.yaml → knowledge`
Structured facts: projects, experience, FAQs, and short SOPs.

```yaml
knowledge:
  projects:
    - name: "My Project"
      description: "What it does and why."
      tech: ["Python", "FastAPI"]
      github: "https://github.com/..."

  experience:
    - role: "AI Engineer"
      company: "Acme Corp"
      period: "2024 – present"
      highlights:
        - "Built X using Y."

  faqs:
    - q: "Are you available?"
      a: "Yes, immediately."

  sops:
    - title: "How to answer salary questions"
      content: "My target is $X–$Y..."
```

### 3. `knowledge/` folder
For longer content — bios, recruiter SOPs, project writeups, interview prep notes. Drop any `.md` or `.txt` file here and it loads automatically at startup. The filename becomes the section heading.

```
knowledge/
  about-me.md          ← your background and personality
  sop-recruiter.md     ← how to handle recruiter conversations
  project-rag.md       ← detailed writeup of a project
  ...
```

---

## GitHub + LinkedIn Integration

### GitHub (live)
When a user asks about repos, contributions, stars, or code — the `profile_node` calls the GitHub API and returns your real, up-to-date repo list, bio, follower count, and more.

Configure in `config.yaml`:
```yaml
github:
  enabled: true
  username: "your-github-username"
```

Optional: add `GITHUB_TOKEN=ghp_...` to `.env` to raise the rate limit from 60 to 5000 requests/hour.

**Trigger words:** `github`, `repo`, `repository`, `open source`, `contributions`, `stars`, `commits`, `pull request`

### LinkedIn (from config)
LinkedIn's public API requires company-level OAuth approval — live fetching is not possible without it. Instead, fill in your profile details once in `config.yaml` and the bot answers from them accurately.

```yaml
linkedin:
  enabled: true
  url: "https://www.linkedin.com/in/your-profile"
  headline: "AI Engineer · LangGraph · Claude · FastAPI"
  summary: |
    Paste your LinkedIn About section here.
  experience:
    - title: "AI Engineer"
      company: "Acme Corp"
      period: "2024 – present"
      highlights:
        - "Built LLM pipelines..."
  education:
    - degree: "MS Computer Science"
      school: "Cal State East Bay"
      period: "2022 – 2024"
  skills:
    - "LangGraph"
    - "Python"
    - "FastAPI"
  certifications:
    - "AWS ML Specialty"
```

For more detail (recommendations, full job descriptions), put it in `knowledge/linkedin.md`.

**Trigger words:** `linkedin`, `resume`, `cv`, `profile`, `experience`, `background`, `work history`, `connect`

---

## Configuration Reference

All settings live in `config.yaml`. Never hardcode values in Python files.

```yaml
persona:
  name: "Your Full Name"
  title: "Your Job Title"
  identity: |
    You are [name] — a real person...
  stack: [...]
  opinions: [...]
  rules: [...]
  tone_by_audience:
    recruiter: "warm, confident, 2-3 sentences"
    engineer: "detailed, technical"
    casual: "relaxed, can be funny"

llm:
  model: "claude-sonnet-4-5"     # swap model — zero code changes needed
  max_tokens: 2048
  temperature: 0.9               # higher = more natural/conversational

memory:
  backend: "redis"               # redis | sqlite
  redis_ttl_seconds: 604800      # sessions auto-expire after 7 days
  history_limit: 10              # past messages to load per session

graph:
  routing:
    tool_keywords:               # trigger retrieval_node
      - "code"
      - "project"
      - "architecture"
    default_route: "direct"

github:
  enabled: true
  username: "your-github-username"
  max_repos: 6

linkedin:
  enabled: true
  url: "https://www.linkedin.com/in/..."
  headline: "..."
  summary: |
    ...
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key — [console.anthropic.com](https://console.anthropic.com) |
| `REDIS_URL` | Yes (Redis backend) | e.g. `redis://localhost:6379` or hosted URL |
| `GITHUB_TOKEN` | Optional | Raises GitHub API rate limit from 60 to 5000 req/hr |
| `TELEGRAM_BOT_TOKEN` | Optional | From @BotFather on Telegram |
| `NEO4J_URI` | Optional | Only when `neo4j.enabled: true` |
| `NEO4J_USER` | Optional | Neo4j username |
| `NEO4J_PASSWORD` | Optional | Neo4j password |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Optional | Set `true` to enable LangSmith traces |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

---

## What to Gitignore

```
.env            → gitignored → API keys and secrets (security)
config.yaml     → gitignored → your personal persona and details (privacy)
knowledge/      → gitignored → your personal SOPs and profile notes (privacy)
```

`config.yaml.example` and `.env.example` **are** committed — they are fully documented blank templates so anyone cloning the repo knows exactly what to fill in.

**Setup on a new machine:**
```bash
cp config.yaml.example config.yaml    # fill in your personal details
cp .env.example .env                  # fill in your API keys
```

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
| **GitHub profile fetching** | Set `github.enabled: true` + `github.username` in config |
| **LinkedIn answers** | Set `linkedin.enabled: true` + fill in profile fields in config |
| **Knowledge folder** | Drop any `.md` / `.txt` file into `knowledge/` — loaded automatically |
| **Telegram bot** | Set `telegram.enabled: true` in config + `TELEGRAM_BOT_TOKEN` in `.env` |
| **Neo4j code graph** | Set `neo4j.enabled: true` in config + Neo4j credentials in `.env` |
| **LangSmith tracing** | Set `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` in `.env` |
| **SQLite fallback** | Set `memory.backend: "sqlite"` — no Redis needed, good for local dev |
| **Wide UI layout** | Set `ui.layout: "wide"` in config |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Claude (Anthropic) | Strong persona consistency; config-swappable model |
| Agent pipeline | LangGraph | Explicit node/edge control, typed state, easy to extend |
| API server | FastAPI + Uvicorn | Async, lightweight, auto-docs at `/docs` |
| Agent protocol | MCP | Standard tool interface, future-compatible with Claude Desktop / Cursor |
| Chat UI | Streamlit (terminal theme) | Zero frontend setup, custom dark terminal aesthetic |
| Memory | Redis (primary) | Fast, TTL-based auto-expiry, production-ready |
| Memory fallback | SQLite | Zero setup for local dev, built into Python |
| Profile data | GitHub REST API | Live repo and bio data, no auth required for public profiles |
| Code graph RAG | Neo4j (optional) | Structured traversal of code call relationships |
| Observability | LangSmith (optional) | Trace every LLM call end-to-end |
| Messaging | Telegram Bot API (optional) | Chat from anywhere |

---

## Deployment

When deploying to a server (Railway, Render, Fly.io, etc.):

1. Set all environment variables in your hosting platform's dashboard
2. Point `REDIS_URL` to a hosted Redis instance (Upstash free tier works great)
3. Set `server.reload: false` in `config.yaml`
4. Set `ui.headless: true` in `config.yaml`
5. For Telegram, register the webhook after deploy: `GET /register-webhook?url=https://your-domain.com`

---

## Why These Technologies

### LangGraph
Most AI agents are written as a single long function — prompt in, answer out. That breaks down fast when you need routing, memory, and optional tool calls in the same pipeline. LangGraph turns the agent into an explicit directed graph where each node does exactly one thing and the edges between them are conditions on state.

In this project the routing is a 3-way fork: profile questions go to `profile_node`, technical questions go to `retrieval_node`, and everything else goes straight to Claude. Adding a new path, inserting a new step, or changing routing logic never touches any other node. Plain LangChain chains don't give you this — they're linear and hard to fork.

### Claude (Anthropic)
Claude was chosen for one specific reason: **persona consistency**. When instructed to be a specific person with specific opinions, it stays in character across long conversations without drifting into "as an AI" disclaimers. The system prompt defines not just what the person knows but *how they speak* — with different tones for recruiters, engineers, and casual visitors. Temperature is set to `0.9` — higher than typical defaults to produce natural, conversational replies rather than stiff formal ones.

### FastAPI
FastAPI sits as a thin HTTP gateway between the outside world and the MCP server. A critical detail: `compiled_graph.invoke()` is a synchronous blocking call. If called directly inside an async FastAPI handler, it would freeze the entire event loop for every Claude request. The fix is `await asyncio.to_thread(compiled_graph.invoke, ...)` — this offloads the blocking call to a thread pool so the event loop stays free.

### MCP (Model Context Protocol)
MCP is an open protocol by Anthropic that standardises how applications expose tools to LLMs. In this project MCP wraps three tools: `chat` (runs the full LangGraph pipeline), `get_persona` (returns the persona config), and `clear_memory` (wipes a session from Redis). Because they're MCP-compliant, they could be exposed to Claude Desktop, Cursor, or any future MCP client without rewriting anything.

### Redis
Every message pair is stored as JSON in a Redis list keyed by session ID. The `LPUSH` + `LRANGE` pattern keeps the most recent messages at the front — loading the last 10 turns is O(1) regardless of conversation length. Sessions auto-expire after 7 days via Redis `EXPIRE` — no manual cleanup, no unbounded database growth. Swap `REDIS_URL` in `.env` to any hosted provider and the code doesn't change.

### Neo4j (Code Graph RAG)
Standard vector RAG is good for prose but poor for code — it loses structural relationships like "function A calls function B which imports module C". Neo4j indexes the codebase as a graph and the retrieval node traverses it by following `CALLS` edges up to `max_hops` deep. This gives Claude actual structural knowledge of the codebase, not just fuzzy semantic matches. Currently disabled (`neo4j.enabled: false`) until a graph is built, but the full retrieval logic is wired and ready.

---

## Ideas for Future Improvements

- **Streaming responses** — stream Claude output token-by-token to the UI
- **Config validation** — Pydantic model to validate `config.yaml` on startup
- **Rate limiting** — protect the `/chat` endpoint from abuse
- **Voice interface** — add a Whisper transcription layer in front of the pipeline
- **Auth** — simple token check so only you (and people you share it with) can access the agent
- **Calendar / availability** — connect Google Calendar so the bot knows your schedule

---

## License

MIT — use it, fork it, make it yours.
