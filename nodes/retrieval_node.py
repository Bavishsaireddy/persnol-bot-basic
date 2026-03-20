# nodes/retrieval_node.py
# Fetches supporting knowledge from Neo4j (when enabled in config).
# Populates state["code_context"] for bchat_node to use.
# All config comes from config.yaml → neo4j — zero hardcoding.

import logging
import os
from time import perf_counter

import anthropic

from config_loader import CONFIG
from nodes.state import AgentState

logger = logging.getLogger(__name__)

_llm   = CONFIG["llm"]
_neo4j = CONFIG["neo4j"]

_claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _fetch_from_neo4j(query: str) -> str:
    """Traverse the code graph for entities mentioned in the query."""
    if not _neo4j.get("enabled", False):
        return ""
    try:
        from neo4j import GraphDatabase

        driver     = GraphDatabase.driver(
            _neo4j["uri"], auth=(_neo4j["user"], _neo4j["password"])
        )
        max_hops   = _neo4j["max_hops"]
        max_ents   = _neo4j["max_entities"]
        result_lim = _neo4j["result_limit"]

        extraction = _claude.messages.create(
            model=_llm["model"],
            max_tokens=_llm["entity_extraction_max_tokens"],
            system=(
                "Extract function or class names from this query. "
                "Return only a comma-separated list, nothing else."
            ),
            messages=[{"role": "user", "content": query}],
        )
        entities = [e.strip() for e in extraction.content[0].text.split(",") if e.strip()]

        rows_out: list[str] = []
        with driver.session() as session:
            for entity in entities[:max_ents]:
                rows = session.run(
                    f"""
                    MATCH (n {{name: $name}})-[:CALLS*0..{max_hops}]->(dep)
                    RETURN n.name AS source, dep.name AS dep,
                           dep.file AS file, dep.signature AS sig
                    LIMIT {result_lim}
                    """,
                    name=entity,
                ).data()
                for row in rows:
                    rows_out.append(
                        f"{row['source']} → {row['dep']} "
                        f"(in {row.get('file','?')}) sig: {row.get('sig','?')}"
                    )
        driver.close()
        return "\n".join(rows_out)

    except Exception as exc:
        logger.warning("retrieval_node | Neo4j failed: %s", exc)
        return f"[Neo4j unavailable: {exc}]"


def retrieval_node(state: AgentState) -> AgentState:
    """
    Runs all enabled knowledge retrieval sources and populates
    state["code_context"] and state["tools_output"].
    """
    user_msg = state.get("user_message", "")
    t0 = perf_counter()

    code_context = _fetch_from_neo4j(user_msg)
    tools_output = code_context

    elapsed = round(perf_counter() - t0, 3)
    logger.debug(
        "retrieval_node | session=%s | chars=%d | %.3fs",
        state.get("session_id"), len(code_context), elapsed,
    )

    return {
        **state,
        "code_context": code_context,
        "tools_output": tools_output,
        "metadata": {
            **(state.get("metadata") or {}),
            "retrieval_seconds":    elapsed,
            "retrieval_code_chars": len(code_context),
        },
    }
