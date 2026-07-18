"""Run Session Manager: gestisce l'identità di una run e di un esperimento.

Un esperimento = N run indipendenti dello stesso ticket, associate a uno stesso
experiment_id. Ogni run ha un run_id univoco. La sessione tiene traccia di:

- metadati dell'esperimento (ticket, macro selezionata, modello, N richiesto);
- timestamp di apertura e chiusura;
- eventi emessi in append-only via l'EventStore associato.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ExperimentMeta:
    """Metadati statici di un esperimento (immutabili dopo la creazione)."""
    experiment_id: str
    ticket_id: str
    macro_focus: str
    model: str
    temperature: float
    runs_target: int
    started_at: int
    created_by: str = "demo"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "ticket_id": self.ticket_id,
            "macro_focus": self.macro_focus,
            "model": self.model,
            "temperature": self.temperature,
            "runs_target": self.runs_target,
            "started_at": self.started_at,
            "created_by": self.created_by,
            "notes": self.notes,
        }


@dataclass
class RunMeta:
    """Metadati di una singola run all'interno di un esperimento."""
    run_id: str
    experiment_id: str
    run_index: int  # 1..N
    started_at: int
    ended_at: int = 0
    ok: bool = True
    error: str = ""
    total_events: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "run_index": self.run_index,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "ok": self.ok,
            "error": self.error,
            "total_events": self.total_events,
        }


class RunSessionManager:
    """Genera gli identificatori e traccia il ciclo di vita run/esperimento.

    L'oggetto non decide dove scrivere: quello è compito dell'EventStore.
    Qui teniamo solo l'identità e i metadati.
    """

    def __init__(self, ticket_id: str, macro_focus: str, model: str,
                 temperature: float, runs_target: int, notes: str = "") -> None:
        now = int(time.time() * 1000)
        self.experiment = ExperimentMeta(
            experiment_id=_new_id("exp"),
            ticket_id=ticket_id,
            macro_focus=macro_focus,
            model=model,
            temperature=temperature,
            runs_target=runs_target,
            started_at=now,
            notes=notes,
        )
        self.runs: list[RunMeta] = []

    # ------- API di ciclo di vita --------------------------------------
    def start_run(self, run_index: int) -> RunMeta:
        run = RunMeta(
            run_id=_new_id("run"),
            experiment_id=self.experiment.experiment_id,
            run_index=run_index,
            started_at=int(time.time() * 1000),
        )
        self.runs.append(run)
        return run

    def end_run(self, run: RunMeta, ok: bool = True, error: str = "",
                total_events: int = 0) -> None:
        run.ended_at = int(time.time() * 1000)
        run.ok = ok
        run.error = error
        run.total_events = total_events
