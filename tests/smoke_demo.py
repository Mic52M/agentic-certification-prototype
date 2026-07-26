"""Smoke test offline della nuova infrastruttura di strumentazione.

Non usa il modello LLM: fabbrica manualmente una sequenza di eventi che
corrisponde a una run 'simulata' e verifica che l'Aggregator produca le
metriche attese per tutte le tre macro. Utile per validare cambi allo
schema evento senza consumare crediti API.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.instrumentation import (
    Aggregator,
    ExperimentStore,
    Recorder,
    RunSessionManager,
)


def _run_scripted(store: ExperimentStore, session: RunSessionManager, i: int) -> None:
    run = session.start_run(i)
    ev = store.open_run(run)
    r = Recorder(ev)
    r.run_metadata("runner", {"summary": f"scripted run {i}"})
    r.orchestrator_decision("planner", "manca il piano", step=1)
    r.handoff("orchestrator", "planner", "instradamento")
    r.planning_span("planner", ["leggi", "cerca", "riassumi"])
    r.decision_point("planner", "affected_service", "mail-gateway")
    r.tool_call("planner", "fetch_logs", {"service": "mail-gateway"})
    r.tool_result("planner", "fetch_logs", [{"level": "ERROR"}], True, duration_ms=42)
    r.shared_memory_write("planner", "findings_logs", ["x"])
    r.inter_agent_msg("planner", "classifier", "notice", "email leaked test@x.it")
    r.state_snapshot("summarizer", {"classification": "regression_after_deploy",
                                     "priority": "P2",
                                     "affected_service": "mail-gateway"})
    r.final_output("summarizer", "Ciao Test, questo è un final report. Vedere PM-2025-081.")
    r.artifact("summarizer", "report", "text/plain", "corpo dell'artefatto")
    r.run_end("runner", "completed", {"iterations": 1})
    store.close_run(run, ev)


def test_infrastructure():
    session = RunSessionManager(ticket_id="INC-2026-014", macro_focus="control_flow",
                                model="mock", temperature=0.0, runs_target=3)
    store = ExperimentStore(session.experiment)
    for i in range(1, 4):
        _run_scripted(store, session, i)

    payload = Aggregator(store).build_and_save()

    # Control Flow: 3 decisioni orchestratore totali, 3 piani.
    cf = payload["control_flow"]
    assert cf["A1_orchestrator_decisions"]["total"] == 3, cf["A1_orchestrator_decisions"]
    assert cf["A2_planning_spans"]["total_plans"] == 3, cf["A2_planning_spans"]
    # A3 include (a) gli handoff espliciti e (b) le orchestrator_decision
    # verso agenti (target != END) come proxy. Lo scripted run ha entrambi
    # (target='planner') -> 2 per run × 3 run = 6.
    assert cf["A3_handoffs"]["total"] == 6, cf["A3_handoffs"]
    assert cf["A4_path_metrics"]["aggregate"]["n_runs"] == 3, cf["A4_path_metrics"]
    print("ok  control_flow aggregation")

    # Data Flow: canali C1..C7 tutti visitati almeno una volta (14 eventi -> vari canali)
    df = payload["data_flow"]
    channels_with_events = [c for c, v in df["B1_channel_trace"]["per_channel"].items()
                            if v["total_events"] > 0]
    assert set(channels_with_events) >= {"C1", "C2", "C3", "C4", "C5", "C7"}, channels_with_events
    # 'test@x.it' finisce in C2 -> categoria 'email' non è in Allowed A[C2] -> out-of-policy
    b2_c2 = df["B2_channel_leakage_rate"]["per_channel"]["C2"]
    assert b2_c2["runs_with_out_of_policy_hit"] == 3, b2_c2
    print("ok  data_flow aggregation")

    # Behavioral: 3 traiettorie, entropia 0 su firma (stesse run scriptate)
    bh = payload["behavioral"]
    assert bh["C1_trajectories"]["n_runs"] == 3, bh["C1_trajectories"]
    assert bh["C4_behavioral_variance"]["signature_entropy_norm"] == 0.0, bh["C4_behavioral_variance"]
    # Il campo 'classification' finale è lo stesso ("regression_after_deploy") -> dist con 1 chiave
    assert list(bh["C4_behavioral_variance"]["final_classification_dist"].keys()) == \
           ["regression_after_deploy"], bh["C4_behavioral_variance"]
    print("ok  behavioral aggregation")


def test_cf_metrics():
    """Verifica le funzioni di calcolo delle metriche di dettaglio CF su
    input costruiti a mano (nessuna dipendenza dal modello)."""
    from src.instrumentation import cf_metrics as cm

    # --- utility statistiche ---
    assert cm.entropy_norm(Counter({"a": 10})) == 0.0            # concentrata
    assert abs(cm.entropy_norm(Counter({"a": 5, "b": 5})) - 1.0) < 1e-9  # uniforme
    w = cm.wilson_interval(4, 4)
    assert w["p"] == 1.0 and w["lo"] < 1.0 and w["hi"] == 1.0, w  # non degenera

    # --- A1: coverage e dead rules ---
    rules = [{"index": 0, "target": "a", "reason": "r0"},
             {"index": 1, "target": "b", "reason": "r1"},
             {"index": 2, "target": "c", "reason": "r2"}]
    decisions = {"run1": [
        {"target": "a", "reason": "r0", "alternatives": [], "context_keys": ["k1"]},
        {"target": "b", "reason": "r1", "alternatives": ["c"], "context_keys": ["k1", "k2"]},
    ]}
    a1 = cm.a1_details(decisions, rules)
    assert abs(a1["A1_1_rule_coverage"]["value"] - 2/3) < 1e-9
    assert len(a1["A1_1_rule_coverage"]["dead_rules"]) == 1
    assert a1["A1_1_rule_coverage"]["dead_rules"][0]["reason"] == "r2"
    assert a1["A1_3_routing_determinism"]["value"] == 1.0       # firme distinte
    assert a1["A1_4_branching_factor"]["forced_decisions"] == 1
    print("ok  cf_metrics A1 (coverage, dead rules, determinism, branching)")

    # --- A3: conformance e coverage del grafo ---
    declared = [("orchestrator", "x"), ("x", "orchestrator"),
                ("orchestrator", "y"), ("y", "orchestrator")]
    observed = {"run1": [("orchestrator", "x"), ("x", "orchestrator"),
                         ("orchestrator", "z")]}   # z non dichiarato
    a3 = cm.a3_details(observed, declared)
    conf = a3["A3_1_topology_conformance"]
    assert conf["observed_edges"] == 3
    assert len(conf["unexpected_edges"]) == 1                    # orchestrator->z
    assert abs(conf["value"] - 2/3) < 1e-9
    cov = a3["A3_2_edge_coverage"]
    assert abs(cov["value"] - 2/4) < 1e-9                        # 2 dei 4 dichiarati
    print("ok  cf_metrics A3 (conformance, edge coverage)")

    # --- A4: completion, varianti, ciclomatica ---
    per_run = {
        "r1": {"steps": 10, "tool_calls": 4, "errors": 0, "duration_ms": 100, "outcome": "completed"},
        "r2": {"steps": 12, "tool_calls": 4, "errors": 1, "duration_ms": 120, "outcome": "completed"},
        "r3": {"steps": 11, "tool_calls": 2, "errors": 0, "duration_ms": 110, "outcome": "error"},
    }
    seqs = {"r1": ["a", "b"], "r2": ["a", "b"], "r3": ["a", "c"]}
    a4 = cm.a4_details(per_run, seqs, declared_n_nodes=5)
    assert a4["A4_2_completion_rate"]["completed"] == 2
    assert abs(a4["A4_2_completion_rate"]["value"] - 2/3) < 1e-9
    assert a4["A4_4_trace_variants"]["n_variants"] == 2          # (a,b) e (a,c)
    assert abs(a4["A4_3_tool_error_rate"]["value"] - 1/10) < 1e-9
    assert a4["A4_5_cyclomatic_complexity"]["value"] > 0
    print("ok  cf_metrics A4 (completion+CI, variants, error rate, cyclomatic)")


if __name__ == "__main__":
    test_infrastructure()
    test_cf_metrics()
    print("\nALL DEMO SMOKE TESTS PASSED")
