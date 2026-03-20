# ui.py — Streamlit chat UI
# Reads ALL display config from config.yaml — zero hardcoding.
# Start via:  python main.py  (recommended)
#         or: streamlit run ui.py  (if backend already running)

import uuid
import requests
import streamlit as st

from config_loader import CONFIG

# ── Config aliases ────────────────────────────────────────────
_persona = CONFIG["persona"]
_server  = CONFIG["server"]
_ui      = CONFIG["ui"]
_llm     = CONFIG["llm"]
_mem     = CONFIG["memory"]

BACKEND        = f"http://localhost:{_server['port']}"
AVATAR_USER    = _ui["avatars"]["user"]
AVATAR_BOT     = _ui["avatars"]["assistant"]


# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title=f"{_persona['name']} — AI Agent",
    page_icon=_ui["page_icon"],
    layout=_ui["layout"],
)


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

if not backend_live:
    st.error(
        f"Backend is not running on port **{_server['port']}**.  \n"
        "Start everything with: `python main.py`",
        icon=_ui["avatars"]["assistant"],
    )


# ── Header ────────────────────────────────────────────────────
st.markdown(f"### {_persona['name']} — AI Agent")
st.markdown(
    f"<span style='color:gray;font-size:13px'>"
    f"{_persona['title']} · {_persona['location']} · "
    + " · ".join(_persona["stack"][:4])
    + "</span>",
    unsafe_allow_html=True,
)
st.divider()


# ── Chat history ──────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = AVATAR_USER if msg["role"] == "user" else AVATAR_BOT
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])


# ── Input ─────────────────────────────────────────────────────
first_name  = _persona["name"].split()[0]
placeholder = f"Ask {first_name} anything..."

if prompt := st.chat_input(placeholder, disabled=not backend_live):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATAR_USER):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=AVATAR_BOT):
        with st.spinner(f"{first_name} is thinking..."):
            try:
                resp = requests.post(
                    f"{BACKEND}/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "message":    prompt,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                answer = resp.json()["response"]
            except Exception as exc:
                answer = f"Error: {exc}"

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"**{_persona['name']}**")
    st.markdown(f"*{_persona['title']}*")
    st.markdown(f"{_persona['location']}")
    st.markdown(f"`{_persona['status']}`")

    st.divider()
    st.markdown("**Stack**")
    for tool in _persona["stack"]:
        st.markdown(f"- {tool}")

    st.divider()
    st.markdown("**Session**")
    st.code(st.session_state.session_id, language=None)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear chat"):
            old_sid = st.session_state.session_id
            st.session_state.messages  = []
            st.session_state.session_id = f"streamlit-{uuid.uuid4().hex[:8]}"
            try:
                requests.post(
                    f"{BACKEND}/clear-memory",
                    json={"session_id": old_sid},
                    timeout=5,
                )
            except Exception:
                pass
            st.rerun()

    with col2:
        if st.button("Persona"):
            try:
                resp = requests.get(f"{BACKEND}/persona", timeout=5)
                resp.raise_for_status()
                st.code(resp.json()["persona"], language="yaml")
            except Exception as exc:
                st.error(str(exc))

    st.divider()
    status_icon = "🟢" if backend_live else "🔴"
    st.caption(
        f"{status_icon} Backend: `{BACKEND}`  \n"
        f"Model: `{_llm['model']}`  \n"
        f"Memory: `{_mem['backend']}`  \n"
        f"History: last `{_mem['history_limit']}` turns"
    )
