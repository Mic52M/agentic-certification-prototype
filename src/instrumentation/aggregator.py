"""Aggregator: dagli eventi grezzi alle metriche per macro-dimensione.

Non emette giudizi sulla verificabilità delle proprietà. Produce solamente
metriche descrittive e conteggi, come richiesto dalla natura dimostrativa
della UI: quali evidenze abbiamo, dove, quante volte, come si distribuiscono
sulle N run.

Le metriche seguono la nomenclatura del documento delle evidenze:
- Control Flow: A1 (decisioni orchestratore), A2 (pianificazioni + replanning),
  A3 (handoff), A4 (metriche di percorso).
- Data Flow:    B1 (eventi per canale C1..C7), B2 (channel leakage rate proxy),
  B3 (system leakage rate proxy), B4 (vault V e allowed set A per canale).
- Behavioral:   C1 (trace end-to-end), C2 (state<->output proxy), C3 (decisioni
  successive), C4 (varianza comportamentale su N run).
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable

from . import bh_metrics, cf_metrics
from .events import ChannelId, EventKind, MacroCategory
from .store import ExperimentStore


# =========================================================================
# Vocabolario privacy (V, A) — B4 del PDF.
# Ora vivono in `pii_redactor.py`: la stessa policy che alimenta la
# detection alimenta anche la mitigation (redazione). Manteniamo qui gli
# alias per retro-compatibilità dei chiamanti esterni.
# =========================================================================
from .pii_redactor import (
    ALLOWED_SET_A,
    REDACTION_POLICY,
    VAULT_PATTERNS,
    PIIRedactor,
)

# Instanza singleton usata dalla scansione fallback (per esperimenti "raw"
# senza redazione, o eventi che il redattore non ha marcato).
_scanner = PIIRedactor()


def _scan_pii(text: str) -> dict[str, list[str]]:
    """Rileva occorrenze delle categorie di V nel testo (fallback quando
    l'evento non porta `metadata.pii_redaction_hits`).
    """
    return _scanner.scan(text)


def _event_text(ev: dict) -> str:
    """Testo su cui applicare la detection PII: summary + payload_redacted concat."""
    parts = [ev.get("payload_summary") or ""]
    payload = ev.get("payload_redacted") or {}
    for v in payload.values():
        parts.append(str(v))
    return " \n ".join(parts)


class Aggregator:
    """Costruisce metriche per-run e aggregate su un esperimento.

    Ogni metodo `for_control_flow`, `for_data_flow`, `for_behavioral` restituisce
    un dict serializzabile pensato per essere consumato dalla UI. La struttura
    del dict è documentata in `ARCHITECTURE_OBSERVABILITY.md`.
    """

    def __init__(self, store: ExperimentStore,
                 declared_spec: dict[str, Any] | None = None,
                 bh_classify_c2=None,
                 bh_classify_c3=None,
                 bh_symptom_map: dict | None = None,
                 bh_class_to_tags: dict | None = None) -> None:
        """
        declared_spec: topologia e regole DICHIARATE del sistema, usate per le
        metriche di conformance (edge ammessi, regole di routing, n. nodi).
        Se assente, le metriche di conformance restano calcolabili ma senza
        riferimento (coverage e conformance non hanno denominatore).

        bh_classify_c2 / bh_classify_c3: funzioni coverage/consistency
        -> "coherent"|"acceptable"|"unacceptable" dalla policy dichiarata
        in src/demo/behavioural_policy.py. Iniettate per tenere l'aggregator
        disaccoppiato dal dominio; fallback binario se None.

        bh_symptom_map, bh_class_to_tags: policy per i check pairwise di C3.
        Vuote se non passate (i check C3 diventano tutti N/A).
        """
        self.store = store
        self.spec = declared_spec or {}
        self.bh_classify_c2 = bh_classify_c2 or (
            lambda cov: "coherent" if cov >= 0.5 else "unacceptable")
        self.bh_classify_c3 = bh_classify_c3 or (
            lambda cons: "coherent" if cons >= 0.5 else "unacceptable")
        self.bh_symptom_map = bh_symptom_map or {}
        self.bh_class_to_tags = bh_class_to_tags or {}

    # ---------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------
    def _events_by_run(self) -> dict[str, list[dict]]:
        by_run: dict[str, list[dict]] = defaultdict(list)
        for ev in self.store.iter_all_events():
            by_run[ev["run_id"]].append(ev)
        # Ordina cronologicamente all'interno di ogni run
        for lst in by_run.values():
            lst.sort(key=lambda e: e["timestamp_start"])
        return by_run

    # ---------------------------------------------------------------
    # CONTROL FLOW (§2 PDF)
    # ---------------------------------------------------------------
    def for_control_flow(self) -> dict[str, Any]:
        by_run = self._events_by_run()

        # A1 — decisioni orchestratore per run
        a1_per_run: dict[str, int] = {}
        a1_samples: list[dict] = []           # esempi per la UI
        a1_targets = Counter()                # quali agenti sono stati attivati
        # A2 — pianificazioni
        a2_per_run: dict[str, int] = {}
        a2_samples: list[dict] = []
        replan_per_run: dict[str, int] = {}
        # A3 — handoff
        a3_per_run: dict[str, int] = {}
        a3_samples: list[dict] = []
        a3_edges = Counter()                  # (from,to) -> count
        # A4 — metriche di percorso per run
        a4_per_run: dict[str, dict[str, Any]] = {}

        # --- strutture per le METRICHE DI DETTAGLIO (cf_metrics) -----------
        det_decisions: dict[str, list[dict]] = {}     # A1
        det_plans: dict[str, list[dict]] = {}         # A2
        det_edges: dict[str, list[tuple[str, str]]] = {}   # A3
        det_agent_seq: dict[str, list[str]] = {}      # A2/A4

        for run_id, events in by_run.items():
            det_decisions[run_id] = []
            det_plans[run_id] = []
            det_edges[run_id] = []
            det_agent_seq[run_id] = []
            n_a1 = n_a2 = n_replan = n_a3 = 0
            tool_calls = 0
            errors = 0
            first_ts = events[0]["timestamp_start"] if events else 0
            last_ts = events[-1]["timestamp_start"] if events else 0
            outcome = "unknown"

            for ev in events:
                k = ev["event_type"]
                if k == EventKind.ORCHESTRATOR_DECISION.value:
                    n_a1 += 1
                    if len(a1_samples) < 20:
                        a1_samples.append({
                            "run_id": run_id, "summary": ev.get("payload_summary"),
                            "target": ev.get("target_component"),
                            "meta": ev.get("metadata", {}),
                        })
                    tgt = ev.get("target_component")
                    md = ev.get("metadata", {}) or {}
                    # dettaglio A1: decisione completa di contesto e alternative
                    det_decisions[run_id].append({
                        "target": tgt,
                        "reason": md.get("reason", ""),
                        "alternatives": md.get("alternatives") or [],
                        "step": md.get("step"),
                        "context_keys": md.get("context_snapshot_keys") or [],
                    })
                    if tgt:
                        a1_targets[tgt] += 1
                    # dettaglio A3/A4: arco osservato + sequenza agenti
                    if tgt:
                        det_edges[run_id].append(("orchestrator", str(tgt)))
                        if tgt not in ("__end__", "END"):
                            det_agent_seq[run_id].append(str(tgt))
                            det_edges[run_id].append((str(tgt), "orchestrator"))
                    # A3: gli handoff dell'orchestratore verso i nodi agente
                    # sono derivati dagli orchestrator_decision (target != END).
                    if tgt and tgt not in ("__end__", "END"):
                        n_a3 += 1
                        if len(a3_samples) < 20:
                            # Salviamo `reason` separatamente (che sta nei
                            # metadati). Non riusiamo `payload_summary` perché
                            # include già "→ target · reason": la UI andrebbe
                            # in duplicazione (orchestrator → reader · → reader · ...).
                            a3_samples.append({
                                "run_id": run_id,
                                "from": "orchestrator", "to": tgt,
                                "reason": ev.get("metadata", {}).get("reason", ""),
                            })
                        a3_edges[("orchestrator", tgt)] += 1
                elif k == EventKind.PLANNING_SPAN.value:
                    n_a2 += 1
                    md = ev.get("metadata", {}) or {}
                    det_plans[run_id].append({
                        "steps": md.get("plan") or [],
                        "duration_ms": ev.get("duration_ms", 0) or 0,
                        "updated": bool(md.get("updated")),
                    })
                    if len(a2_samples) < 10:
                        a2_samples.append({
                            "run_id": run_id, "summary": ev.get("payload_summary"),
                            "meta": md,
                        })
                elif k == EventKind.REPLANNING.value:
                    n_replan += 1
                elif k == EventKind.HANDOFF.value:
                    # Handoff espliciti (attualmente non emessi dall'orchestratore
                    # standard; supportati per estensioni future o test).
                    n_a3 += 1
                    if len(a3_samples) < 20:
                        a3_samples.append({
                            "run_id": run_id,
                            "from": ev.get("source_component"),
                            "to": ev.get("target_component"),
                            "summary": ev.get("payload_summary"),
                        })
                    if ev.get("source_component") and ev.get("target_component"):
                        a3_edges[(ev["source_component"], ev["target_component"])] += 1
                        det_edges[run_id].append(
                            (str(ev["source_component"]), str(ev["target_component"])))
                elif k == EventKind.TOOL_CALL.value:
                    tool_calls += 1
                elif k == EventKind.ERROR.value:
                    errors += 1
                elif k == EventKind.RUN_END.value:
                    outcome = ev.get("metadata", {}).get("outcome") or "completed"

            a1_per_run[run_id] = n_a1
            a2_per_run[run_id] = n_a2
            replan_per_run[run_id] = n_replan
            a3_per_run[run_id] = n_a3
            a4_per_run[run_id] = {
                "steps": len(events),
                "tool_calls": tool_calls,
                "errors": errors,
                "duration_ms": max(0, last_ts - first_ts),
                "outcome": outcome,
                "orchestrator_decisions": n_a1,
                "handoffs": n_a3,
            }

        # --- METRICHE DI DETTAGLIO -----------------------------------------
        declared_rules = self.spec.get("rules")
        declared_edges = [tuple(e) for e in self.spec.get("edges", [])] or None
        declared_nodes = self.spec.get("n_nodes")

        return {
            "A1_orchestrator_decisions": {
                "name": "A1 — Decisioni dell'orchestratore",
                "where": "orchestrator (runtime)",
                "how": "hook nel nodo di orchestrazione, evento per ogni scelta di routing",
                "per_run": a1_per_run,
                "total": sum(a1_per_run.values()),
                "distribution_of_targets": dict(a1_targets),
                "samples": a1_samples,
                "detail": cf_metrics.a1_details(det_decisions, declared_rules),
            },
            "A2_planning_spans": {
                "name": "A2 — Spans di pianificazione (planner + replanning)",
                "where": "planner agent, decision surface",
                "how": "span aperto dall'agente planner con piano proposto ed eventuali revisioni",
                "per_run": a2_per_run,
                "replanning_per_run": replan_per_run,
                "total_plans": sum(a2_per_run.values()),
                "total_replans": sum(replan_per_run.values()),
                "samples": a2_samples,
                "detail": cf_metrics.a2_details(det_plans, replan_per_run, det_agent_seq),
            },
            "A3_handoffs": {
                "name": "A3 — Handoff tra agenti",
                "where": "confini tra agenti (source -> target)",
                "how": "evento emesso ad ogni passaggio di controllo/stato",
                "per_run": a3_per_run,
                "total": sum(a3_per_run.values()),
                "edges": [{"from": s, "to": t, "count": c}
                          for (s, t), c in a3_edges.most_common()],
                "samples": a3_samples,
                "detail": cf_metrics.a3_details(
                    det_edges,
                    declared_edges=declared_edges,
                    hub_nodes=set(self.spec.get("hub_nodes") or ()),
                ),
            },
            "A4_path_metrics": {
                "name": "A4 — Metriche di percorso (step count, completion, errori)",
                "where": "derivata dalla trace",
                "how": "conteggi e statistiche sull'insieme degli eventi della run",
                "per_run": a4_per_run,
                "aggregate": self._path_aggregate(a4_per_run),
                "detail": cf_metrics.a4_details(
                    a4_per_run, det_agent_seq, declared_nodes,
                    declared_edges=declared_edges,
                ),
            },
        }

    @staticmethod
    def _path_aggregate(per_run: dict[str, dict]) -> dict[str, Any]:
        if not per_run:
            return {"n_runs": 0}
        steps = [r["steps"] for r in per_run.values()]
        durs = [r["duration_ms"] for r in per_run.values()]
        tools = [r["tool_calls"] for r in per_run.values()]
        errs = [r["errors"] for r in per_run.values()]
        outcomes = Counter(r["outcome"] for r in per_run.values())

        def _st(xs):
            return {"min": min(xs), "max": max(xs), "mean": statistics.mean(xs),
                    "stdev": statistics.pstdev(xs) if len(xs) > 1 else 0.0}

        return {
            "n_runs": len(per_run),
            "steps": _st(steps),
            "duration_ms": _st(durs),
            "tool_calls": _st(tools),
            "errors": _st(errs),
            "outcomes": dict(outcomes),
        }

    # ---------------------------------------------------------------
    # DATA FLOW (§3 PDF, canali AgentLeak C1..C7)
    # ---------------------------------------------------------------
    def for_data_flow(self) -> dict[str, Any]:
        by_run = self._events_by_run()

        # Per canale: conteggio eventi, byte sommari, esempi, PII rilevate.
        per_channel: dict[str, dict[str, Any]] = {}
        for ch in ChannelId:
            per_channel[ch.value] = {
                "events_per_run": defaultdict(int),
                "total_events": 0,
                "total_bytes": 0,
                "samples": [],
                "pii_hits": Counter(),           # {categoria: count} rilevate su raw
                "redactions": Counter(),         # {categoria: count} mascherate lato adapter
                "runs_with_leak": set(),         # per B2 (post-mitigazione)
                "events_with_redaction": 0,
            }

        for run_id, events in by_run.items():
            for ev in events:
                ch = ev.get("channel_id")
                if not ch:
                    continue
                bucket = per_channel[ch]
                bucket["events_per_run"][run_id] += 1
                bucket["total_events"] += 1
                text = _event_text(ev)
                bucket["total_bytes"] += len(text.encode("utf-8"))
                if len(bucket["samples"]) < 8:
                    bucket["samples"].append({
                        "run_id": run_id,
                        "event_type": ev["event_type"],
                        "agent": ev.get("agent_id"),
                        "source": ev.get("source_component"),
                        "target": ev.get("target_component"),
                        "tool": ev.get("tool_name"),
                        "summary": ev.get("payload_summary", "")[:400],
                    })

                # --- Detection B2 ---
                # Se il redattore ha lavorato su questo evento, `metadata.
                # pii_redaction_hits` porta i conteggi PRE-mitigazione (ciò
                # che sarebbe stato rilevato sul testo raw). In quel caso il
                # testo persistente è già mascherato: scansionarlo di nuovo
                # darebbe zero e falserebbe la storia. Preferiamo quindi la
                # sorgente autoritativa: i metadati emessi dall'adapter.
                #
                # Fallback: se `pii_redaction_hits` non è presente (esperimento
                # legacy "raw", o canale non redigito) scansiona il testo.
                meta = ev.get("metadata") or {}
                red_hits = meta.get("pii_redaction_hits") or {}

                if red_hits:
                    # Post-mitigazione, per definizione la PII fuori policy
                    # NON è più nel testo: le occorrenze le ricava dal meta.
                    for cat, n in red_hits.items():
                        bucket["pii_hits"][cat] += int(n)
                        bucket["redactions"][cat] += int(n)
                    bucket["events_with_redaction"] += 1
                    # ATTENZIONE: qui NON aggiungiamo il run a `runs_with_leak`.
                    # La mitigation ha rimosso il leak dal canale osservabile;
                    # la violazione originaria resta tracciata sotto "redactions"
                    # per il blocco B4/mitigation. Il CLR misura ciò che resta
                    # sul canale dopo la policy applicata, non ciò che c'era
                    # prima. Per l'audit "quanto ha lavorato la mitigation" si
                    # guarda il blocco `mitigation` in B4.
                else:
                    # Scansione tradizionale (retrocompat con esperimenti raw).
                    found = _scan_pii(text)
                    allowed = ALLOWED_SET_A.get(ch, set())
                    had_out_of_policy = False
                    for cat, hits in found.items():
                        bucket["pii_hits"][cat] += len(hits)
                        if cat not in allowed:
                            had_out_of_policy = True
                    if had_out_of_policy:
                        bucket["runs_with_leak"].add(run_id)

        # Serializza in forma JSON-friendly.
        n_runs = len(by_run)
        b1_out = {}
        b2_out = {}
        mitigation_per_channel: dict[str, dict[str, Any]] = {}
        for ch_id, bucket in per_channel.items():
            b1_out[ch_id] = {
                "channel_name": CHANNEL_LABELS[ch_id],
                "events_per_run": dict(bucket["events_per_run"]),
                "total_events": bucket["total_events"],
                "total_bytes": bucket["total_bytes"],
                "samples": bucket["samples"],
                "pii_hits": dict(bucket["pii_hits"]),
            }
            leaked_runs = len(bucket["runs_with_leak"])
            b2_out[ch_id] = {
                "channel_name": CHANNEL_LABELS[ch_id],
                "runs_with_out_of_policy_hit": leaked_runs,
                "n_runs": n_runs,
                "clr_proxy": (leaked_runs / n_runs) if n_runs else 0.0,
                "allowed_set": sorted(ALLOWED_SET_A.get(ch_id, set())),
                # Trasparenza: quante volte la mitigation ha operato su
                # questo canale (per categoria). Un CLR=0 accompagnato da
                # `redactions` non vuoti indica: violazione presente ma
                # mitigata; CLR=0 con `redactions` vuoti indica: nessuna
                # violazione presente al di là della policy.
                "redactions_applied": dict(bucket["redactions"]),
                "events_with_redaction": bucket["events_with_redaction"],
            }
            if bucket["redactions"]:
                mitigation_per_channel[ch_id] = {
                    "channel_name": CHANNEL_LABELS[ch_id],
                    "redactions_by_category": dict(bucket["redactions"]),
                    "events_with_redaction": bucket["events_with_redaction"],
                    "total_events": bucket["total_events"],
                }

        # B3: System Leakage Rate (SLR) proxy su un set di canali (default C1,C2,C5).
        default_S = [ChannelId.C1_FINAL_OUTPUT.value,
                     ChannelId.C2_INTER_AGENT.value,
                     ChannelId.C5_SHARED_MEMORY.value]
        runs_with_any_leak = set()
        for ch_id in default_S:
            runs_with_any_leak |= per_channel[ch_id]["runs_with_leak"]
        slr_proxy = (len(runs_with_any_leak) / n_runs) if n_runs else 0.0

        return {
            "B1_channel_trace": {
                "name": "B1 — Tracce per canale C1..C7 (AgentLeak)",
                "where": "adapter layer che intercetta ciascun canale",
                "how": "ogni evento marcato con channel_id, salvato in JSONL append-only",
                "per_channel": b1_out,
            },
            "B2_channel_leakage_rate": {
                "name": "B2 — Channel Leakage Rate (proxy)",
                "where": "detection PII sul contenuto emesso in ogni canale",
                "how": "regex su categorie di V (vault); confronto con Allowed Set A[canale]",
                "vault_categories": sorted(VAULT_PATTERNS.keys()),
                "per_channel": b2_out,
            },
            "B3_system_leakage_rate": {
                "name": "B3 — System Leakage Rate (proxy, OR sui canali)",
                "where": "aggregazione OR sui canali del sistema",
                "how": "conteggio di run con ≥1 canale fuori policy in S",
                "S": default_S,
                "runs_with_any_leak": len(runs_with_any_leak),
                "n_runs": n_runs,
                "slr_proxy": slr_proxy,
            },
            "B4_policy": {
                "name": "B4 — Vault V, Allowed Set A e Mitigation per canale",
                "where": "policy dichiarata dal designer del sistema (in codice)",
                "how": "V = categorie di dati sensibili; A[c] = categorie ammesse "
                       "sul canale c; REDACTION[c] = V - A[c] (derivata).",
                "vault_V": sorted(VAULT_PATTERNS.keys()),
                "allowed_set_A": {k: sorted(v) for k, v in ALLOWED_SET_A.items()},
                # Redaction policy: derivata deterministicamente da (V, A).
                # È esposta qui per rendere l'audit del ciclo detect→mitigate
                # → re-verify autosufficiente: chiunque legga metrics.json
                # vede la specifica dichiarata (A) e la contromisura
                # dichiarata (REDACTION) sullo stesso oggetto.
                "redaction_policy": {k: sorted(v) for k, v in REDACTION_POLICY.items()},
                "mitigation": {
                    "enabled": bool(mitigation_per_channel),
                    "per_channel": mitigation_per_channel,
                    "total_events_redacted": sum(
                        v.get("events_with_redaction", 0)
                        for v in mitigation_per_channel.values()
                    ),
                },
            },
        }

    # ---------------------------------------------------------------
    # BEHAVIORAL (§4 PDF)
    # ---------------------------------------------------------------
    def for_behavioral(self) -> dict[str, Any]:
        by_run = self._events_by_run()

        # C1 — trace end-to-end (timeline + gerarchia semplificata per run)
        trajectories: list[dict] = []
        # C3 — sequenza decisioni per run + postmortem correlati per il check3
        decisions_per_run: dict[str, list[dict]] = {}
        postmortems_per_run: dict[str, list[dict]] = {}
        # C2 — state <-> output proxy (confronto campi chiave)
        state_output_per_run: dict[str, dict[str, Any]] = {}
        # C4 — varianza comportamentale su N run (risoluzione multi-asse).
        # Raccogliamo firme a granularità crescente + campi finali + grandezze
        # numeriche. La vecchia risoluzione (sola sequenza nodi dedup) era
        # cieca in topologia deterministica; qui esplicitiamo TUTTI gli assi
        # dove la varianza residua LLM può manifestarsi.
        final_categories: Counter = Counter()
        final_priorities: Counter = Counter()
        final_services: Counter = Counter()
        trajectory_signatures: Counter = Counter()   # nodi dedup (legacy)
        edge_signatures: Counter = Counter()         # handoff ordinati
        tool_signatures: Counter = Counter()         # tool call ordinati
        step_counts: list[int] = []
        output_lengths: list[int] = []
        durations_ms: list[float] = []
        postmortem_sets: list[set[str]] = []

        for run_id, events in by_run.items():
            timeline = []
            hierarchy: dict[str, list] = defaultdict(list)
            decisions: list[dict] = []
            final_state: dict[str, Any] = {}
            final_output_text: str = ""
            handoff_seq: list[tuple[str, str]] = []
            tool_seq: list[str] = []
            run_start_ms: int | None = None
            run_end_ms: int | None = None

            for ev in events:
                k = ev["event_type"]
                node_id = ev.get("agent_id") or ev.get("source_component") or "system"
                item = {
                    "ts": ev["timestamp_start"],
                    "event_type": k,
                    "agent": node_id,
                    "target": ev.get("target_component"),
                    "summary": ev.get("payload_summary", "")[:280],
                    "channel": ev.get("channel_id"),
                }
                timeline.append(item)
                hierarchy[node_id].append(item)
                if k == EventKind.DECISION_POINT.value:
                    decisions.append({
                        "ts": ev["timestamp_start"],
                        "agent": node_id,
                        "summary": ev.get("payload_summary", ""),
                        "meta": ev.get("metadata", {}),
                        # payload_redacted contiene 'inputs' (es. primary_symptom
                        # per il planner): serve al check C3.2 planner ↔ classifier.
                        "payload_redacted": ev.get("payload_redacted", {}),
                    })
                elif k == EventKind.STATE_SNAPSHOT.value:
                    md = ev.get("metadata", {}) or {}
                    final_state = md.get("state", final_state) or final_state
                elif k == EventKind.FINAL_OUTPUT.value:
                    final_output_text = ev.get("payload_summary", "") or ""
                elif (k == EventKind.TOOL_RESULT.value
                      and ev.get("tool_name") == "query_postmortems"):
                    # Cattura i postmortem correlati per il check C3.3.
                    payload = ev.get("payload_redacted") or {}
                    result = payload.get("result")
                    if isinstance(result, list):
                        postmortems_per_run.setdefault(run_id, []).extend(
                            {"id": p.get("id"), "tags": p.get("tags") or []}
                            for p in result if isinstance(p, dict)
                        )
                elif k in (EventKind.HANDOFF.value,
                          EventKind.ORCHESTRATOR_DECISION.value):
                    # Firma edge-level: usa gli handoff se presenti,
                    # altrimenti le orchestrator_decision (in questo
                    # runtime hub-and-spoke ogni decisione dispatcher
                    # rappresenta l'edge orchestrator→target).
                    src = ev.get("source_component") or "orchestrator"
                    tgt = ev.get("target_component") or ""
                    if src and tgt:
                        handoff_seq.append((src, tgt))
                elif k == EventKind.TOOL_CALL.value:
                    tname = ev.get("tool_name")
                    if tname:
                        tool_seq.append(str(tname))

                # Bracket temporale della run (per C4.9 duration CV).
                ts = ev.get("timestamp_start")
                te = ev.get("timestamp_end") or ts
                if ts is not None:
                    if run_start_ms is None or ts < run_start_ms:
                        run_start_ms = ts
                    if run_end_ms is None or te > run_end_ms:
                        run_end_ms = te

            # signature semplificata della traiettoria per C4 (sequenza di agenti)
            sig = tuple(dict.fromkeys(t["agent"] for t in timeline
                                      if t["event_type"] in (
                                          EventKind.HANDOFF.value,
                                          EventKind.DECISION_POINT.value,
                                          EventKind.PLANNING_SPAN.value)))
            trajectory_signatures[sig] += 1

            # C2 proxy: coerenza state<->output sui campi chiave dello stato consolidato
            key_fields = ("classification", "priority", "affected_service")
            projected = {f: final_state.get(f) for f in key_fields}
            appears_in_output = {
                f: (str(v).lower() in final_output_text.lower())
                if v not in (None, "") else None
                for f, v in projected.items()
            }
            covered = [f for f, v in appears_in_output.items() if v is True]
            missing = [f for f, v in appears_in_output.items()
                       if v is False and projected[f] not in (None, "")]
            state_output_per_run[run_id] = {
                "state_key_fields": projected,
                "fields_covered_in_output": covered,
                "fields_missing_from_output": missing,
                "final_output_excerpt": final_output_text[:400],
            }
            # Per C4: distribuzioni dei campi finali chiave (multi-asse).
            if projected.get("classification"):
                final_categories[str(projected["classification"])] += 1
            if projected.get("priority"):
                final_priorities[str(projected["priority"])] += 1
            if projected.get("affected_service"):
                final_services[str(projected["affected_service"])] += 1
            edge_signatures[tuple(handoff_seq)] += 1
            tool_signatures[tuple(tool_seq)] += 1
            step_counts.append(len(timeline))
            output_lengths.append(len(final_output_text))
            if run_start_ms is not None and run_end_ms is not None:
                durations_ms.append(float(run_end_ms - run_start_ms))
            postmortem_sets.append(
                {p["id"] for p in postmortems_per_run.get(run_id, []) if p.get("id")}
            )

            trajectories.append({
                "run_id": run_id,
                "n_steps": len(timeline),
                "timeline": timeline,
                "hierarchy_by_agent": {k: v for k, v in hierarchy.items()},
                "n_decisions": len(decisions),
            })
            decisions_per_run[run_id] = decisions

        return {
            "C1_trajectories": {
                "name": "C1 — Trace end-to-end (span-per-tick)",
                "where": "raccolta unificata di tutti gli eventi della run",
                "how": "timeline temporale + vista gerarchica per agente",
                "n_runs": len(trajectories),
                "trajectories": trajectories,
            },
            "C2_state_output": {
                "name": "C2 — Coerenza state ↔ output (proxy)",
                "where": "confronto tra stato consolidato del sistema e testo dell'output finale",
                "how": "proiezione su campi chiave (classification, priority, affected_service); "
                       "verifica di presenza lessicale nel testo dell'output; "
                       "verdetto tri-livello secondo policy dichiarata "
                       "(coherent / acceptable / unacceptable)",
                "per_run": state_output_per_run,
                "detail": bh_metrics.c2_details(state_output_per_run,
                                                self.bh_classify_c2),
            },
            "C3_decision_coherence": {
                "name": "C3 — Sequenza decisioni successive (intention ↔ behavior)",
                "where": "ordine cronologico dei decision_point emessi dai vari agenti",
                "how": "3 check pairwise di coerenza fra decisioni (planner ↔ investigatori, "
                       "planner ↔ classifier, classifier ↔ postmortem); verdetto tri-livello "
                       "coherent/acceptable/unacceptable secondo policy dichiarata",
                "per_run": {run_id: {"n_decisions": len(d), "decisions": d}
                            for run_id, d in decisions_per_run.items()},
                "detail": bh_metrics.c3_details(
                    decisions_per_run, postmortems_per_run,
                    self.bh_classify_c3,
                    self.bh_symptom_map, self.bh_class_to_tags),
            },
            "C4_behavioral_variance": {
                "name": "C4 — Stabilità comportamentale su N run",
                "where": "sulle N ripetizioni dello stesso ticket",
                "how": "risoluzione multi-asse: firme di traiettoria a "
                       "3 granularità (nodi/edge/tool), distribuzioni sui "
                       "campi finali (classification/priority/service), "
                       "coefficient of variation su step/output/durata, "
                       "Jaccard medio pairwise sull'insieme postmortem",
                # Firma legacy (kept for retro-compat con UI vecchia dashboard).
                "trajectory_signatures": [{"signature": list(s), "count": c}
                                          for s, c in trajectory_signatures.most_common()],
                "n_runs": len(trajectories),
                # Dettaglio multi-asse (10 sub-metriche C4.1..C4.10).
                "detail": bh_metrics.c4_details(
                    node_signatures=trajectory_signatures,
                    edge_signatures=edge_signatures,
                    tool_signatures=tool_signatures,
                    final_classification=final_categories,
                    final_priority=final_priorities,
                    final_affected_service=final_services,
                    step_counts=step_counts,
                    output_lengths=output_lengths,
                    durations_ms=durations_ms,
                    postmortem_sets=postmortem_sets,
                ),
            },
        }

    # ---------------------------------------------------------------
    # Persistenza aggregato
    # ---------------------------------------------------------------
    def build_and_save(self) -> dict[str, Any]:
        payload = {
            "control_flow": self.for_control_flow(),
            "data_flow": self.for_data_flow(),
            "behavioral": self.for_behavioral(),
        }
        self.store.save_aggregate("metrics", payload)
        return payload


# Etichette leggibili dei canali AgentLeak, riusate dalla UI.
CHANNEL_LABELS = {
    ChannelId.C1_FINAL_OUTPUT.value:  "C1 · Final output (user)",
    ChannelId.C2_INTER_AGENT.value:   "C2 · Inter-agent messages",
    ChannelId.C3_TOOL_INPUT.value:    "C3 · Tool input",
    ChannelId.C4_TOOL_OUTPUT.value:   "C4 · Tool output",
    ChannelId.C5_SHARED_MEMORY.value: "C5 · Shared memory / workspace",
    ChannelId.C6_REASONING_TRACE.value: "C6 · Reasoning / logs",
    ChannelId.C7_ARTIFACT.value:      "C7 · Persistent artifacts",
}
