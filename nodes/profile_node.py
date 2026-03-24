# nodes/profile_node.py
# Fetches live GitHub data and formats LinkedIn profile from config.yaml.
# Runs only when route == "profile" (triggered by profile keywords in the message).
# Populates state["profile_context"] for bchat_node to use.
# All config comes from config.yaml → github / linkedin — zero hardcoding.

import logging
import os
from time import perf_counter
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

from config_loader import CONFIG
from nodes.state import AgentState

logger = logging.getLogger(__name__)

_github   = CONFIG.get("github",   {})
_linkedin = CONFIG.get("linkedin", {})


# ── Shared HTTP helper ─────────────────────────────────────────────────────────

def _api_get(url: str, headers: dict) -> dict | list | None:
    """Generic GET with JSON response. Returns None on any failure."""
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except URLError as exc:
        logger.warning("profile_node | request failed %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.warning("profile_node | unexpected error %s: %s", url, exc)
        return None


# ── GitHub fetcher ─────────────────────────────────────────────────────────────

def _fetch_github() -> str:
    """Fetches user bio + top repos from the GitHub API."""
    if not _github.get("enabled", False):
        return ""

    username = _github.get("username", "")
    if not username:
        return ""
    max_repos = int(_github.get("max_repos", 6))

    token = os.getenv("GITHUB_TOKEN") or _github.get("token", "")
    if token.startswith("${"):
        token = ""

    gh_headers = {"Accept": "application/vnd.github+json"}
    if token:
        gh_headers["Authorization"] = f"Bearer {token}"

    parts: list[str] = [f"## GitHub — github.com/{username}"]

    user = _api_get(f"https://api.github.com/users/{username}", gh_headers)
    if isinstance(user, dict):
        details: list[str] = []
        if user.get("bio"):
            details.append(f"Bio: {user['bio'].strip()}")
        if user.get("company"):
            details.append(f"Company: {user['company'].strip()}")
        if user.get("blog"):
            details.append(f"Website: {user['blog'].strip()}")
        details.append(
            f"Public repos: {user.get('public_repos', 0)} | "
            f"Followers: {user.get('followers', 0)} | "
            f"Following: {user.get('following', 0)}"
        )
        parts.append("\n".join(details))

    repos = _api_get(
        f"https://api.github.com/users/{username}/repos"
        f"?sort=updated&direction=desc&per_page={max_repos}",
        gh_headers,
    )
    if isinstance(repos, list) and repos:
        repo_lines = ["### Top repositories (most recently updated)"]
        for repo in repos[:max_repos]:
            desc   = repo.get("description") or "No description."
            topics = ", ".join(repo.get("topics") or [])
            line   = (
                f"- **{repo.get('name', '')}** "
                f"({repo.get('language') or '—'}) "
                f"★{repo.get('stargazers_count', 0)} "
                f"⑂{repo.get('forks_count', 0)}\n"
                f"  {desc}"
            )
            if topics:
                line += f"\n  Topics: {topics}"
            if repo.get("html_url"):
                line += f"\n  {repo['html_url']}"
            repo_lines.append(line)
        parts.append("\n".join(repo_lines))

    return "\n\n".join(parts)


# ── LinkedIn formatter ─────────────────────────────────────────────────────────

def _format_linkedin() -> str:
    """
    Renders the full LinkedIn profile from config.yaml → linkedin.
    Covers: headline, connections, summary, experience, education, skills,
    and certifications.
    """
    if not _linkedin.get("enabled", False):
        return ""

    url  = _linkedin.get("url", "")
    parts: list[str] = [f"## LinkedIn — {url}"]

    if _linkedin.get("headline"):
        parts.append(f"Headline: {_linkedin['headline']}")
    if _linkedin.get("connections"):
        parts.append(f"Connections: {_linkedin['connections']}")

    summary = (_linkedin.get("summary") or "").strip()
    if summary:
        parts.append(f"Summary:\n{summary}")

    # Experience
    experience = _linkedin.get("experience") or []
    if experience:
        lines = ["### Experience"]
        for e in experience:
            lines.append(f"- **{e.get('title', '')}** at {e.get('company', '')} ({e.get('period', '')})")
            for h in e.get("highlights") or []:
                lines.append(f"  - {h}")
        parts.append("\n".join(lines))

    # Education
    education = _linkedin.get("education") or []
    if education:
        lines = ["### Education"]
        for e in education:
            lines.append(f"- {e.get('degree', '')} — {e.get('school', '')} ({e.get('period', '')})")
        parts.append("\n".join(lines))

    # Skills
    skills = _linkedin.get("skills") or []
    if skills:
        parts.append(f"### Skills\n{', '.join(skills)}")

    # Certifications
    certs = _linkedin.get("certifications") or []
    if certs:
        lines = ["### Certifications"]
        for c in certs:
            lines.append(f"- {c}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ── Node ───────────────────────────────────────────────────────────────────────

def profile_node(state: AgentState) -> AgentState:
    """
    Fetches GitHub (live via GitHub API) and LinkedIn (from config.yaml)
    and populates state["profile_context"] for bchat_node.
    """
    t0 = perf_counter()

    github_ctx   = _fetch_github()
    linkedin_ctx = _format_linkedin()

    sections        = [s for s in [github_ctx, linkedin_ctx] if s]
    profile_context = "\n\n".join(sections)

    elapsed = round(perf_counter() - t0, 3)
    logger.debug(
        "profile_node | session=%s | chars=%d | %.3fs",
        state.get("session_id"), len(profile_context), elapsed,
    )

    return {
        **state,
        "profile_context": profile_context,
        "metadata": {
            **(state.get("metadata") or {}),
            "profile_seconds":       elapsed,
            "profile_context_chars": len(profile_context),
        },
    }
