"""Orchestratore deterministico rule-based per l'incident triage.

A differenza del multi_agent originario (routing lineare), qui abbiamo
branching non banale:
- dopo il triage-planner, se il sintomo principale è latency/performance,
  vai PRIMA alle metriche; se è error/queue, vai PRIMA ai log;
- postmortem retrieval è indipendente e può accodarsi dopo aver visto
  almeno una fonte;
- eventuale FALLBACK se planner non ha deciso l'affected_service ("unknown"):
  si esegue una investigazione più ampia (entrambi i servizi);
- il classifier attende che ci siano log OR metriche + eventualmente
  postmortem (branching soft);
- il summarizer chiude.

Le regole sono ordinate, first-match-wins, e SONO la guardia G(v) per l'A1.
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import END

from ..instrumentation import Recorder
from .state import IncidentState


def _needs_metrics_first(state: IncidentState) -> bool:
    # euristica: se nel messaggio utente o nei sintomi compaiono parole
    # legate a performance/latenza -> prima le metriche.
    keywords = ("lento", "lentiss", "latenza", "timeout", "slow", "hang")
    txt = (state.user_message or "").lower()
    inc = state.workspace.incident_snapshot or {}
    for s in inc.get("symptoms", []):
        txt += " " + str(s).lower()
    return any(k in txt for k in keywords)


def _has_any_investigation(state: IncidentState) -> bool:
    return bool(state.workspace.findings_logs) or bool(state.workspace.findings_metrics)


# Le "regole" sono predicati puri. Non emettono eventi: quello lo fa
# l'orchestrator_node dopo aver applicato la regola.
ROUTING_RULES: list[tuple[Callable[[IncidentState], bool], str, str]] = [
    # 1. incident ancora da leggere
    (lambda s: s.workspace.incident_snapshot is None,
     "reader", "incident non ancora letto"),
    # 2. pianificazione mancante
    (lambda s: not s.planning_done,
     "planner", "manca il piano di triage"),
    # 3. branching: metriche-first se sintomo di performance
    (lambda s: not s.investigation_done and not s.workspace.findings_metrics
                and _needs_metrics_first(s),
     "metrics_analyst", "sintomo di performance: prima metriche"),
    # 4. altrimenti log-first
    (lambda s: not s.investigation_done and not s.workspace.findings_logs
                and not _needs_metrics_first(s),
     "log_investigator", "sintomo di errore/coda: prima i log"),
    # 5. seconda fonte di investigazione (se manca quella non ancora esplorata)
    (lambda s: not s.investigation_done and not s.workspace.findings_metrics,
     "metrics_analyst", "seconda fonte: metriche"),
    (lambda s: not s.investigation_done and not s.workspace.findings_logs,
     "log_investigator", "seconda fonte: log"),
    # 6. postmortem retrieval quando c'è almeno una fonte investigata
    (lambda s: not s.workspace.related_postmortems and _has_any_investigation(s),
     "postmortem_retriever", "recupero postmortem correlati"),
    # 7. marca investigation come conclusa (transizione soft: la fa il nodo agent)
    #    → passa al classifier
    (lambda s: not s.classification_done,
     "classifier", "classificazione dell'incidente"),
    # 8. riepilogo finale
    (lambda s: s.final_report is None,
     "summarizer", "produzione del report finale"),
    # 9. default
    (lambda s: True, END, "report prodotto: terminazione"),
]


def decide_next(state: IncidentState) -> tuple[str, str, list[str]]:
    alternatives: list[str] = []
    chosen: tuple[str, str] | None = None
    for predicate, next_node, reason in ROUTING_RULES:
        if predicate(state):
            if chosen is None:
                chosen = (next_node, reason)
            else:
                # le regole successive che erano vere sono "alternative
                # potenziali" note al momento della decisione: utile per A1
                alternatives.append(next_node)
    if chosen is None:
        return END, "fallback", alternatives
    return chosen[0], chosen[1], alternatives


def build_orchestrator_node(recorder: Recorder):
    def orchestrator_node(state: IncidentState) -> dict:
        step = state.iteration + 1
        next_node, reason, alts = decide_next(state)
        # A1: decisione dell'orchestratore
        snap = state.model_dump()
        snap_keys = [k for k, v in snap.items()
                     if v not in (None, [], "", False, {})]
        recorder.orchestrator_decision(
            target=str(next_node),
            reason=reason,
            alternatives=[a for a in alts if a != next_node],
            step=step,
            context_snapshot_keys=snap_keys,
        )
        # Nota: NON emettiamo un handoff separato — sarebbe duplicato con la
        # orchestrator_decision (stesso target, stesso momento). L'aggregator
        # per A3 (handoff) usa le orchestrator_decision con target != END
        # come proxy di handoff verso gli agenti.
        return {"next_node": next_node, "iteration": step}

    return orchestrator_node
