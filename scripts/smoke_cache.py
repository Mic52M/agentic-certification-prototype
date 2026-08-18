"""Smoke test della cache LLM (fase 1 rate limit).

Esegue 2 run consecutive dello stesso ticket con la cache attiva e verifica:
- run 1: 3 chiamate LLM reali (planner, classifier, summarizer) → 3 MISS
- run 2: 3 cache HIT (o VERIFIED_HIT), 0 nuovi file cache
- lo stato cache_status compare nei metadata degli eventi trace

Non è un unit test: fa chiamate vere al provider (~6 chiamate Groq totali).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from src import config
from src.demo.runner import run_experiment
from src.instrumentation.llm_cache import (
    CACHE_STATUS_HIT,
    CACHE_STATUS_MISS,
    CACHE_STATUS_VERIFIED_HIT,
)


def _count_cache_statuses(exp_dir: Path) -> Counter:
    counter: Counter = Counter()
    for jsonl in (exp_dir / "runs").glob("*.jsonl"):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = json.loads(line)
            meta = ev.get("metadata") or {}
            st = meta.get("llm_cache_status")
            if st:
                counter[st] += 1
    return counter


def main() -> int:
    assert config.LLM_CACHE_ENABLED, "LLM_CACHE_ENABLED deve essere True"
    assert config.TEMPERATURE == 0.0, "smoke test valido solo a temperature=0"

    incident_id = "INC-2026-014"
    print(f"[smoke_cache] esperimento: {incident_id}, 2 run, cache ON")
    result = run_experiment(incident_id, macro_focus="control_flow", n_runs=2,
                            delay_s=0.0)
    exp_dir = Path(config.EXPERIMENTS_DIR) / result["experiment_id"]
    print(f"[smoke_cache] experiment_dir: {exp_dir}")

    counts = _count_cache_statuses(exp_dir)
    print(f"[smoke_cache] cache_status counts across all events: {dict(counts)}")

    # Il grafo emette il cache_status su 3 eventi LLM per run:
    # planner (reasoning_step + planning_span → stesso resp), classifier
    # (reasoning_step), summarizer (artifact). Quindi:
    #   run1: 4 MISS (2 planner + 1 classifier + 1 summarizer)
    #   run2: 4 HIT (o parte come VERIFIED_HIT se il campione decide di verificare)
    n_miss = counts.get(CACHE_STATUS_MISS, 0)
    n_hit = counts.get(CACHE_STATUS_HIT, 0)
    n_ver = counts.get(CACHE_STATUS_VERIFIED_HIT, 0)

    # Vincoli minimi (indipendenti dal campionamento verify):
    ok_miss = n_miss == 4         # tutti e soli gli eventi LLM di run1
    ok_run2 = (n_hit + n_ver) == 4  # tutti eventi di run2 serviti da cache o verificati
    print(f"[smoke_cache] MISS={n_miss} (atteso 4)   "
          f"HIT+VERIFIED={n_hit + n_ver} (atteso 4)   [HIT={n_hit} VERIFIED={n_ver}]")

    # Numero file cache creati = numero di fingerprint distinti (=3, uno per
    # ogni chiamata LLM del pipeline: planner/classifier/summarizer).
    cache_dir = exp_dir / "llm_cache"
    n_entries = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
    print(f"[smoke_cache] entry in cache_dir: {n_entries} (atteso 3)")

    all_ok = ok_miss and ok_run2 and n_entries == 3
    print(f"[smoke_cache] risultato: {'OK' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
