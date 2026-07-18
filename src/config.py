"""Central configuration. Reads from environment / .env, exposes plain constants.

Kept deliberately small: the demo's value is the execution trace, not config
surface area. Only GROQ_API_KEY is required; everything else has a default.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root if present (no error if missing).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- LLM / Groq ----------------------------------------------------------
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# Modello di default: openai/gpt-oss-120b (131K contesto, tool use nativo).
# Il precedente qwen/qwen3-32b è stato deprecato da Groq; alternative valide
# sono qwen/qwen3.6-27b e llama-3.3-70b-versatile. Override via env MODEL=.
MODEL: str = os.getenv("MODEL", "openai/gpt-oss-120b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

# Safety limit against runaway ReAct loops (single agent).
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "10"))

# Numero di run per esperimento nella demo multi-run (default 10).
EXPERIMENT_RUNS: int = int(os.getenv("EXPERIMENT_RUNS", "10"))
# Delay in secondi tra run consecutive (rate limit Groq).
EXPERIMENT_DELAY_S: float = float(os.getenv("EXPERIMENT_DELAY_S", "1.0"))

# --- Paths ---------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
TRACES_DIR = PROJECT_ROOT / "traces"
EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
INCIDENT_DATA_DIR = DATA_DIR / "incidents"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
TICKETS_PATH = DATA_DIR / "tickets.json"
INCIDENTS_PATH = INCIDENT_DATA_DIR / "incidents.json"
APP_LOGS_PATH = INCIDENT_DATA_DIR / "app_logs.json"
METRICS_PATH = INCIDENT_DATA_DIR / "metrics.json"
POSTMORTEMS_PATH = INCIDENT_DATA_DIR / "postmortems.json"


def require_api_key() -> str:
    """Fail fast with a readable message if the key is missing."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY non impostata. Copia .env.example in .env e inserisci "
            "la tua chiave Groq (https://console.groq.com/keys)."
        )
    return GROQ_API_KEY
