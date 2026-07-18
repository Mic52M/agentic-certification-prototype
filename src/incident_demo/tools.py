"""Tool per il use case incident triage.

Ogni funzione è deterministica e opera su dataset JSON locali. Sono
strumenti "puliti" dal punto di vista del dominio: la strumentazione
(TraceEvent per canali C3/C4) è aggiunta dal chiamante tramite Recorder.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .. import config


@lru_cache(maxsize=1)
def _incidents() -> dict[str, dict]:
    data = json.loads(config.INCIDENTS_PATH.read_text(encoding="utf-8"))
    return {i["id"]: i for i in data}


@lru_cache(maxsize=1)
def _app_logs() -> dict[str, list[dict]]:
    return json.loads(config.APP_LOGS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _metrics() -> dict[str, dict]:
    return json.loads(config.METRICS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _postmortems() -> list[dict]:
    return json.loads(config.POSTMORTEMS_PATH.read_text(encoding="utf-8"))


# ---------- Tool esposti agli agenti -----------------------------------
def read_incident(incident_id: str) -> dict[str, Any]:
    inc = _incidents().get(incident_id)
    if not inc:
        return {"error": "incident_not_found", "incident_id": incident_id,
                "available_ids": list(_incidents().keys())}
    return dict(inc)


def fetch_logs(service: str, min_level: str = "INFO") -> list[dict]:
    """Log applicativi filtrati per servizio e livello minimo."""
    order = {"INFO": 0, "WARN": 1, "ERROR": 2}
    threshold = order.get(min_level.upper(), 0)
    logs = _app_logs().get(service, [])
    return [l for l in logs if order.get(l.get("level", "INFO"), 0) >= threshold]


def fetch_metrics(service: str) -> dict[str, Any]:
    """Metriche di sistema attuali per un servizio."""
    m = _metrics().get(service)
    if m is None:
        return {"error": "service_not_found", "service": service,
                "available_services": list(_metrics().keys())}
    return m


def query_postmortems(keywords: list[str], limit: int = 3) -> list[dict]:
    """Cerca postmortem passati per parole chiave (tag + titolo + root_cause)."""
    kws = {k.lower() for k in keywords if k}
    if not kws:
        return []
    scored: list[tuple[int, dict]] = []
    for pm in _postmortems():
        haystack = " ".join([
            pm["title"].lower(),
            " ".join(pm.get("tags", [])).lower(),
            pm.get("root_cause", "").lower(),
        ])
        score = 0
        for k in kws:
            if k in haystack:
                score += 1
        # tag match extra weight
        score += sum(1 for t in pm.get("tags", []) if t.lower() in kws)
        if score > 0:
            scored.append((score, pm))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"_score": s, **pm} for s, pm in scored[:limit]]


TOOL_REGISTRY = {
    "read_incident":      read_incident,
    "fetch_logs":         fetch_logs,
    "fetch_metrics":      fetch_metrics,
    "query_postmortems":  query_postmortems,
}


TOOL_DESCRIPTIONS = {
    "read_incident":      "read_incident(incident_id: str) — dettagli del ticket incident, con sintomi e messaggi di errore.",
    "fetch_logs":         "fetch_logs(service: str, min_level: 'INFO'|'WARN'|'ERROR') — log applicativi del servizio.",
    "fetch_metrics":      "fetch_metrics(service: str) — metriche di sistema attuali (cpu/mem/latency/error_rate).",
    "query_postmortems":  "query_postmortems(keywords: list[str], limit: int=3) — postmortem passati rilevanti.",
}


def execute_tool(name: str, args: dict[str, Any]) -> tuple[Any, bool]:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": "unknown_tool", "tool": name}, False
    try:
        result = fn(**args)
        success = not (isinstance(result, dict) and result.get("error"))
        return result, success
    except TypeError as e:
        return {"error": "bad_arguments", "detail": str(e), "tool": name}, False
    except Exception as e:  # noqa: BLE001
        return {"error": "tool_exception", "detail": str(e), "tool": name}, False
