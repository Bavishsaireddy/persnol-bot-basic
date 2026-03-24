# ui.py — Streamlit chat UI (full terminal style)
# Start via:  python main.py  (recommended)
#         or: streamlit run ui.py  (if backend already running)

import html
import uuid
import requests
import streamlit as st

from config_loader import CONFIG

# ── Config aliases ────────────────────────────────────────────
_persona = CONFIG["persona"]
_server  = CONFIG["server"]
_ui      = CONFIG["ui"]

BACKEND    = f"http://localhost:{_server['port']}"
first_name = _persona["name"].split()[0]

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title=_persona["name"],
    page_icon=_ui["page_icon"],
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, header, footer,
[data-testid="stToolbar"],
[data-testid="collapsedControl"] { display: none !important; }

/* ── Page background ── */
[data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at 20% 20%, #1a1040 0%, #0d0f14 45%, #0a1628 100%);
    min-height: 100vh;
}
[data-testid="stMain"] { background: transparent; }
section[data-testid="stMain"] > div { padding-top: 0 !important; }

/* ── Terminal window ── */
.terminal {
    background: #0e1117;
    border: 1px solid #2a2d3a;
    border-radius: 12px 12px 0 0;
    border-bottom: none;
    overflow: hidden;
    margin-bottom: 0;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5);
}
.terminal-bar {
    background: #1c1f26;
    padding: 9px 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    border-bottom: 1px solid #2a2d3a;
}
.dot-red { width:11px;height:11px;border-radius:50%;background:#ff5f57;flex-shrink:0; }
.dot-yel { width:11px;height:11px;border-radius:50%;background:#febc2e;flex-shrink:0; }
.dot-grn { width:11px;height:11px;border-radius:50%;background:#28c840;flex-shrink:0; }

/* ── Terminal body text ── */
.terminal-body {
    padding: 16px 20px 14px;
    font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.82rem;
    line-height: 1.75;
}
.t-prompt  { color: #6366f1; font-weight: 700; }
.t-cmd     { color: #e2e8f0; }
.t-key     { color: #6b7280; }
.t-val     { color: #22c55e; }
.t-val-dim { color: #a5b4fc; }
.t-divider { border: none; border-top: 1px solid #1e2130; margin: 10px 0 6px; }
.t-user-line { margin: 4px 0 2px; }
.t-reply {
    color: #22c55e;
    padding-left: 14px;
    margin: 0 0 4px;
    white-space: pre-wrap;
    word-break: break-word;
}

/* ── Blinking cursor in idle state ── */
.t-cursor {
    display: inline-block;
    width: 7px; height: 13px;
    background: #22c55e;
    vertical-align: middle;
    margin-left: 1px;
    animation: blink 1.1s step-end infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* ── Form wraps the input line — no default styling ── */
[data-testid="stForm"] {
    background: #0e1117 !important;
    border: 1px solid #2a2d3a !important;
    border-top: 1px solid #1e2130 !important;
    border-radius: 0 0 12px 12px !important;
    padding: 0 !important;
    margin-top: 0 !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5) !important;
}
/* Hide the submit button — Enter key triggers it */
[data-testid="stFormSubmitButton"] { display: none !important; }

/* ── Text input — looks like a terminal prompt line ── */
[data-testid="stTextInput"] {
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stTextInput"] > div {
    background: #0e1117 !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 0 12px 12px !important;
    position: relative !important;
    padding: 0 !important;
}
/* Permanent ❯ prompt */
[data-testid="stTextInput"] > div::before {
    content: "❯";
    position: absolute;
    left: 20px;
    top: 50%;
    transform: translateY(-50%);
    color: #6366f1;
    font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 0.84rem;
    font-weight: 700;
    pointer-events: none;
    z-index: 10;
}
[data-testid="stTextInput"] > div:focus-within::before { color: #22c55e; }
[data-testid="stTextInput"] input {
    background: #0e1117 !important;
    border: none !important;
    border-radius: 0 0 12px 12px !important;
    color: #e2e8f0 !important;
    font-size: 0.84rem !important;
    font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace !important;
    caret-color: #22c55e !important;
    box-shadow: none !important;
    outline: none !important;
    padding: 12px 16px 12px 38px !important;
    height: 44px !important;
}
[data-testid="stTextInput"] input:focus {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stTextInput"] input::placeholder { color: #2a2d3a !important; }
[data-testid="stForm"]:focus-within {
    border-color: #22c55e !important;
    box-shadow: 0 0 0 1px rgba(34,197,94,0.1) !important;
}

/* ── Spinner — inside terminal ── */
[data-testid="stSpinner"] {
    background: transparent !important;
    padding: 6px 0 !important;
    font-family: 'SF Mono', monospace !important;
    font-size: 0.78rem !important;
    color: #374151 !important;
}

/* ── Clear button ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1e2130 !important;
    color: #374151 !important;
    border-radius: 6px !important;
    font-size: 0.7rem !important;
    font-family: 'SF Mono', monospace !important;
    padding: 3px 10px !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    border-color: #374151 !important;
    color: #6b7280 !important;
}

/* ── Offline banner ── */
.offline-banner {
    background: rgba(239,68,68,0.07);
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 10px;
    padding: 10px 14px;
    color: #fca5a5;
    font-size: 0.8rem;
    font-family: 'SF Mono', monospace;
    margin-bottom: 8px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #0d0f14; }
::-webkit-scrollbar-thumb { background: #1e2130; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = f"streamlit-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Backend health check ──────────────────────────────────────
def _backend_ok() -> bool:
    try:
        return requests.get(f"{BACKEND}/", timeout=2).status_code == 200
    except Exception:
        return False

backend_live = _backend_ok()

# ── Build chat history HTML ───────────────────────────────────
def _chat_lines_html(messages: list[dict]) -> str:
    if not messages:
        return ""
    lines = ['<hr class="t-divider">']
    for msg in messages:
        safe = html.escape(msg["content"])
        if msg["role"] == "user":
            lines.append(
                f'<div class="t-user-line">'
                f'<span class="t-prompt">❯</span> '
                f'<span class="t-cmd">{safe}</span>'
                f'</div>'
            )
        else:
            lines.append(f'<div class="t-reply">{safe}</div>')
    return "\n".join(lines)

# ── Terminal card (profile + chat history) ────────────────────
status_val   = "Let's shoot 🟢" if backend_live else "Offline 🔴"
history_html = _chat_lines_html(st.session_state.messages)

st.markdown(f"""
<div class="terminal">
  <div class="terminal-bar">
    <span class="dot-red"></span>
    <span class="dot-yel"></span>
    <span class="dot-grn"></span>
  </div>
  <div class="terminal-body">
    <div><span class="t-prompt">❯</span> <span class="t-cmd">whoami</span></div>
    <div><span class="t-val">{_persona['name']}</span></div>
    <div style="margin-top:6px">
      <span class="t-prompt">❯</span> <span class="t-cmd">cat profile.json</span>
    </div>
    <div>
      <span class="t-key">  role   </span><span class="t-key">→ </span><span class="t-val-dim">{_persona['title']}</span><br>
      <span class="t-key">  based  </span><span class="t-key">→ </span><span class="t-val-dim">{_persona['location']}</span><br>
      <span class="t-key">  status </span><span class="t-key">→ </span><span class="t-val">{status_val}</span>
    </div>
    {history_html}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Offline banner ────────────────────────────────────────────
if not backend_live:
    st.markdown(
        f'<div class="offline-banner">⚠ backend not running on port '
        f'<strong>{_server["port"]}</strong> — run <code>python main.py</code></div>',
        unsafe_allow_html=True,
    )

# ── Input form — fused as terminal bottom ────────────────────
with st.form("cmd_form", clear_on_submit=True):
    prompt = st.text_input(
        "cmd",
        placeholder="type your command...",
        label_visibility="collapsed",
        disabled=not backend_live,
    )
    submitted = st.form_submit_button("send", use_container_width=False)

# ── Clear button ──────────────────────────────────────────────
_, col_btn = st.columns([6, 1])
with col_btn:
    if st.button("clear", key="clear_btn"):
        old_sid = st.session_state.session_id
        st.session_state.messages = []
        st.session_state.session_id = f"streamlit-{uuid.uuid4().hex[:8]}"
        try:
            requests.post(f"{BACKEND}/clear-memory",
                          json={"session_id": old_sid}, timeout=5)
        except Exception:
            pass
        st.rerun()

# ── Handle submission ─────────────────────────────────────────
if submitted and prompt and prompt.strip():
    st.session_state.messages.append({"role": "user", "content": prompt.strip()})

    with st.spinner(""):
        try:
            resp = requests.post(
                f"{BACKEND}/chat",
                json={"session_id": st.session_state.session_id,
                      "message": prompt.strip()},
                timeout=30,
            )
            resp.raise_for_status()
            answer = resp.json().get("response", "").strip()
            if not answer:
                answer = "No response received — please try again."
        except Exception as exc:
            answer = f"Error: {exc}"

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
