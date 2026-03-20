# config_loader.py
# Loads config.yaml once at startup. All other files import CONFIG from here.
# • Expands ${VAR} placeholders from .env / environment.
# • Validates that all required top-level sections are present.
# • Config path can be overridden via CONFIG_PATH env var.

import logging
import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REQUIRED_SECTIONS = [
    "app", "persona", "llm", "memory",
    "neo4j", "server", "ui", "telegram",
]


def _expand_env_vars(value: object) -> object:
    """Recursively replace ${VAR} placeholders with os.environ values."""
    if isinstance(value, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.getenv(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def _validate(config: dict) -> None:
    """Raise clearly if any required section is missing."""
    missing = [s for s in REQUIRED_SECTIONS if s not in config]
    if missing:
        raise KeyError(
            f"config.yaml is missing required section(s): {missing}. "
            "Check config.yaml against config.yaml.example."
        )


def load_config(path: str | None = None) -> dict:
    """
    Load, expand, and validate config.yaml.
    Path priority: argument → CONFIG_PATH env var → ./config.yaml
    """
    resolved = Path(path or os.getenv("CONFIG_PATH", "config.yaml"))
    if not resolved.exists():
        raise FileNotFoundError(
            f"Config file not found: {resolved.absolute()}\n"
            "Set CONFIG_PATH env var or place config.yaml in the working directory."
        )

    with open(resolved) as f:
        raw = yaml.safe_load(f)

    config = _expand_env_vars(raw)
    _validate(config)

    logger.debug("Config loaded from %s", resolved.absolute())
    return config


# Singleton — imported everywhere as `from config_loader import CONFIG`
CONFIG: dict = load_config()
