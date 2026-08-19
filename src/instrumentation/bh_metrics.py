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

import math
import re
from collections import Counter
from itertools import combinations
from typing import Any

from .cf_metrics import stats, wilson_interval


def _entropy_norm(counter: Counter) -> float:
    """Entropia di Shannon normalizzata in [0,1] su una distribuzione categoriale.

    0.0 = distribuzione degenere (tutto uguale). 1.0 = massima varianza
    (uniforme sul supporto osservato).
    """
    total = sum(counter.values())
    if total <= 1 or len(counter) <= 1:
        return 0.0
    probs = [c / total for c in counter.values()]
    H = -sum(p * math.log2(p) for p in probs if p > 0)
    Hmax = math.log2(len(counter))
    return H / Hmax if Hmax > 0 else 0.0


def _cv(values: list[float]) -> float | None:
    """Coefficient of variation = σ / |μ|. Adimensionale, confrontabile
    fra grandezze di scala diversa (durata ms vs lunghezza char).
    None se μ==0 o N<2.
    """
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    if m == 0:
        return None
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var) / abs(m)


def _mean_pairwise_jaccard(sets: list[set[str]]) -> float | None:
    """Jaccard medio su tutte le coppie di run. 1.0 = tutti identici,
    0.0 = tutti disgiunti. None se N<2 o tutti i set vuoti.
    """
    if len(sets) < 2:
        return None
    scores: list[float] = []
    for a, b in combinations(sets, 2):
        if not a and not b:
            continue
        u = a | b
        scores.append(len(a & b) / len(u) if u else 1.0)
    return sum(scores) / len(scores) if scores else None


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


# =========================================================================
# C3 · Sequenza decisioni — con check di coerenza pairwise + triade
# =========================================================================
def _tokens(s: str) -> set[str]:
    """Token informativi minuscoli, len >= 4."""
    return {w for w in re.findall(r"\w+", (s or "").lower()) if len(w) >= 4}


def _extract_by_agent_label(decisions: list[dict],
                            agent: str, label: str) -> dict | None:
    """Trova la (prima) decisione emessa da un agente con una certa label."""
    for d in decisions:
        if d.get("agent") == agent and (d.get("meta") or {}).get("label") == label:
            return d
    return None


def _service_of(decision: dict | None) -> str | None:
    """Estrae il campo 'service' dai meta di una decisione investigatore."""
    if not decision:
        return None
    meta = decision.get("meta") or {}
    return meta.get("service") or meta.get("choice")


def _check1_planner_vs_investigators(decisions: list[dict],
                                     symptom_map: dict) -> dict:
    """CHECK 1: planner ↔ investigatori.

    Se il planner ha deciso affected_service = X, gli investigatori
    (log_investigator, metrics_analyst) hanno investigato X?
    Il check è N/A se il planner non ha deciso il servizio o se nessun
    investigatore è stato attivato.
    """
    planner = _extract_by_agent_label(decisions, "planner", "affected_service")
    planned_service = ((planner or {}).get("meta") or {}).get("choice") if planner else None
    if not planner or not planned_service or planned_service == "unknown":
        return {"applicable": False,
                "reason": "planner non ha deciso il servizio",
                "planned": planned_service}

    investigators = []
    for agent, label in (("log_investigator", "log_depth"),
                         ("metrics_analyst", "critical_component")):
        d = _extract_by_agent_label(decisions, agent, label)
        if d is not None:
            investigators.append((agent, d))
    if not investigators:
        return {"applicable": False,
                "reason": "nessun investigatore attivato",
                "planned": planned_service}

    # Un investigatore è coerente se il campo 'service' nei suoi meta
    # combacia col servizio pianificato. Il metrics_analyst emette
    # critical_component (es. 'smtp-relay-2') su un servizio (es.
    # 'mail-gateway'): il match si fa sui meta.service.
    mismatches = []
    for agent, d in investigators:
        svc = ((d.get("meta") or {}).get("service"))
        if svc and svc != planned_service:
            mismatches.append({"agent": agent, "expected": planned_service,
                               "actual": svc})
    consistent = len(mismatches) == 0
    return {
        "applicable": True,
        "consistent": consistent,
        "planned": planned_service,
        "investigators": [a for a, _ in investigators],
        "mismatches": mismatches,
    }


def _check2_planner_vs_classifier(decisions: list[dict],
                                  symptom_map: dict) -> dict:
    """CHECK 2: planner ↔ classifier.

    Il primary_symptom identificato dal planner e la classification finale
    del classifier sono compatibili (secondo la policy dichiarata)?
    Il check è N/A se planner o classifier non hanno prodotto la decisione.
    """
    planner = _extract_by_agent_label(decisions, "planner", "affected_service")
    classifier = _extract_by_agent_label(decisions, "classifier", "classification")
    if not planner or not classifier:
        return {"applicable": False,
                "reason": "manca planner o classifier"}
    symptom = ((planner.get("payload_redacted") or {})
               .get("inputs", {}).get("primary_symptom")
               or (planner.get("meta") or {}).get("primary_symptom") or "")
    classification = (classifier.get("meta") or {}).get("choice") or ""
    if not symptom:
        # fallback: usa il summary della decisione planner
        symptom = str(planner.get("summary") or "")
    sym_tokens = _tokens(symptom)
    if not sym_tokens or not classification:
        return {"applicable": False, "reason": "sintomo o classification vuoti",
                "symptom": symptom, "classification": classification}

    # Cerca almeno una keyword del sintomo mappata a una famiglia che
    # contenga la classification scelta.
    compatible_classes: set[str] = set()
    matched_keys: list[str] = []
    for key, classes in symptom_map.items():
        if key in sym_tokens or any(key in t for t in sym_tokens):
            compatible_classes |= classes
            matched_keys.append(key)
    if not matched_keys:
        return {"applicable": False,
                "reason": "nessuna keyword del sintomo riconosciuta",
                "symptom": symptom, "classification": classification}

    consistent = classification in compatible_classes
    return {
        "applicable": True,
        "consistent": consistent,
        "symptom": symptom[:120],
        "classification": classification,
        "matched_symptom_keys": matched_keys,
        "compatible_classifications": sorted(compatible_classes),
    }


def _check3_classifier_vs_postmortems(decisions: list[dict],
                                      pm_events: list[dict],
                                      class_to_tags: dict) -> dict:
    """CHECK 3: classifier ↔ postmortem retriever.

    I postmortem selezionati hanno tag semanticamente compatibili con la
    classification scelta? Il check è N/A se manca la classification o se
    nessun postmortem è stato recuperato.
    """
    classifier = _extract_by_agent_label(decisions, "classifier", "classification")
    if not classifier:
        return {"applicable": False, "reason": "manca classification"}
    classification = (classifier.get("meta") or {}).get("choice") or ""
    expected_tags = class_to_tags.get(classification, set())
    if not classification or not expected_tags:
        return {"applicable": False,
                "reason": "classification vuota o senza tag attesi",
                "classification": classification}

    pms = pm_events   # lista di dict {id, tags} raccolti dalla trace
    if not pms:
        return {"applicable": False,
                "reason": "nessun postmortem correlato recuperato",
                "classification": classification}

    # Matching bidirezionale: un tag di postmortem 'db-pool' considera match
    # con l'expected 'db' (perché 'db' è sotto-stringa di 'db-pool'), e
    # simmetricamente 'auth' matcha un expected 'auth-token'. Questo evita
    # fail lessicali su varianti dello stesso concetto, senza allargare la
    # semantica della policy — la policy resta dichiarata, il matching resta
    # ispezionabile (nel campo 'overlap' compaiono le coppie 'pm~expected').
    exp_lower = {e.lower() for e in expected_tags}

    def _pair_matches(pm_tags: set[str]) -> list[str]:
        pairs: list[str] = []
        for t in pm_tags:
            for e in exp_lower:
                if e == t or e in t or t in e:
                    pairs.append(t if e == t else f"{t}~{e}")
                    break
        return sorted(pairs)

    hits: list[dict] = []
    for pm in pms:
        pm_tags = {t.lower() for t in (pm.get("tags") or [])}
        overlap = _pair_matches(pm_tags)
        hits.append({"id": pm.get("id"), "tags": sorted(pm_tags),
                     "overlap": overlap})
    at_least_one = any(h["overlap"] for h in hits)
    return {
        "applicable": True,
        "consistent": at_least_one,
        "classification": classification,
        "expected_tags": sorted(expected_tags),
        "postmortem_hits": hits,
    }


def c3_details(per_run_decisions: dict[str, list[dict]],
               per_run_postmortems: dict[str, list[dict]],
               classify_fn,
               symptom_map: dict,
               class_to_tags: dict) -> dict[str, Any]:
    """Metriche di dettaglio per C3 con verdetto tri-livello.

    per_run_decisions: {run_id: [ decision_point, ... ]}
    per_run_postmortems: {run_id: [ {id, tags}, ... ]} — dai tool_result
        della sonda postmortem_retriever.
    classify_fn: consistency -> "coherent"|"acceptable"|"unacceptable".
    symptom_map, class_to_tags: policy dichiarate.
    """
    verdicts: Counter = Counter()
    consistencies: list[float] = []
    per_run_out: dict[str, dict[str, Any]] = {}

    for run_id, decisions in per_run_decisions.items():
        pm_events = per_run_postmortems.get(run_id, [])
        c1 = _check1_planner_vs_investigators(decisions, symptom_map)
        c2 = _check2_planner_vs_classifier(decisions, symptom_map)
        c3 = _check3_classifier_vs_postmortems(decisions, pm_events, class_to_tags)
        results = {"planner_vs_investigators": c1,
                   "planner_vs_classifier": c2,
                   "classifier_vs_postmortems": c3}

        applicable = [r for r in results.values() if r.get("applicable")]
        n_applicable = len(applicable)
        n_passed = sum(1 for r in applicable if r.get("consistent"))
        consistency = (n_passed / n_applicable) if n_applicable else 0.0
        verdict = classify_fn(consistency) if n_applicable else "unacceptable"

        verdicts[verdict] += 1
        consistencies.append(consistency)
        per_run_out[run_id] = {
            "consistency": consistency,
            "n_applicable": n_applicable,
            "n_passed": n_passed,
            "verdict": verdict,
            "checks": results,
        }

    n_runs = len(per_run_decisions)
    n_ok = verdicts["coherent"] + verdicts["acceptable"]
    wilson_ok = wilson_interval(n_ok, n_runs)
    n_coh = verdicts["coherent"]
    wilson_coherent = wilson_interval(n_coh, n_runs)

    return {
        "C3_1_verdict_distribution": {
            "label": "Verdetto per run (triade)",
            "root": "specifica accettabile (allineamento 2026-07-29)",
            "question": "Quante run sono coerenti, quante accettabili, quante inaccettabili?",
            "distribution": dict(verdicts),
            "n_runs": n_runs,
        },
        "C3_2_consistency_stats": {
            "label": "Consistency (frazione check superati)",
            "root": "intention-behavior consistency (letteratura multi-agent LLM)",
            "question": "Quanti dei check pairwise di coerenza fra decisioni successive sono superati?",
            "stats": stats(consistencies),
            "per_run": {rid: v["consistency"] for rid, v in per_run_out.items()},
        },
        "C3_3_acceptable_rate": {
            "label": "Tasso di comportamento almeno accettabile (con IC 95%)",
            "root": "statistical model checking · Wilson score interval",
            "question": "Con quale probabilità la sequenza di decisioni è almeno accettabile?",
            "value": wilson_ok["p"],
            "format": "pct",
            "ci_lo": wilson_ok["lo"],
            "ci_hi": wilson_ok["hi"],
            "successes": n_ok,
            "n_runs": n_runs,
            "note": "'Successo' = verdetto in {coherent, acceptable}. IC Wilson 95%.",
        },
        "C3_4_coherent_rate": {
            "label": "Tasso di comportamento pienamente coerente (con IC 95%)",
            "root": "statistical model checking · Wilson score interval",
            "question": "Con quale probabilità tutti i check pairwise sono superati?",
            "value": wilson_coherent["p"],
            "format": "pct",
            "ci_lo": wilson_coherent["lo"],
            "ci_hi": wilson_coherent["hi"],
            "successes": n_coh,
            "n_runs": n_runs,
        },
        "per_run_verdicts": per_run_out,
    }


# =========================================================================
# C4 · Stabilità comportamentale su N run — risoluzione multi-asse
# =========================================================================
def c4_details(
    *,
    node_signatures: Counter,          # sequenza agenti dedup
    edge_signatures: Counter,          # sequenza handoff ordinati
    tool_signatures: Counter,          # sequenza tool call ordinati
    final_classification: Counter,
    final_priority: Counter,
    final_affected_service: Counter,
    step_counts: list[int],            # n step per run
    output_lengths: list[int],         # len(final_output_text) per run
    durations_ms: list[float],         # durata totale run
    postmortem_sets: list[set[str]],   # id postmortem selezionati per run
) -> dict[str, Any]:
    """Metriche di dettaglio C4 a risoluzione multi-asse.

    Rationale: la vecchia C4 osservava solo la sequenza di agenti attivati
    (sempre uguale a temp=0 in topologia deterministica → entropia sempre 0).
    Ma a temp=0 c'è varianza reale su altri assi (batch composition + FP
    non-associativity lato provider): affected_service scelto dal planner,
    tool sequence, classification finale, insieme postmortem, lunghezza
    output, durata totale. Le sonde di questa funzione la esplicitano.

    Ogni sotto-metrica dichiara nel proprio dict:
    - `label`, `root`, `question` (schema comune al framework);
    - `axis` (nome asse di varianza), `format` (int/pct/ratio/dist);
    - il valore osservato + eventuale entropia normalizzata / CV / Jaccard.
    """
    n_runs = len(step_counts)

    def _key_to_str(k: Any) -> str:
        # Le firme edge/tool sono tuple; convertiamole in stringhe leggibili
        # per la serializzazione JSON (le chiavi JSON devono essere scalari)
        # e per la lettura nella dashboard.
        if isinstance(k, tuple):
            if not k:
                return "∅"
            if k and isinstance(k[0], tuple):
                return " → ".join(f"{a}→{b}" for a, b in k)
            return " → ".join(str(x) for x in k)
        return str(k)

    def _dist_block(axis: str, counter: Counter, root: str,
                    question: str) -> dict[str, Any]:
        distribution = {_key_to_str(k): c for k, c in counter.most_common()}
        return {
            "label": f"Distribuzione + entropia — {axis}",
            "root": root,
            "question": question,
            "axis": axis,
            "distribution": distribution,
            "entropy_norm": _entropy_norm(counter),
            "n_distinct": len(counter),
            "n_runs": n_runs,
            "format": "dist",
        }

    def _cv_block(axis: str, values: list[float], root: str,
                  question: str, unit: str) -> dict[str, Any]:
        s = stats(values)
        return {
            "label": f"Coefficiente di variazione — {axis}",
            "root": root,
            "question": question,
            "axis": axis,
            "cv": _cv([float(v) for v in values]),
            "mean": s.get("mean"),
            "stdev": s.get("stdev"),
            "min": s.get("min"),
            "max": s.get("max"),
            "unit": unit,
            "n_runs": n_runs,
            "format": "ratio",
        }

    return {
        "C4_1_signature_nodes": _dist_block(
            "trajectory_nodes", node_signatures,
            "process mining · trace variants (nodi)",
            "Le run visitano la stessa sequenza deduplicata di agenti?"),
        "C4_2_signature_edges": _dist_block(
            "trajectory_edges", edge_signatures,
            "process mining · trace variants (edge-level)",
            "Le run seguono la stessa sequenza ordinata di handoff?"),
        "C4_3_tool_sequences": _dist_block(
            "tool_sequences", tool_signatures,
            "process mining · trace variants (tool-level)",
            "Le run invocano gli stessi tool nello stesso ordine?"),
        "C4_4_final_classification": _dist_block(
            "final_classification", final_classification,
            "output diversity (agentic evaluation)",
            "La classification finale è stabile fra run?"),
        "C4_5_final_priority": _dist_block(
            "final_priority", final_priority,
            "output diversity (agentic evaluation)",
            "La priority finale è stabile fra run?"),
        "C4_6_affected_service": _dist_block(
            "affected_service", final_affected_service,
            "decision diversity (planner-level)",
            "Il planner sceglie sempre lo stesso servizio come impattato?"),
        "C4_7_step_count_cv": _cv_block(
            "step_count", [float(x) for x in step_counts],
            "process observability · step efficiency",
            "Il numero di step per run è stabile?", "steps"),
        "C4_8_output_length_cv": _cv_block(
            "output_length", [float(x) for x in output_lengths],
            "output stability (agentic evaluation)",
            "La lunghezza dell'output finale è stabile?", "chars"),
        "C4_9_duration_cv": _cv_block(
            "run_duration", [float(x) for x in durations_ms],
            "latency stability (pipeline observability)",
            "La durata end-to-end della run è stabile?", "ms"),
        "C4_10_postmortem_stability": {
            "label": "Stabilità set postmortem (Jaccard medio pairwise)",
            "root": "retrieval stability",
            "question": "Le run selezionano lo stesso insieme di postmortem?",
            "axis": "postmortem_selection",
            "mean_pairwise_jaccard": _mean_pairwise_jaccard(postmortem_sets),
            "n_runs": n_runs,
            "n_nonempty": sum(1 for s in postmortem_sets if s),
            "format": "ratio",
        },
    }
