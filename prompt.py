# prompt.py
# Builds the Claude system prompt from config.yaml → persona.
# Shared by both mcp_server.py and bchat_node.py — no circular dependency.

from config_loader import CONFIG

_persona = CONFIG["persona"]


def build_system_prompt(memory_context: str = "", code_context: str = "") -> str:
    """
    Assembles the full system prompt from persona config.
    Optionally appends memory context and Neo4j code context.
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

    if memory_context:
        prompt += f"\n\n## Recent conversation context\n{memory_context}"
    if code_context:
        prompt += f"\n\n## Relevant code from your GitHub repo\n{code_context}"

    return prompt
