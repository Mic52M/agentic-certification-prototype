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
# Groq's model id for Qwen 3 32B. (The paper refers to it as "Qwen 3 32B".)
MODEL: str = os.getenv("MODEL", "qwen/qwen3-32b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

# Safety limit against runaway ReAct loops (single agent).
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "10"))

# --- Paths ---------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
TRACES_DIR = PROJECT_ROOT / "traces"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge_base.json"
TICKETS_PATH = DATA_DIR / "tickets.json"


def require_api_key() -> str:
    """Fail fast with a readable message if the key is missing."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY non impostata. Copia .env.example in .env e inserisci "
            "la tua chiave Groq (https://console.groq.com/keys)."
        )
    return GROQ_API_KEY
