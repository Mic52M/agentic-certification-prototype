"""Metriche di dettaglio per la macro Control Flow.

Ogni evidenza (A1..A4) è scomposta in metriche puntuali, ciascuna con una
radice esplicita in letteratura. Il modulo è deliberatamente separato
dall'aggregator per tenere leggibile la definizione delle metriche.

Radici principali:
- *Process mining / conformance checking* (van der Aalst; Entropia,
  Polyvyanyy et al.): fitness, precision, trace variants, entropia.
- *Software testing*: branch coverage, complessità ciclomatica (McCabe).
- *Agent evaluation*: step efficiency, tool error rate, completion rate.
- *Statistical model checking*: intervalli di confidenza (Wilson score).

Nessuna metrica emette un giudizio di conformità: sono descrittori. La
soglia e il verdetto sono decisioni successive, fuori da questo modulo.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any, Iterable

TERMINALS = {"__end__", "END"}


# =========================================================================
# Utility statistiche
# =========================================================================
def stats(xs: Iterable[float]) -> dict[str, float]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "min": 0, "max": 0, "mean": 0.0, "stdev": 0.0}
    return {
        "n": len(xs),
        "min": min(xs),
        "max": max(xs),
        "mean": statistics.mean(xs),
        "stdev": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
    }


def percentile(xs: list[float], p: float) -> float:
    """Percentile lineare semplice (p in [0,1])."""
    if not xs:
        return 0.0
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    idx = p * (len(s) - 1)
    lo, hi = int(math.floor(idx)), int(math.ceil(idx))
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (idx - lo))


def entropy_norm(counter: Counter) -> float:
    """Entropia di Shannon normalizzata in [0,1].

    0 = distribuzione concentrata su un solo valore (massima prevedibilità);
    1 = distribuzione uniforme (massima varianza).
    """
    total = sum(counter.values())
    if total <= 1 or len(counter) <= 1:
        return 0.0
    probs = [c / total for c in counter.values()]
    h = -sum(p * math.log2(p) for p in probs if p > 0)
    hmax = math.log2(len(counter))
    return h / hmax if hmax > 0 else 0.0


def wilson_interval(successes: int, n: int, z: float = 1.96) -> dict[str, float]:
    """Intervallo di confidenza di Wilson per una proporzione.

    Preferito all'intervallo normale con N piccolo (Brown, Cai, DasGupta 2001):
    non degenera quando la proporzione è 0 o 1, come accade tipicamente in
    demo con poche run.
    """
    if n == 0:
        return {"p": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return {
        "p": p,
        "lo": max(0.0, (centre - margin) / denom),
        "hi": min(1.0, (centre + margin) / denom),
        "n": n,
    }


def _tok(s: str) -> set[str]:
    import re
    return {w for w in re.findall(r"\w+", (s or "").lower()) if len(w) >= 4}


# =========================================================================
# A1 — Decisioni dell'orchestratore
# =========================================================================
def a1_details(per_run_decisions: dict[str, list[dict]],
               declared_rules: list[dict] | None) -> dict[str, Any]:
    """Metriche di dettaglio sulle decisioni di routing.

    per_run_decisions: {run_id: [ {target, reason, alternatives, step,
                                   context_keys}, ... ]}
    """
    all_dec = [d for lst in per_run_decisions.values() for d in lst]
    n_runs = len(per_run_decisions)

    # --- A1.1 Rule activation coverage (branch coverage) ------------------
    # Una regola è "attivata" se compare almeno una volta come motivo di una
    # decisione osservata. Le regole mai attivate sono dead branches.
    reason_counter = Counter(d.get("reason", "") for d in all_dec)
    declared = declared_rules or []
    activated, dead = [], []
    for rule in declared:
        reason = str(rule.get("reason", ""))
        count = reason_counter.get(reason, 0)
        row = {"index": rule.get("index"), "target": rule.get("target"),
               "reason": reason, "activations": count}
        (activated if count > 0 else dead).append(row)
    coverage = (len(activated) / len(declared)) if declared else 0.0

    # --- A1.2 Distribuzione + entropia delle decisioni --------------------
    target_counter = Counter(d.get("target", "?") for d in all_dec)
    target_entropy = entropy_norm(target_counter)
    reason_entropy = entropy_norm(reason_counter)

    # --- A1.3 Routing determinism -----------------------------------------
    # Firma del contesto = insieme ordinato delle chiavi di stato valorizzate
    # al momento della decisione. Se a parità di firma l'orchestratore sceglie
    # sempre lo stesso target, il routing è deterministico su quel contesto.
    ctx_to_targets: dict[tuple, Counter] = {}
    for d in all_dec:
        sig = tuple(sorted(d.get("context_keys") or []))
        ctx_to_targets.setdefault(sig, Counter())[d.get("target", "?")] += 1
    n_ctx = len(ctx_to_targets)
    n_det = sum(1 for c in ctx_to_targets.values() if len(c) == 1)
    determinism = (n_det / n_ctx) if n_ctx else 1.0
    ambiguous = [
        {"context_size": len(sig), "targets": dict(c)}
        for sig, c in ctx_to_targets.items() if len(c) > 1
    ][:5]

    # --- A1.4 Branching factor --------------------------------------------
    # Quante alternative erano note e non scelte al momento della decisione.
    # 0 = decisione forzata (una sola regola vera); >0 = c'era margine.
    alt_counts = [len(d.get("alternatives") or []) for d in all_dec]
    forced = sum(1 for a in alt_counts if a == 0)

    # --- A1.5 Decisioni per run -------------------------------------------
    per_run_counts = {rid: len(lst) for rid, lst in per_run_decisions.items()}

    return {
        "A1_1_rule_coverage": {
            "label": "Rule activation coverage",
            "root": "branch coverage (software testing)",
            "question": "Quante delle regole di routing dichiarate sono state effettivamente esercitate?",
            "value": coverage,
            "format": "pct",
            "declared": len(declared),
            "activated": len(activated),
            "dead_rules": dead,
            "activated_rules": sorted(activated, key=lambda r: -r["activations"]),
        },
        "A1_2_decision_distribution": {
            "label": "Distribuzione decisioni + entropia",
            "root": "entropy-based conformance (Entropia, Polyvyanyy et al.)",
            "question": "Come si distribuiscono le decisioni sui target? Quanto è concentrato il routing?",
            "target_distribution": dict(target_counter.most_common()),
            "target_entropy_norm": target_entropy,
            "reason_entropy_norm": reason_entropy,
        },
        "A1_3_routing_determinism": {
            "label": "Routing determinism",
            "root": "conformance checking / decisione a parità di contesto",
            "question": "A parità di contesto di stato, l'orchestratore decide sempre allo stesso modo?",
            "value": determinism,
            "format": "pct",
            "n_contexts": n_ctx,
            "n_deterministic": n_det,
            "ambiguous_contexts": ambiguous,
        },
        "A1_4_branching_factor": {
            "label": "Branching factor delle decisioni",
            "root": "decision surface (agent observability)",
            "question": "Quante alternative erano disponibili quando l'orchestratore ha deciso?",
            "stats": stats(alt_counts),
            "forced_decisions": forced,
            "total_decisions": len(all_dec),
            "forced_ratio": (forced / len(all_dec)) if all_dec else 0.0,
        },
        "A1_5_decisions_per_run": {
            "label": "Decisioni per run",
            "root": "step-level agent evaluation",
            "question": "Quante decisioni servono per concludere una run?",
            "stats": stats(list(per_run_counts.values())),
            "per_run": per_run_counts,
            "n_runs": n_runs,
        },
    }


# =========================================================================
# A2 — Spans di pianificazione
# =========================================================================
def a2_details(per_run_plans: dict[str, list[dict]],
               per_run_replans: dict[str, int],
               per_run_executed_agents: dict[str, list[str]]) -> dict[str, Any]:
    """Metriche di dettaglio sulla pianificazione.

    per_run_plans: {run_id: [ {steps: [...], duration_ms: int}, ... ]}
    per_run_executed_agents: {run_id: [agent, ...]} nell'ordine di esecuzione.
    """
    all_plans = [p for lst in per_run_plans.values() for p in lst]
    lengths = [len(p.get("steps") or []) for p in all_plans]
    latencies = [p.get("duration_ms", 0) for p in all_plans]

    n_runs = len(per_run_plans)
    runs_with_replan = sum(1 for v in per_run_replans.values() if v > 0)

    # --- A2.3 Plan-execution fitness / precision ---------------------------
    # Proxy lessicale dichiarato: uno step pianificato è "coperto" se
    # condivide token informativi con il nome di un agente eseguito o con la
    # sua area (log/metriche/postmortem/classificazione/report).
    AGENT_TOKENS = {
        "reader": {"ticket", "incident", "legg", "read"},
        "planner": {"piano", "plan", "triage"},
        "log_investigator": {"log", "logs", "errori", "eventi"},
        "metrics_analyst": {"metric", "metriche", "cpu", "memoria", "latenza", "risorse"},
        "postmortem_retriever": {"postmortem", "storic", "passat", "simil", "precedenti"},
        "classifier": {"classific", "categor", "priorit", "triage", "ipotesi"},
        "summarizer": {"riepilog", "report", "sintesi", "azioni", "raccomand", "sommario"},
    }
    fitness_vals, precision_vals = [], []
    for run_id, plans in per_run_plans.items():
        if not plans:
            continue
        steps = plans[-1].get("steps") or []          # ultimo piano della run
        executed = per_run_executed_agents.get(run_id, [])
        exec_set = set(executed)
        if not steps:
            continue
        # fitness: frazione degli step pianificati riconducibili a un agente eseguito
        covered = 0
        matched_agents: set[str] = set()
        for st in steps:
            toks = _tok(str(st))
            hit = None
            for ag in exec_set:
                keys = AGENT_TOKENS.get(ag, set())
                if any(any(t.startswith(k) or k in t for t in toks) for k in keys):
                    hit = ag
                    break
            if hit:
                covered += 1
                matched_agents.add(hit)
        fitness_vals.append(covered / len(steps))
        # precision: frazione degli agenti eseguiti (escluso il planner stesso)
        # che erano previsti nel piano
        relevant_exec = {a for a in exec_set if a not in ("planner", "reader")}
        if relevant_exec:
            precision_vals.append(len(matched_agents & relevant_exec) / len(relevant_exec))

    # --- A2.5 Variabilità del piano fra run --------------------------------
    len_counter = Counter(lengths)
    first_step_counter = Counter(
        str((p.get("steps") or ["—"])[0])[:60] for p in all_plans if p.get("steps"))

    return {
        "A2_1_plan_length": {
            "label": "Lunghezza del piano",
            "root": "planning span (agent observability)",
            "question": "Quanti step contiene il piano prodotto dal planner?",
            "stats": stats(lengths),
            "distribution": dict(sorted(len_counter.items())),
        },
        "A2_2_replanning_rate": {
            "label": "Replanning rate",
            "root": "stabilità del control flow",
            "question": "In quante run il piano è stato rivisto almeno una volta?",
            "value": (runs_with_replan / n_runs) if n_runs else 0.0,
            "format": "pct",
            "runs_with_replan": runs_with_replan,
            "n_runs": n_runs,
            "total_replans": sum(per_run_replans.values()),
        },
        "A2_3_plan_execution_alignment": {
            "label": "Plan-execution fitness / precision",
            "root": "fitness & precision (conformance checking)",
            "question": "Quanto il piano dichiarato corrisponde a ciò che è stato realmente eseguito?",
            "fitness": stats(fitness_vals),
            "precision": stats(precision_vals),
            "note": "Proxy lessicale dichiarato: match fra token dello step "
                    "pianificato e area semantica dell'agente eseguito.",
        },
        "A2_4_planning_latency": {
            "label": "Latenza di pianificazione",
            "root": "span duration (tracing)",
            "question": "Quanto tempo impiega il planner a produrre il piano?",
            "stats": stats(latencies),
            "p95_ms": percentile([float(x) for x in latencies], 0.95),
        },
        "A2_5_plan_variability": {
            "label": "Variabilità del piano fra run",
            "root": "trace variants (process mining)",
            "question": "Su ripetizioni dello stesso ticket, il piano resta simile?",
            "length_entropy_norm": entropy_norm(len_counter),
            "distinct_lengths": len(len_counter),
            "distinct_first_steps": len(first_step_counter),
            "first_step_distribution": dict(first_step_counter.most_common(6)),
        },
    }


# =========================================================================
# A3 — Handoff
# =========================================================================
def a3_details(per_run_edges: dict[str, list[tuple[str, str]]],
               declared_edges: list[tuple[str, str]] | None) -> dict[str, Any]:
    """Metriche di dettaglio sugli handoff (grafo di control flow osservato)."""
    all_edges = [e for lst in per_run_edges.values() for e in lst]
    edge_counter = Counter(all_edges)
    observed_edges = set(edge_counter)
    declared_set = {tuple(e) for e in (declared_edges or [])}

    # --- A3.1 Topology conformance (role adherence) ------------------------
    # Il grafo osservato deve essere un sottografo di quello dichiarato.
    unexpected = sorted(observed_edges - declared_set) if declared_set else []
    conformant = len(observed_edges) - len(unexpected)
    conformance = (conformant / len(observed_edges)) if observed_edges else 1.0

    # --- A3.2 Edge coverage -------------------------------------------------
    exercised = observed_edges & declared_set if declared_set else observed_edges
    edge_coverage = (len(exercised) / len(declared_set)) if declared_set else 0.0
    never_used = sorted(declared_set - observed_edges) if declared_set else []

    # --- A3.3 Densità del grafo osservato ----------------------------------
    nodes = {n for e in observed_edges for n in e}
    n_nodes = len(nodes)
    max_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
    density = len(observed_edges) / max_edges

    # --- A3.4 Bounce / cicli ------------------------------------------------
    # Bounce = A→B seguito da B→A nella stessa run.
    bounces = 0
    repeat_targets = 0
    for run_id, edges in per_run_edges.items():
        for i in range(len(edges) - 1):
            a, b = edges[i]
            c, d = edges[i + 1]
            if (b, a) == (c, d):
                bounces += 1
        tgt_counts = Counter(t for _s, t in edges)
        repeat_targets += sum(1 for _t, c in tgt_counts.items() if c > 1)

    # --- A3.5 Fan-out --------------------------------------------------------
    fanout: dict[str, int] = {}
    for s, t in observed_edges:
        fanout[s] = fanout.get(s, 0) + 1

    per_run_counts = {rid: len(e) for rid, e in per_run_edges.items()}

    return {
        "A3_1_topology_conformance": {
            "label": "Topology conformance (role adherence)",
            "root": "conformance checking: sottografo del modello dichiarato",
            "question": "Gli handoff osservati sono tutti ammessi dalla topologia dichiarata?",
            "value": conformance,
            "format": "pct",
            "observed_edges": len(observed_edges),
            "declared_edges": len(declared_set),
            "unexpected_edges": [{"from": a, "to": b} for a, b in unexpected],
        },
        "A3_2_edge_coverage": {
            "label": "Edge coverage",
            "root": "coverage testing sul grafo",
            "question": "Quanta parte della topologia dichiarata è stata effettivamente esercitata?",
            "value": edge_coverage,
            "format": "pct",
            "exercised": len(exercised),
            "declared": len(declared_set),
            "never_exercised": [{"from": a, "to": b} for a, b in never_used][:12],
        },
        "A3_3_graph_density": {
            "label": "Densità del grafo osservato",
            "root": "graph theory (directed graph density)",
            "question": "Quanto è connesso il grafo di interazione realmente prodotto?",
            "value": density,
            "format": "ratio",
            "n_nodes": n_nodes,
            "n_edges": len(observed_edges),
            "max_possible_edges": max_edges,
        },
        "A3_4_bounces_cycles": {
            "label": "Bounce e ritorni sullo stesso agente",
            "root": "anti-pattern di orchestrazione multi-agente",
            "question": "Ci sono rimbalzi A→B→A o agenti riattivati più volte nella stessa run?",
            "bounces": bounces,
            "runs_with_repeat_target": repeat_targets,
            "n_runs": len(per_run_edges),
        },
        "A3_5_fanout": {
            "label": "Fan-out per componente",
            "root": "topologia di orchestrazione",
            "question": "Verso quanti destinatari distinti instrada ciascun componente?",
            "fanout": dict(sorted(fanout.items(), key=lambda kv: -kv[1])),
            "top_edges": [{"from": a, "to": b, "count": c}
                          for (a, b), c in edge_counter.most_common(10)],
        },
        "A3_6_handoffs_per_run": {
            "label": "Handoff per run",
            "root": "step-level agent evaluation",
            "question": "Quanti passaggi di controllo servono per concludere una run?",
            "stats": stats(list(per_run_counts.values())),
            "per_run": per_run_counts,
        },
    }


# =========================================================================
# A4 — Metriche di percorso
# =========================================================================
def a4_details(per_run: dict[str, dict],
               per_run_agent_seq: dict[str, list[str]],
               declared_n_nodes: int | None) -> dict[str, Any]:
    """Metriche di dettaglio sul percorso complessivo della run."""
    if not per_run:
        return {}
    steps = [r["steps"] for r in per_run.values()]
    durs = [float(r["duration_ms"]) for r in per_run.values()]
    tools = [r["tool_calls"] for r in per_run.values()]
    errs = [r["errors"] for r in per_run.values()]
    n = len(per_run)

    # --- A4.2 Completion rate + Wilson CI -----------------------------------
    completed = sum(1 for r in per_run.values() if r.get("outcome") == "completed")
    wilson = wilson_interval(completed, n)

    # --- A4.3 Tool error rate ------------------------------------------------
    total_tools = sum(tools)
    total_errs = sum(errs)
    tool_err_rate = (total_errs / total_tools) if total_tools else 0.0

    # --- A4.4 Trace variants -------------------------------------------------
    # Una "variante" è la sequenza distinta di agenti attivati nella run:
    # è la nozione di trace variant del process mining.
    variants = Counter(tuple(seq) for seq in per_run_agent_seq.values())
    variant_rows = [{"count": c, "sequence": list(v)} for v, c in variants.most_common()]

    # --- A4.5 Complessità ciclomatica (McCabe) -------------------------------
    # M = E - N + 2 sul grafo di control flow osservato (aggregato su tutte
    # le run): misura il numero di cammini linearmente indipendenti.
    edges = set()
    nodes = set()
    for seq in per_run_agent_seq.values():
        prev = "orchestrator"
        for a in seq:
            edges.add((prev, a)); edges.add((a, "orchestrator"))
            nodes.add(a); nodes.add(prev)
            prev = "orchestrator"
    n_nodes_obs = len(nodes) or 1
    cyclomatic = len(edges) - n_nodes_obs + 2

    return {
        "A4_1_step_count": {
            "label": "Step count",
            "root": "step-level agent evaluation",
            "question": "Quanti eventi compongono una run?",
            "stats": stats(steps),
            "p95": percentile([float(s) for s in steps], 0.95),
        },
        "A4_2_completion_rate": {
            "label": "Completion rate (con intervallo di confidenza)",
            "root": "statistical model checking · Wilson score interval",
            "question": "Con quale probabilità il sistema porta a termine il task?",
            "value": wilson["p"],
            "format": "pct",
            "ci_lo": wilson["lo"],
            "ci_hi": wilson["hi"],
            "completed": completed,
            "n_runs": n,
            "note": "Intervallo di Wilson al 95%: robusto anche con N piccolo.",
        },
        "A4_3_tool_error_rate": {
            "label": "Tool error rate",
            "root": "agentic KPI (tool error rate)",
            "question": "Quanto spesso una chiamata a tool fallisce?",
            "value": tool_err_rate,
            "format": "pct",
            "total_tool_calls": total_tools,
            "total_errors": total_errs,
        },
        "A4_4_trace_variants": {
            "label": "Trace variants",
            "root": "trace variant analysis (process mining)",
            "question": "Quante sequenze di esecuzione distinte produce lo stesso ticket?",
            "n_variants": len(variants),
            "n_runs": n,
            "entropy_norm": entropy_norm(variants),
            "variants": variant_rows[:8],
        },
        "A4_5_cyclomatic_complexity": {
            "label": "Complessità ciclomatica del control flow",
            "root": "McCabe (1976): M = E − N + 2",
            "question": "Quanti cammini linearmente indipendenti ha il grafo osservato?",
            "value": cyclomatic,
            "format": "int",
            "edges": len(edges),
            "nodes": n_nodes_obs,
            "declared_nodes": declared_n_nodes,
        },
        "A4_6_duration": {
            "label": "Durata della run",
            "root": "latenza di pipeline (orchestration playbooks)",
            "question": "Quanto dura una run e quanto varia?",
            "stats": stats(durs),
            "p95_ms": percentile(durs, 0.95),
        },
    }
