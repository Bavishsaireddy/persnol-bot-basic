# nodes/resume_node.py
# Triggered when route == "resume".
# Builds a formatted resume string from config.yaml (persona, experience,
# education, skills, projects) and stores it in state["profile_context"]
# so that bchat_node can present it naturally via Claude.
# No live API calls — all data comes from config.yaml.
# All config keys come from config.yaml — zero hardcoding.

import logging
import os
import re
from time import perf_counter

from config_loader import CONFIG
from nodes.state import AgentState

logger = logging.getLogger(__name__)

_persona   = CONFIG["persona"]
_linkedin  = CONFIG.get("linkedin", {})
_knowledge = CONFIG.get("knowledge", {})
_resume    = CONFIG.get("resume", {})


# ── Lead data extractor ────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _extract_lead_data(text: str) -> dict:
    """Pull any email + phone number the visitor mentioned in their message."""
    emails = _EMAIL_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    data: dict = {}
    if emails:
        data["email"] = emails[0]
    if phones:
        data["phone"] = phones[0]
    return data


# ── Resume formatter ──────────────────────────────────────────────────────────

def _build_resume_text() -> str:
    """
    Assembles a plain-text resume from config.yaml.
    Sections: header, summary, experience, education, skills, projects.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# {_persona['name']}")
    lines.append(f"{_persona['title']} | {_persona['location']}")
    lines.append(f"Status: {_persona['status']}")

    contact_parts: list[str] = []
    linkedin_url = _linkedin.get("url", "")
    if linkedin_url:
        contact_parts.append(f"LinkedIn: {linkedin_url}")
    resume_url = _resume.get("url", "")
    if resume_url:
        contact_parts.append(f"Resume PDF: {resume_url}")
    email = os.getenv("CONTACT_EMAIL", "")
    if email and _resume.get("show_email", True):
        contact_parts.append(f"Email: {email}")
    if contact_parts:
        lines.append(" | ".join(contact_parts))

    lines.append("")

    # Summary
    summary = _linkedin.get("summary", "").strip()
    if summary:
        lines.append("## Summary")
        lines.append(summary)
        lines.append("")

    # Experience
    experience = _linkedin.get("experience") or _knowledge.get("experience") or []
    if experience:
        lines.append("## Experience")
        for exp in experience:
            role    = exp.get("title") or exp.get("role", "")
            company = exp.get("company", "")
            period  = exp.get("period", "")
            lines.append(f"**{role}** — {company} ({period})")
            for h in exp.get("highlights") or []:
                lines.append(f"  • {h}")
            lines.append("")

    # Education
    education = _linkedin.get("education") or []
    if education:
        lines.append("## Education")
        for edu in education:
            lines.append(f"**{edu.get('degree', '')}** — {edu.get('school', '')} ({edu.get('period', '')})")
        lines.append("")

    # Skills
    skills = _linkedin.get("skills") or _persona.get("stack") or []
    if skills:
        lines.append("## Skills")
        lines.append(", ".join(skills))
        lines.append("")

    # Projects
    projects = _knowledge.get("projects") or []
    if projects:
        lines.append("## Projects")
        for p in projects:
            link = f" — {p['github']}" if p.get("github") else ""
            tech = ", ".join(p.get("tech") or [])
            lines.append(f"**{p['name']}**{link}")
            lines.append(f"  {p.get('description', '').strip()}")
            if tech:
                lines.append(f"  Tech: {tech}")
            lines.append("")

    return "\n".join(lines).strip()


# ── Node ──────────────────────────────────────────────────────────────────────

def resume_node(state: AgentState) -> AgentState:
    """
    Formats a complete resume from config.yaml and stores it in
    state["profile_context"] for bchat_node to present.
    Also extracts any contact info (email/phone) the visitor included
    in their message and stores it in state["lead_data"] for persist_node
    to save.
    """
    t0         = perf_counter()
    session_id = state.get("session_id", "")
    user_msg   = state.get("user_message", "")

    resume_text = _build_resume_text()
    lead_data   = _extract_lead_data(user_msg)

    elapsed = round(perf_counter() - t0, 3)
    logger.debug(
        "resume_node | session=%s | resume_chars=%d | lead_found=%s | %.3fs",
        session_id, len(resume_text), bool(lead_data), elapsed,
    )

    return {
        **state,
        "profile_context": resume_text,
        "lead_data":        lead_data,
        "metadata": {
            **(state.get("metadata") or {}),
            "resume_node_seconds":    elapsed,
            "resume_node_lead_found": bool(lead_data),
        },
    }
