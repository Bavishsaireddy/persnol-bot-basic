# prompt.py
# Builds the Claude system prompt from config.yaml → persona + knowledge.
# Shared by both mcp_server.py and bchat_node.py — no circular dependency.

import logging
import os
from pathlib import Path

from config_loader import CONFIG

logger = logging.getLogger(__name__)

_persona   = CONFIG["persona"]
_knowledge = CONFIG.get("knowledge", {})


# ── Knowledge file loader ──────────────────────────────────────────────────────

def _load_knowledge_files() -> str:
    """
    Reads all .md and .txt files from the knowledge/ folder (if configured).
    Returns their concatenated content, or an empty string if none exist.
    """
    files_dir = _knowledge.get("files_dir", "")
    if not files_dir:
        return ""

    base = Path(files_dir)
    if not base.is_dir():
        return ""

    parts: list[str] = []
    for path in sorted(base.glob("**/*")):
        if path.suffix.lower() in {".md", ".txt"} and path.is_file():
            try:
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    parts.append(f"### {path.stem}\n{text}")
            except Exception as exc:
                logger.warning("prompt | failed to read knowledge file %s: %s", path, exc)

    return "\n\n".join(parts)


# ── Knowledge section renderer ─────────────────────────────────────────────────

def _render_knowledge() -> str:
    """
    Renders the structured knowledge section from config.yaml → knowledge.
    Returns an empty string if the section is empty.
    """
    parts: list[str] = []

    # Projects
    projects = _knowledge.get("projects") or []
    if projects:
        lines = ["## Your projects"]
        for p in projects:
            tech = ", ".join(p.get("tech") or [])
            link = f" — {p['github']}" if p.get("github") else ""
            lines.append(f"- **{p['name']}**{link}: {p.get('description', '').strip()}")
            if tech:
                lines.append(f"  Tech: {tech}")
        parts.append("\n".join(lines))

    # Experience
    experience = _knowledge.get("experience") or []
    if experience:
        lines = ["## Your experience"]
        for e in experience:
            lines.append(f"- **{e['role']}** at {e['company']} ({e.get('period', '')})")
            for h in e.get("highlights") or []:
                lines.append(f"  - {h}")
        parts.append("\n".join(lines))

    # FAQs
    faqs = _knowledge.get("faqs") or []
    if faqs:
        lines = ["## Frequently asked questions"]
        for faq in faqs:
            lines.append(f"Q: {faq['q']}\nA: {faq['a']}")
        parts.append("\n".join(lines))

    # SOPs
    sops = _knowledge.get("sops") or []
    if sops:
        lines = ["## Standard operating procedures"]
        for sop in sops:
            lines.append(f"### {sop.get('title', 'SOP')}\n{sop.get('content', '').strip()}")
        parts.append("\n".join(lines))

    # Files from knowledge/ folder
    file_content = _load_knowledge_files()
    if file_content:
        parts.append(f"## Additional knowledge\n{file_content}")

    return "\n\n".join(parts)


# Cache knowledge once at import time (files don't change mid-run)
_KNOWLEDGE_BLOCK = _render_knowledge()


# ── Public API ─────────────────────────────────────────────────────────────────

def build_system_prompt(
    memory_context: str = "",
    code_context: str = "",
    profile_context: str = "",
) -> str:
    """
    Assembles the full system prompt from persona config + knowledge base.
    Optionally appends memory context, Neo4j code context, and live profile data.
    """
    stack_str    = "\n".join(f"  - {s}" for s in _persona["stack"])
    opinions_str = "\n".join(f"  - {o}" for o in _persona["opinions"])
    rules_str    = "\n".join(f"  - {r}" for r in _persona["rules"])
    tone_str     = "\n".join(
        f"  - {audience}: {desc}"
        for audience, desc in _persona["tone_by_audience"].items()
    )

    prompt = f"""
{_persona["identity"]}

## Your details
- Title: {_persona["title"]}
- Location: {_persona["location"]}
- Status: {_persona["status"]}
- Education: {_persona["education"]}

## Your stack
{stack_str}

## Your opinions
{opinions_str}

## Tone by audience
{tone_str}

## Rules
{rules_str}
""".strip()

    if _KNOWLEDGE_BLOCK:
        prompt += f"\n\n{_KNOWLEDGE_BLOCK}"

    if memory_context:
        prompt += f"\n\n## Recent conversation context\n{memory_context}"
    if profile_context:
        prompt += f"\n\n## Your live profile data (fetched right now)\n{profile_context}"
    if code_context:
        prompt += f"\n\n## Relevant code from your GitHub repo\n{code_context}"

    return prompt
