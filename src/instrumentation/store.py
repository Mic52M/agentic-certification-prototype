"""Event Store: persistenza append-only degli eventi.

Struttura su disco (relativa a `experiments/`):

    experiments/
      <experiment_id>/
        experiment.json              # metadati esperimento + indice run
        runs/<run_id>.jsonl          # eventi della singola run
        aggregate/metrics.json       # (scritto dall'Aggregator a fine batch)

I file JSONL sono append-only durante la run, immutabili una volta chiusa la run
(come raccomandato dalla letteratura sull'agent observability, cfr. documento
delle evidenze §2.1 ciclo di vita). Il formato è deliberatamente leggibile a
occhio nudo, per essere ispezionabile senza tooling.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .. import config
from .events import TraceEvent
from .pii_redactor import PIIRedactor
from .session import ExperimentMeta, RunMeta


class EventStore:
    """Store degli eventi di una singola run: scrive un file JSONL append-only.

    Se un PIIRedactor è passato in `redactor`, prima della persistenza il
    payload testuale dell'evento viene mascherato per le categorie non
    ammesse sul suo `channel_id` (mitigation lato adapter). Le occorrenze
    mascherate finiscono nei `metadata.pii_redaction_hits` come contatore
    per categoria, così l'aggregator può misurare *quanto* la mitigation
    ha lavorato senza dover ri-scansionare il testo (che ora è mascherato).
    """

    def __init__(self, experiment_dir: Path, run: RunMeta,
                 subscribers: list[Callable[[dict], None]] | None = None,
                 redactor: PIIRedactor | None = None) -> None:
        self.run = run
        self.subscribers = subscribers or []
        self.redactor = redactor
        self.dir = experiment_dir / "runs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{run.run_id}.jsonl"
        self._fh = self.path.open("w", encoding="utf-8")
        self._count = 0

    def _apply_redaction(self, d: dict) -> None:
        """In-place: maschera il payload dell'evento se ha channel_id e il
        redactor ha categorie da mascherare per quel canale.

        Modifica `payload_summary` e ricorsivamente ogni stringa raggiungibile
        in `payload_redacted` (i payload reali sono dict/list annidati: es.
        `payload_redacted.result.reporter_email`). Annota in
        `metadata.pii_redaction_hits` il conteggio aggregato per categoria.
        """
        if self.redactor is None:
            return
        ch = d.get("channel_id")
        if not self.redactor.is_active_for(ch):
            return

        total_hits: dict[str, int] = {}

        def _bump(hits: dict[str, int]) -> None:
            for cat, n in hits.items():
                total_hits[cat] = total_hits.get(cat, 0) + n

        def _redact_deep(value):
            """Redige ricorsivamente. Ritorna il valore possibly-modificato."""
            if isinstance(value, str):
                if not value:
                    return value
                r = self.redactor.redact(value, ch)
                if r.hits:
                    _bump(r.hits)
                    return r.text
                return value
            if isinstance(value, dict):
                for k, v in list(value.items()):
                    value[k] = _redact_deep(v)
                return value
            if isinstance(value, list):
                for i, v in enumerate(value):
                    value[i] = _redact_deep(v)
                return value
            return value

        summary = d.get("payload_summary") or ""
        if summary:
            d["payload_summary"] = _redact_deep(summary)

        payload = d.get("payload_redacted")
        if payload:
            d["payload_redacted"] = _redact_deep(payload)

        if total_hits:
            meta = d.get("metadata") or {}
            meta["pii_redaction_hits"] = total_hits
            d["metadata"] = meta

    def append(self, event: TraceEvent) -> None:
        """Scrive un evento nel JSONL della run e notifica gli iscritti (UI live)."""
        # Aggancia gli id della run se non impostati (comodità per i chiamanti).
        if not event.run_id:
            event.run_id = self.run.run_id
        if not event.experiment_id:
            event.experiment_id = self.run.experiment_id
        d = event.to_dict()
        # Mitigation: se un redattore è attivo per questo canale, applica
        # la redazione PRIMA di persistere e PRIMA di notificare i sink UI
        # (nessun percorso deve vedere PII fuori policy).
        self._apply_redaction(d)
        self._fh.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()
        self._count += 1
        for s in self.subscribers:
            try:
                s(d)
            except Exception:  # noqa: BLE001 - i sink non devono mai rompere la run
                pass

    @property
    def count(self) -> int:
        return self._count

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:  # noqa: BLE001
            pass


class ExperimentStore:
    """Gestisce l'intera cartella di un esperimento: metadati + indice run.

    Non memorizza gli eventi in memoria: quelli vivono nei file per-run.
    """

    def __init__(self, meta: ExperimentMeta,
                 base_dir: Path | None = None) -> None:
        self.meta = meta
        base = base_dir or config.EXPERIMENTS_DIR
        base.mkdir(exist_ok=True)
        self.dir = base / meta.experiment_id
        self.dir.mkdir(exist_ok=True)
        self._index_path = self.dir / "experiment.json"
        self._run_index: list[RunMeta] = []
        self._flush_index()

    def open_run(self, run: RunMeta,
                 subscribers: list[Callable[[dict], None]] | None = None,
                 redactor: PIIRedactor | None = None) -> EventStore:
        """Apre uno store per una nuova run e aggiorna l'indice."""
        self._run_index.append(run)
        store = EventStore(self.dir, run, subscribers=subscribers,
                           redactor=redactor)
        self._flush_index()
        return store

    def close_run(self, run: RunMeta, event_store: EventStore) -> None:
        run.total_events = event_store.count
        event_store.close()
        self._flush_index()

    def _flush_index(self) -> None:
        payload = {
            "meta": self.meta.to_dict(),
            "runs": [r.to_dict() for r in self._run_index],
        }
        self._index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    # -------- lettura (usata dall'aggregator e dalla UI) --------------
    def iter_run_events(self, run_id: str):
        """Itera gli eventi di una run come dict, dal file JSONL."""
        path = self.dir / "runs" / f"{run_id}.jsonl"
        if not path.exists():
            return
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def iter_all_events(self):
        for run in self._run_index:
            for ev in self.iter_run_events(run.run_id):
                yield ev

    @property
    def runs(self) -> list[RunMeta]:
        return list(self._run_index)

    def save_aggregate(self, name: str, payload: dict[str, Any]) -> Path:
        agg_dir = self.dir / "aggregate"
        agg_dir.mkdir(exist_ok=True)
        out = agg_dir / f"{name}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        return out
