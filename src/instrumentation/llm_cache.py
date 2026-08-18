"""Cache deterministica delle risposte LLM per gli esperimenti multi-run.

Motivazione (ricerca, non ingegneria)
-------------------------------------
Il framework di certificazione richiede batch grandi (N=500+ run dello stesso
ticket) per stimare le metriche behavioural con intervalli di confidenza
significativi. A `temperature=0` il provider LLM restituisce risposte identiche
bit a bit per la stessa tripla (model, system_prompt, user_prompt): pagare N
chiamate reali quando il risultato osservabile è indistinguibile da una
memoizzazione è puro spreco di token/day, senza alcun guadagno scientifico.

Regola dura, non convenzionale
------------------------------
La cache è attiva **se e solo se `temperature == 0.0`**. Con temperature > 0 la
risposta è stocastica per definizione, e servirla da cache falsificherebbe la
misura di varianza comportamentale (C4). Questa proprietà è codificata nei
metodi `get()` e `put()`: non è un flag da ricordarsi di disattivare, è una
condizione strutturale. In scenari di studio della varianza (`temperature>0`,
ticket ambigui, perturbazioni) la cache diventa automaticamente un no-op.

Trasparenza scientifica
-----------------------
Ogni risposta è marcata con un `cache_status` che finisce nei metadata degli
eventi trace, così l'aggregato di esperimento può sempre dichiarare
`real_calls / cache_hits / verified_hits`. Il campionamento di verifica
(gestito nel `LLMClient`) rilancia periodicamente la chiamata reale per
detectare drift lato provider — se una risposta cached diverge dal risultato
attuale, il codice fallisce forte anziché silenzioso.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path


# Valori possibili per LLMResponse.cache_status
CACHE_STATUS_MISS = "miss"                # cache attiva, entry non trovata → chiamata reale
CACHE_STATUS_HIT = "hit"                  # cache attiva, entry servita (nessuna chiamata reale)
CACHE_STATUS_VERIFIED_HIT = "verified_hit"  # cache attiva, hit + ri-chiamata di verifica confermata
CACHE_STATUS_DISABLED = "disabled"        # cache non presente o temperature != 0


def fingerprint(model: str, system_prompt: str, user_prompt: str,
                temperature: float) -> str:
    """Hash sha256 stabile della tripla (model, prompts, temperature).

    Non include timestamp, run_id, experiment_id: due chiamate identiche in
    contesti diversi devono collidere sulla stessa entry (è il punto).
    """
    payload = json.dumps(
        {
            "model": model,
            "system": system_prompt,
            "user": user_prompt,
            "temperature": temperature,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class CachedEntry:
    """Contenuto serializzato di una entry di cache."""

    text: str
    raw_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # componenti del fingerprint, replicati nel file per audit ex-post
    model: str
    temperature: float
    # provenance
    written_at: float


class LLMCache:
    """File-per-hash cache; una entry = un file JSON leggibile.

    Il layout su disco è deliberatamente ispezionabile senza tooling:

        <cache_dir>/
          <sha256>.json   # entry per fingerprint
    """

    def __init__(self, cache_dir: Path) -> None:
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_deterministic(temperature: float) -> bool:
        # Regola dura: cache abilitata solo a temperature=0.0.
        # Il confronto con float è intenzionalmente stretto: qualunque valore
        # > 0 introduce stocasticità e disabilita la cache.
        return temperature == 0.0

    def _path(self, fp: str) -> Path:
        return self.dir / f"{fp}.json"

    def get(self, model: str, system_prompt: str, user_prompt: str,
            temperature: float) -> CachedEntry | None:
        """Ritorna la entry se presente e la cache è attiva per questa temperatura."""
        if not self._is_deterministic(temperature):
            return None
        p = self._path(fingerprint(model, system_prompt, user_prompt, temperature))
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return CachedEntry(**d)
        except (json.JSONDecodeError, TypeError):
            # entry corrotta: la trattiamo come miss (verrà sovrascritta).
            return None

    def put(self, model: str, system_prompt: str, user_prompt: str,
            temperature: float, *, text: str, raw_text: str,
            prompt_tokens: int, completion_tokens: int,
            total_tokens: int) -> None:
        """Scrive la entry se la cache è attiva per questa temperatura."""
        if not self._is_deterministic(temperature):
            return
        fp = fingerprint(model, system_prompt, user_prompt, temperature)
        payload = {
            "text": text,
            "raw_text": raw_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model,
            "temperature": temperature,
            "written_at": time.time(),
        }
        self._path(fp).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def size(self) -> int:
        """Numero di entry attualmente cachate (utile per gli aggregati)."""
        return sum(1 for _ in self.dir.glob("*.json"))
