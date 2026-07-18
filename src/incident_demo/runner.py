"""Multi-run runner per la demo osservativa.

Esegue N run indipendenti dello stesso ticket incident, ciascuna con:
- il proprio run_id;
- il proprio file JSONL di eventi;
- gli stessi metadati di esperimento (experiment_id condiviso).

Al termine del batch invoca l'Aggregator per produrre le metriche per macro
e le salva come metrics.json dentro la cartella dell'esperimento.

Il runner accetta un event_sink opzionale: una callback che riceve ogni evento
in tempo reale (usata dalla web UI per lo streaming SSE).
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from .. import config
from ..instrumentation import (
    Aggregator,
    ExperimentStore,
    Recorder,
    RunSessionManager,
)
from ..llm_client import LLMClient
from .graph import build_incident_graph
from .state import IncidentState
from .tools import read_incident


def load_incident_input(incident_id: str) -> dict[str, str]:
    inc = read_incident(incident_id)
    if inc.get("error"):
        raise ValueError(f"incident non trovato: {incident_id}")
    return {"incident_id": incident_id,
            "user_message": inc.get("user_message", "")}


def run_experiment(
    incident_id: str,
    macro_focus: str,
    n_runs: int | None = None,
    delay_s: float | None = None,
    event_sink: Callable[[dict], None] | None = None,
    progress_sink: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    """Esegue N run dello stesso incident e ritorna il payload aggregato.

    Args:
        incident_id: id del ticket (es. "INC-2026-014").
        macro_focus: macro selezionata dall'utente ("control_flow" | "data_flow" | "behavioral").
        n_runs: numero di run da eseguire (default da .env / EXPERIMENT_RUNS).
        delay_s: pausa tra run consecutive (default EXPERIMENT_DELAY_S).
        event_sink: callback(evento_dict) per streaming live all'UI.
        progress_sink: callback({"kind": "run_start"|"run_end"|"experiment_end", ...}).
    """
    n_runs = n_runs if n_runs is not None else config.EXPERIMENT_RUNS
    delay_s = delay_s if delay_s is not None else config.EXPERIMENT_DELAY_S

    inc_input = load_incident_input(incident_id)

    session = RunSessionManager(
        ticket_id=incident_id, macro_focus=macro_focus,
        model=config.MODEL, temperature=config.TEMPERATURE,
        runs_target=n_runs,
    )
    store = ExperimentStore(session.experiment)

    if progress_sink:
        progress_sink({"kind": "experiment_start",
                       "experiment_id": session.experiment.experiment_id,
                       "meta": session.experiment.to_dict()})

    llm = LLMClient()

    for i in range(1, n_runs + 1):
        run = session.start_run(i)
        subscribers = [event_sink] if event_sink else []
        event_store = store.open_run(run, subscribers=subscribers)
        recorder = Recorder(event_store)

        # meta iniziale della run
        recorder.run_metadata("runner", {
            "run_index": i,
            "incident_id": incident_id,
            "macro_focus": macro_focus,
            "model": config.MODEL,
            "temperature": config.TEMPERATURE,
            "summary": f"run {i}/{n_runs} · {incident_id} · {macro_focus}",
        })
        if progress_sink:
            progress_sink({"kind": "run_start",
                           "run_index": i, "run_id": run.run_id,
                           "n_runs": n_runs})

        try:
            graph = build_incident_graph(llm, recorder)
            initial = IncidentState(
                user_message=inc_input["user_message"],
                incident_id=inc_input["incident_id"],
            )
            final = graph.invoke(initial, config={"recursion_limit": 40})
            outcome = "completed" if final.get("final_report") else "no_final_report"
            recorder.run_end("runner", outcome, {
                "iterations": final.get("iteration"),
                "total_tokens": final.get("total_tokens"),
                "agent_history": final.get("agent_history"),
                "classification": final.get("classification"),
                "priority": final.get("priority"),
                "affected_service": final.get("affected_service"),
            })
            session.end_run(run, ok=True, total_events=event_store.count)
        except Exception as exc:  # noqa: BLE001
            recorder.error("runner", f"{type(exc).__name__}: {exc}")
            recorder.run_end("runner", "error", {"detail": str(exc)})
            session.end_run(run, ok=False, error=str(exc),
                            total_events=event_store.count)

        store.close_run(run, event_store)

        if progress_sink:
            progress_sink({"kind": "run_end", "run_index": i,
                           "run_id": run.run_id, "n_runs": n_runs,
                           "ok": run.ok, "events": run.total_events})

        if i < n_runs and delay_s > 0:
            time.sleep(delay_s)

    # Aggregazione a fine batch
    agg = Aggregator(store).build_and_save()
    result = {
        "experiment_id": session.experiment.experiment_id,
        "meta": session.experiment.to_dict(),
        "runs": [r.to_dict() for r in store.runs],
        "aggregate": agg,
    }
    if progress_sink:
        progress_sink({"kind": "experiment_end", **result})
    return result
