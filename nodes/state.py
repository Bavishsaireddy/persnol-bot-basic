# nodes/state.py
# Shared state that flows through every node in the LangGraph pipeline.
# Every field is optional at entry — nodes populate what they need.

from typing import Annotated
import operator
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # ── Identity ──────────────────────────────────────────────
    session_id:     str             # caller-supplied, unique per conversation
    user_message:   str             # raw incoming message

    # ── Routing ───────────────────────────────────────────────
    route:          str             # "lc" | "orchestrate" | "finalize"
    needs_tools:    bool            # orchestration_node decides

    # ── Context built across nodes ────────────────────────────
    memory_context:  str            # summarised chat history
    code_context:    str            # Neo4j / code graph results
    tools_output:    str            # combined output from data_tool_node
    profile_context: str            # GitHub + LinkedIn data from profile_node
    needs_profile:   bool           # set by context_node when route == "profile"

    # ── LangChain / LangGraph message list ────────────────────
    messages: Annotated[list[dict], operator.add]   # accumulated turn-by-turn messages

    # ── Final output ──────────────────────────────────────────
    response:       str             # the text to return to the caller

    # ── Diagnostics ───────────────────────────────────────────
    metadata:       dict            # node timings, token counts, route taken
