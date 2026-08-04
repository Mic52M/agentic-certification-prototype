"""Metriche di dettaglio per la macro Behavioural.

Gemello di `cf_metrics.py`. Ogni funzione trasforma dati grezzi estratti
dalla trace in un dict serializzabile pensato per essere consumato dalla UI
(schema Cosa/Come/Dati + eventuale valore/CI).

Nessuna funzione emette un giudizio finale: le classificazioni tri-livello
(coherent/acceptable/unacceptable) dipendono dalle *soglie dichiarate* in
`src/demo/behavioural_policy.py` — mantenerle in un modulo separato è
deliberato, così la policy resta ispezionabile ex ante.

Radici in letteratura:
- Trajectory evaluation (Confident AI, LangChain): C1..C4 come pattern.
- Groundedness / context adherence (RAGAS): base per C2.
- Statistical Model Checking (Legay et al. 2010) + Wilson score
  (Brown/Cai/DasGupta 2001): base per l'aggregato cross-run con CI.
- Comportamento accettabile (allineamento 2026-07-29): la triade
  coherent/acceptable/unacceptable come specifica dichiarata.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .cf_metrics import stats, wilson_interval


# =========================================================================
# C2 · Coerenza state ↔ output — con verdetto tri-livello
# =========================================================================
def c2_details(per_run: dict[str, dict[str, Any]],
               classify_fn) -> dict[str, Any]:
    """Metriche di dettaglio per C2.

    per_run: {run_id: {state_key_fields, fields_covered_in_output,
                        fields_missing_from_output, final_output_excerpt}}
    classify_fn: funzione coverage -> "coherent"|"acceptable"|"unacceptable".
                 Iniettata (non importata) per tenere questo modulo
                 disaccoppiato dalla policy — la policy dichiarata vive
                 in src/demo/behavioural_policy.py e viene passata dal runner.
    """
    n_runs = len(per_run)
    verdicts: Counter = Counter()
    coverages: list[float] = []
    per_run_out: dict[str, dict[str, Any]] = {}

    for run_id, r in per_run.items():
        fields = r.get("state_key_fields") or {}
        covered = r.get("fields_covered_in_output") or []
        missing = r.get("fields_missing_from_output") or []
        # denominatore = campi effettivamente valorizzati nello stato
        # consolidato (se la classification è None non conta come "missing")
        denom = sum(1 for f in ("classification", "priority", "affected_service")
                    if fields.get(f))
        coverage = (len(covered) / denom) if denom else 0.0
        verdict = classify_fn(coverage)
        verdicts[verdict] += 1
        coverages.append(coverage)
        per_run_out[run_id] = {
            "coverage": coverage,
            "denom": denom,
            "covered": list(covered),
            "missing": list(missing),
            "verdict": verdict,
        }

    # Aggregato cross-run: quanto spesso il sistema resta almeno "acceptable"
    # (proxy statistical model checking). Wilson CI 95% per robustezza a N piccolo.
    n_ok = verdicts["coherent"] + verdicts["acceptable"]
    wilson_ok = wilson_interval(n_ok, n_runs)
    n_coh = verdicts["coherent"]
    wilson_coherent = wilson_interval(n_coh, n_runs)

    return {
        "C2_1_verdict_distribution": {
            "label": "Verdetto per run (triade)",
            "root": "specifica accettabile (allineamento 2026-07-29)",
            "question": "Quante run sono coerenti, quante accettabili, quante inaccettabili?",
            "distribution": dict(verdicts),
            "n_runs": n_runs,
        },
        "C2_2_coverage_stats": {
            "label": "Coverage (state ↔ output)",
            "root": "groundedness / context adherence (RAGAS)",
            "question": "Quale frazione dei campi chiave dello stato compare nell'output?",
            "stats": stats(coverages),
            "per_run": {rid: v["coverage"] for rid, v in per_run_out.items()},
        },
        "C2_3_acceptable_rate": {
            "label": "Tasso di comportamento almeno accettabile (con IC 95%)",
            "root": "statistical model checking · Wilson score interval",
            "question": "Con quale probabilità il sistema produce output almeno accettabile?",
            "value": wilson_ok["p"],
            "format": "pct",
            "ci_lo": wilson_ok["lo"],
            "ci_hi": wilson_ok["hi"],
            "successes": n_ok,
            "n_runs": n_runs,
            "note": "'Successo' = verdetto in {coherent, acceptable}. "
                    "IC 95% con Wilson score: robusto anche con N piccolo.",
        },
        "C2_4_coherent_rate": {
            "label": "Tasso di comportamento pienamente coerente (con IC 95%)",
            "root": "statistical model checking · Wilson score interval",
            "question": "Con quale probabilità il sistema produce output pienamente coerente (100% campi)?",
            "value": wilson_coherent["p"],
            "format": "pct",
            "ci_lo": wilson_coherent["lo"],
            "ci_hi": wilson_coherent["hi"],
            "successes": n_coh,
            "n_runs": n_runs,
        },
        "per_run_verdicts": per_run_out,
    }
