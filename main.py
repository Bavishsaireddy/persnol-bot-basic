# main.py
# Single entry point for the entire Bavish Bot.
# Reads everything from config.yaml — zero hardcoding.
#
# Usage:
#   python main.py                 → backend + UI  (default)
#   python main.py --mode backend  → API server only
#   python main.py --mode ui       → Streamlit UI only (backend must be running)

import argparse
import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

from config_loader import CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config aliases ────────────────────────────────────────────
_app     = CONFIG["app"]
_persona = CONFIG["persona"]
_server  = CONFIG["server"]
_ui      = CONFIG["ui"]
_llm     = CONFIG["llm"]
_mem     = CONFIG["memory"]
_neo4j   = CONFIG["neo4j"]

HERE        = Path(__file__).parent
BACKEND_URL = f"http://localhost:{_server['port']}"
UI_URL      = f"http://localhost:{_ui['port']}"


# ── Health polling ────────────────────────────────────────────

def _wait_for_backend() -> bool:
    timeout = _server["startup_timeout"]
    for _ in range(timeout * 2):
        try:
            if requests.get(f"{BACKEND_URL}/", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ── Process launchers ─────────────────────────────────────────

def _start_backend() -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "uvicorn", "gateway:app",
        "--host",      _server["host"],
        "--port",      str(_server["port"]),
        "--log-level", _server["log_level"],
    ]
    if _server.get("reload"):
        cmd.append("--reload")
    logger.info("Backend cmd: %s", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=HERE)


def _start_ui() -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(HERE / "ui.py"),
        "--server.port",              str(_ui["port"]),
        "--server.headless",          str(_ui.get("headless", False)).lower(),
        "--browser.gatherUsageStats", "false",
    ]
    logger.info("UI cmd: %s", " ".join(cmd))
    return subprocess.Popen(cmd, cwd=HERE)


# ── Runner ────────────────────────────────────────────────────

def run(mode: str) -> None:
    procs: list[subprocess.Popen] = []

    def _shutdown(sig=None, frame=None) -> None:
        logger.info("Shutting down all processes...")
        for p in procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── startup banner ────────────────────────────────────────
    sep = "─" * 52
    print(f"\n{sep}")
    print(f"  {_persona['name']}  —  AI Agent  v{_app['version']}")
    print(f"  LLM    : {_llm['provider']} / {_llm['model']}")
    print(f"  Memory : {_mem['backend']}  →  {_mem['db_path']}")
    print(f"  Neo4j  : {'enabled' if _neo4j.get('enabled') else 'disabled'}")
    print(f"{sep}\n")

    if mode in ("all", "backend"):
        logger.info("Starting backend  →  %s", BACKEND_URL)
        procs.append(_start_backend())

    if mode in ("all", "ui"):
        if mode == "all":
            logger.info("Waiting for backend (timeout=%ds)…", _server["startup_timeout"])
            if not _wait_for_backend():
                logger.error("Backend did not become ready in time. Aborting.")
                _shutdown()
            logger.info("Backend ready ✓")

        logger.info("Starting UI  →  %s", UI_URL)
        procs.append(_start_ui())

    print(f"\nAll services running. Press Ctrl+C to stop.\n")

    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    logger.error("Process %d exited unexpectedly. Shutting down.", p.pid)
                    _shutdown()
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown()


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"{_persona['name']} AI Agent — unified runner"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "backend", "ui"],
        default="all",
        help="all = backend + UI (default) | backend = API only | ui = UI only",
    )
    args = parser.parse_args()
    run(args.mode)
