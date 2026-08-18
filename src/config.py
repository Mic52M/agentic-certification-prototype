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

# --- LLM: provider e chiavi ----------------------------------------------
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
CEREBRAS_API_KEY: str | None = os.getenv("CEREBRAS_API_KEY")

# Ordine di preferenza dei provider (fallback su rate-limit del primo).
# I provider senza chiave vengono automaticamente saltati dal LLMClient.
PROVIDER_PRIORITY: list[str] = [
    p.strip() for p in os.getenv("PROVIDER_PRIORITY", "groq,cerebras").split(",")
    if p.strip()
]

# Modello CANONICO (nome indipendente dal provider). Il client fa mapping:
#   canonico "gpt-oss-120b" → Groq: "openai/gpt-oss-120b", Cerebras: "gpt-oss-120b".
# Modello principale: usato da tutti gli agenti se non c'è override.
# Deve esistere su TUTTI i provider abilitati per garantire il fallback.
MODEL: str = os.getenv("MODEL", "gpt-oss-120b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

# --- Data-flow mitigation --------------------------------------------------
# Se True, il layer di persistenza applica un redattore PII per-canale
# (categorie non ammesse dalla ALLOWED_SET_A vengono mascherate prima di
# scrivere gli eventi JSONL e prima di notificare i sink UI). Le occorrenze
# mascherate finiscono nei metadata dell'evento come `pii_redaction_hits`,
# in modo che l'aggregator possa dichiarare quante violazioni sono state
# mitigate senza dover ri-scansionare il testo (che ora è già mascherato).
# Impostare DATAFLOW_REDACTION_ENABLED=false per esperimenti "raw" utili
# a documentare la detection in assenza di mitigation.
DATAFLOW_REDACTION_ENABLED: bool = os.getenv(
    "DATAFLOW_REDACTION_ENABLED", "true"
).lower() in {"1", "true", "yes"}

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

# Dataset della demo attuale (incident triage) in data/demo/.
DEMO_DATA_DIR = DATA_DIR / "demo"
INCIDENTS_PATH = DEMO_DATA_DIR / "incidents.json"
APP_LOGS_PATH = DEMO_DATA_DIR / "app_logs.json"
METRICS_PATH = DEMO_DATA_DIR / "metrics.json"
POSTMORTEMS_PATH = DEMO_DATA_DIR / "postmortems.json"

# Dataset del vecchio prototipo (mail troubleshooting) in data/legacy/.
LEGACY_DATA_DIR = DATA_DIR / "legacy"
KNOWLEDGE_BASE_PATH = LEGACY_DATA_DIR / "knowledge_base.json"
TICKETS_PATH = LEGACY_DATA_DIR / "tickets.json"


def require_api_key() -> str:
    """Compat: la vecchia utility ritorna la Groq key se presente, altrimenti
    la Cerebras key. Il client multi-provider verifica indipendentemente
    l'availability di ogni backend; questa funzione resta per il codice che
    chiedeva una singola chiave in modo esplicito.
    """
    if GROQ_API_KEY:
        return GROQ_API_KEY
    if CEREBRAS_API_KEY:
        return CEREBRAS_API_KEY
    raise RuntimeError(
        "Nessuna chiave provider impostata. Copia .env.example in .env e "
        "inserisci almeno una tra GROQ_API_KEY e CEREBRAS_API_KEY."
    )
