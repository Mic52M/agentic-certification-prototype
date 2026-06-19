"""Local web UI for watching the agents work in real time.

This does NOT change the agents. It attaches a second consumer to the exact
same event stream that already produces the JSONL trace (TraceLogger.event_sink)
and pushes those events to the browser over Server-Sent Events (SSE).

    python -m webapp.server          # then open http://127.0.0.1:8000

Architecture:
- GET /api/run-stream starts a run in a background thread and streams every
  trace event as it happens. One thread-safe queue bridges the (blocking) run
  thread and the (async) SSE response.
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
from fastapi.responses import FileResponse, StreamingResponse
from rich.console import Console

# Make the project root importable so we can reuse run.py and src/.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import run as runner  # noqa: E402
from src import tools  # noqa: E402
from src.logging_utils import TraceLogger, make_run_id  # noqa: E402

app = FastAPI(title="Agentic Certification Prototype — Live View")
STATIC = Path(__file__).resolve().parent / "static"

# Sentinel that marks the end of a run's event stream.
_END = object()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/tickets")
def list_tickets() -> list[dict]:
    """Feed the ticket dropdown in the UI."""
    data = json.loads((ROOT / "data" / "tickets.json").read_text(encoding="utf-8"))
    return [{"id": t["id"], "utente": t["utente"], "descrizione": t["descrizione"]}
            for t in data]


def _run_in_thread(configuration: str, task: str, q: "queue.Queue") -> None:
    """Run one task, pushing every trace event into `q`. Console output is
    suppressed (the browser is the surface here)."""
    console = Console(file=open("/dev/null", "w"), force_terminal=False)
    run_id = make_run_id(configuration, task)
    logger = TraceLogger(run_id, configuration, console, event_sink=q.put)
    try:
        if configuration == "single_agent":
            runner.run_single_agent(task, logger)
        else:
            runner.run_multi_agent(task, logger)
    except Exception as exc:  # noqa: BLE001 - surface the error to the UI
        q.put({
            "event_type": "error", "run_id": run_id,
            "configuration": configuration, "node_name": "__run__",
            "iteration": -1, "payload": {"detail": f"{type(exc).__name__}: {exc}"},
        })
    finally:
        logger.close()
        q.put(_END)


@app.get("/api/run-stream")
async def run_stream(
    config: str = Query(..., pattern="^(single_agent|multi_agent)$"),
    task: str = Query(...),
) -> StreamingResponse:
    q: "queue.Queue" = queue.Queue()
    thread = threading.Thread(target=_run_in_thread, args=(config, task, q),
                              daemon=True)
    thread.start()

    async def event_generator():
        loop = asyncio.get_event_loop()
        yield ": stream-open\n\n"  # nudge the browser to open the connection
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
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    print("Live view su http://127.0.0.1:8000  (Ctrl+C per uscire)")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
