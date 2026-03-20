# __init__.py
# Package marker. All metadata is driven by config.yaml — nothing hardcoded here.

from config_loader import CONFIG

__version__ = CONFIG["app"]["version"]
__agent__   = CONFIG["persona"]["name"]
__model__   = CONFIG["llm"]["model"]
__backend__ = f"http://localhost:{CONFIG['server']['port']}"
