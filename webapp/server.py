"""Web app della demo osservativa.

Serve la UI a tre viste (Control Flow / Data Flow / Comportamentale) e i
seguenti endpoint HTTP + SSE:

- GET  /                       -> UI
- GET  /api/config             -> modello, N run, incident disponibili
- GET  /api/incidents          -> lista incident con snippet
- GET  /api/experiment/stream  -> avvia un esperimento e streamma eventi + progress
- GET  /api/experiment/<id>    -> restituisce i metadati + aggregato di un esperimento
- GET  /api/experiments        -> lista esperimenti eseguiti (per la sidebar)
"""

from __future__ import annotations

import asyncio
import functools
import json
import queue
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.demo.runner import run_experiment  # noqa: E402

app = FastAPI(title="Agentic Instrumentation Demo")
STATIC = Path(__file__).resolve().parent / "static"

_END = object()


# =========================================================================
# Routes base
# =========================================================================
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/config")
def get_config() -> dict:
    return {
        "model": config.MODEL,
        "temperature": config.TEMPERATURE,
        "runs_default": config.EXPERIMENT_RUNS,
        "delay_default": config.EXPERIMENT_DELAY_S,
        "groq_base_url": config.GROQ_BASE_URL,
    }


@app.get("/api/incidents")
def list_incidents() -> list[dict]:
    data = json.loads(config.INCIDENTS_PATH.read_text(encoding="utf-8"))
    out = []
    for i in data:
        out.append({
            "id": i["id"],
            "reporter_name": i.get("reporter_name"),
            "service_hint": i.get("service_hint"),
            "primary_symptom": (i.get("symptoms") or [""])[0],
            "user_message": i.get("user_message"),
        })
    return out


# =========================================================================
# Experiment streaming (SSE)
# =========================================================================
def _run_experiment_in_thread(incident_id: str, macro: str,
                              n_runs: int, delay_s: float,
                              q: "queue.Queue") -> None:
    """Esegue l'esperimento e alimenta la coda con:
    - eventi grezzi (event_type == ...) tramite event_sink;
    - eventi di progresso (kind == 'run_start' | 'run_end' | 'experiment_end').

    Alla fine spinge il sentinel _END.
    """
    def event_sink(ev: dict) -> None:
        q.put({"stream": "event", "data": ev})

    def progress_sink(msg: dict) -> None:
        q.put({"stream": "progress", "data": msg})

    try:
        run_experiment(
            incident_id=incident_id,
            macro_focus=macro,
            n_runs=n_runs,
            delay_s=delay_s,
            event_sink=event_sink,
            progress_sink=progress_sink,
        )
    except Exception as exc:  # noqa: BLE001
        q.put({"stream": "error",
               "data": {"detail": f"{type(exc).__name__}: {exc}"}})
    finally:
        q.put(_END)


@app.get("/api/experiment/stream")
async def experiment_stream(
    incident: str = Query(...),
    macro: str = Query(..., pattern="^(control_flow|data_flow|behavioral)$"),
    runs: int = Query(default=config.EXPERIMENT_RUNS, ge=1, le=50),
    delay: float = Query(default=config.EXPERIMENT_DELAY_S, ge=0, le=10),
) -> StreamingResponse:
    q: "queue.Queue" = queue.Queue()
    thread = threading.Thread(
        target=_run_experiment_in_thread,
        args=(incident, macro, runs, delay, q),
        daemon=True,
    )
    thread.start()

    async def gen():
        loop = asyncio.get_event_loop()
        yield ": stream-open\n\n"
        while True:
            try:
                item = await loop.run_in_executor(
                    None, functools.partial(q.get, True, 0.25))
            except queue.Empty:
                if not thread.is_alive() and q.empty():
                    break
                continue
            if item is _END:
                yield "event: done\ndata: {}\n\n"
                break
            data = json.dumps(item, ensure_ascii=False, default=str)
            yield f"data: {data}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# =========================================================================
# Post-mortem retrieval degli esperimenti
# =========================================================================
@app.get("/api/experiments")
def list_experiments() -> list[dict]:
    base = config.EXPERIMENTS_DIR
    out = []
    if not base.exists():
        return out
    for d in sorted(base.iterdir(), reverse=True):
        idx = d / "experiment.json"
        if idx.is_file():
            try:
                data = json.loads(idx.read_text(encoding="utf-8"))
                out.append({
                    "experiment_id": data["meta"]["experiment_id"],
                    "macro_focus": data["meta"]["macro_focus"],
                    "ticket_id": data["meta"]["ticket_id"],
                    "started_at": data["meta"]["started_at"],
                    "n_runs": len(data.get("runs", [])),
                })
            except Exception:
                pass
    return out[:30]


@app.get("/api/experiment/{experiment_id}")
def get_experiment(experiment_id: str) -> JSONResponse:
    d = config.EXPERIMENTS_DIR / experiment_id
    idx = d / "experiment.json"
    agg = d / "aggregate" / "metrics.json"
    if not idx.exists():
        return JSONResponse(status_code=404, content={"error": "not_found"})
    payload = {
        "index": json.loads(idx.read_text(encoding="utf-8")),
        "aggregate": (json.loads(agg.read_text(encoding="utf-8"))
                      if agg.exists() else None),
    }
    return JSONResponse(content=payload)


if __name__ == "__main__":
    print("Demo osservativa su http://127.0.0.1:8000  (Ctrl+C per uscire)")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
