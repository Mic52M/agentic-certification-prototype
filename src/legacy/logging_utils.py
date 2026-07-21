"""Structured JSONL tracing + colored live console output.

THIS IS THE MOST IMPORTANT DELIVERABLE. Every run produces one JSONL file in
./traces/. The first line is run metadata (code hash, lib versions, prompts,
sampling params, state schema). Every subsequent line is one event.

Event schema (one JSON object per line):
{
  "timestamp", "run_id", "configuration", "event_type",
  "node_name", "iteration", "payload": {...}
}
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .. import config

# Recognized event types (kept here as the single declarative list).
EVENT_TYPES = (
    "run_metadata",
    "agent_step",
    "tool_call",
    "tool_result",
    "orchestrator_decision",
    "handoff",
    "state_transition",
    "final_answer",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def code_hash() -> str:
    """SHA-256 over all .py files under src/ — identifies the exact code run."""
    h = hashlib.sha256()
    for path in sorted(Path(config.PROJECT_ROOT, "src").rglob("*.py")):
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def make_run_id(configuration: str, task: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_hash = hashlib.sha256(task.encode("utf-8")).hexdigest()[:8]
    return f"{ts}_{configuration}_{task_hash}"


class TraceLogger:
    """Writes JSONL events and mirrors them to the console via rich."""

    def __init__(self, run_id: str, configuration: str, console: Console,
                 event_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.run_id = run_id
        self.configuration = configuration
        self.console = console
        # Optional second consumer of every event (e.g. the web UI's live
        # stream). Same data as the JSONL — one event in, two sinks out.
        self.event_sink = event_sink
        config.TRACES_DIR.mkdir(exist_ok=True)
        self.path = config.TRACES_DIR / f"{run_id}.jsonl"
        self._fh = self.path.open("w", encoding="utf-8")

    # --- core writer -----------------------------------------------------
    def _write(self, event_type: str, node_name: str, iteration: int,
               payload: dict[str, Any]) -> None:
        event = {
            "timestamp": _now_iso(),
            "run_id": self.run_id,
            "configuration": self.configuration,
            "event_type": event_type,
            "node_name": node_name,
            "iteration": iteration,
            "payload": payload,
        }
        self._fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()
        if self.event_sink is not None:
            try:
                self.event_sink(event)
            except Exception:  # noqa: BLE001 - the UI must never break a run
                pass

    def write_metadata(self, metadata: dict[str, Any]) -> None:
        self._write("run_metadata", node_name="__run__", iteration=-1,
                    payload=metadata)
        self.console.rule(f"[bold cyan]RUN {self.run_id}")
        self.console.print(
            f"[dim]configuration=[/dim] [bold]{self.configuration}[/bold]  "
            f"[dim]model=[/dim] {metadata.get('model')}  "
            f"[dim]temp=[/dim] {metadata.get('temperature')}  "
            f"[dim]trace=[/dim] {self.path.name}"
        )

    # --- typed event helpers + console rendering -------------------------
    def agent_step(self, node_name: str, iteration: int, thought: str,
                   action: dict[str, Any], raw_llm_output: str) -> None:
        self._write("agent_step", node_name, iteration, {
            "thought": thought,
            "action": action,
            "raw_llm_output": raw_llm_output,
            "model": config.MODEL,
            "temperature": config.TEMPERATURE,
        })
        body = Text()
        body.append("Thought: ", style="bold yellow")
        body.append(f"{thought}\n")
        body.append("Action:  ", style="bold magenta")
        body.append(json.dumps(action, ensure_ascii=False))
        self.console.print(Panel(
            body, title=f"[green]agent_step[/green] · {node_name} · iter {iteration}",
            border_style="green", expand=True))

    def tool_call(self, node_name: str, iteration: int, tool_name: str,
                  args: dict[str, Any]) -> None:
        self._write("tool_call", node_name, iteration,
                    {"tool_name": tool_name, "args": args})
        self.console.print(
            f"  [blue]→ tool_call[/blue] [bold]{tool_name}[/bold]"
            f"({json.dumps(args, ensure_ascii=False)})")

    def tool_result(self, node_name: str, iteration: int, tool_name: str,
                    result: Any, success: bool) -> None:
        self._write("tool_result", node_name, iteration,
                    {"tool_name": tool_name, "result": result, "success": success})
        style = "blue" if success else "red"
        preview = json.dumps(result, ensure_ascii=False, default=str)
        if len(preview) > 300:
            preview = preview[:300] + " …"
        self.console.print(f"  [{style}]← tool_result[/{style}] "
                           f"success={success} {preview}")

    def orchestrator_decision(self, iteration: int, next_node: str, reason: str,
                              state_snapshot_keys: list[str]) -> None:
        self._write("orchestrator_decision", "orchestrator", iteration, {
            "next_node": next_node,
            "reason": reason,
            "state_snapshot_keys": state_snapshot_keys,
        })
        self.console.print(Panel(
            Text.assemble(("next_node: ", "bold white"), (next_node + "\n", "bold cyan"),
                          ("reason: ", "bold white"), (reason, "white")),
            title=f"[cyan]orchestrator_decision[/cyan] · iter {iteration}",
            border_style="cyan", expand=True))

    def handoff(self, from_node: str, to_node: str, iteration: int,
                note: str = "") -> None:
        """Explicit transfer of control between two nodes (multi-agent).

        Makes the flow continuous and precise: every "orchestrator -> X" and
        "X -> orchestrator" hop is its own event, drawn live on the graph edge.
        """
        self._write("handoff", from_node, iteration,
                    {"from": from_node, "to": to_node, "note": note})
        self.console.print(
            f"  [dim]⇄ handoff[/dim] [bold]{from_node}[/bold] → "
            f"[bold]{to_node}[/bold]" + (f"  [dim]{note}[/dim]" if note else ""))

    def state_transition(self, node_name: str, iteration: int,
                         before: dict[str, Any], after: dict[str, Any]) -> None:
        diff = {k: {"before": before.get(k), "after": after.get(k)}
                for k in after if before.get(k) != after.get(k)}
        self._write("state_transition", node_name, iteration,
                    {"before": before, "after": after, "diff": diff})
        if diff:
            self.console.print(
                f"  [dim]state_transition[/dim] [{node_name}] changed: "
                f"[italic]{', '.join(diff.keys())}[/italic]")

    def final_answer(self, node_name: str, iteration: int, answer: str,
                     iterations_used: int, total_tokens: int) -> None:
        self._write("final_answer", node_name, iteration, {
            "answer": answer,
            "iterations_used": iterations_used,
            "total_tokens": total_tokens,
        })
        self.console.print(Panel(
            answer, title="[bold green]FINAL ANSWER[/bold green]",
            border_style="bold green", expand=True))
        self.console.print(
            f"[dim]iterations_used={iterations_used}  total_tokens={total_tokens}[/dim]")

    def close(self) -> None:
        self._fh.close()
