# graph.py
# LangGraph StateGraph — 5-node pipeline.
#
#   START
#     └─► intake_node
#               └─► context_node
#                     ├─ needs_tools → retrieval_node → bchat_node → persist_node → END
#                     └─ direct      ──────────────── → bchat_node → persist_node → END

import logging
from langgraph.graph import StateGraph, END

from nodes import (
    AgentState,
    intake_node,
    context_node,
    retrieval_node,
    bchat_node,
    persist_node,
)

logger = logging.getLogger(__name__)


# ── Edge condition ────────────────────────────────────────────

def _route_after_context(state: AgentState) -> str:
    return "retrieve" if state.get("needs_tools") else "direct"


# ── Graph builder ─────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("intake_node",    intake_node)
    g.add_node("context_node",   context_node)
    g.add_node("retrieval_node", retrieval_node)
    g.add_node("bchat_node",     bchat_node)
    g.add_node("persist_node",   persist_node)

    g.set_entry_point("intake_node")

    g.add_edge("intake_node", "context_node")

    g.add_conditional_edges(
        "context_node",
        _route_after_context,
        {
            "retrieve": "retrieval_node",
            "direct":   "bchat_node",
        },
    )

    g.add_edge("retrieval_node", "bchat_node")
    g.add_edge("bchat_node",     "persist_node")
    g.add_edge("persist_node",   END)

    return g


# ── Compiled singleton ────────────────────────────────────────
compiled_graph = build_graph().compile()

logger.info("LangGraph compiled — intake → context → (retrieval →) bchat → persist")
