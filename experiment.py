"""Run the SAME task N times and quantify the non-determinism.

Certification motivation: an LLM-based agentic system is not bit-reproducible
(even at temperature 0 — batching, MoE routing and float non-associativity on
the serving side). You therefore cannot certify a property from a single run;
you need a *distribution* over runs. This script produces that distribution.

    python experiment.py --config multi_agent --ticket T-004 --runs 20
    python experiment.py --config single_agent --task "..." --runs 10 --delay 1.5

For each run it collects the live trace events (same stream as the JSONL) and
extracts: whether the KB was searched, which articles were retrieved, number of
tool calls / agent steps, iterations, tokens. Then it prints a per-run table and
an aggregate summary, and saves a JSON summary under ./experiments/.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import run as runner
from src import config
from src.legacy.logging_utils import TraceLogger, make_run_id
from src.legacy.properties import SPECS, evaluate_trace

ROOT = Path(__file__).resolve().parent
EXPERIMENTS_DIR = ROOT / "experiments"


def _one_run(configuration: str, task: str) -> list[dict]:
    """Execute one run, returning the list of trace events it emitted."""
    events: list[dict] = []
    quiet = Console(file=open(os.devnull, "w"), force_terminal=False)
    run_id = make_run_id(configuration, task)
    logger = TraceLogger(run_id, configuration, quiet, event_sink=events.append)
    try:
        if configuration == "single_agent":
            runner.run_single_agent(task, logger)
        else:
            runner.run_multi_agent(task, logger)
    finally:
        logger.close()
    return events


def _metrics(events: list[dict]) -> dict:
    """Reduce one run's events to a row of metrics."""
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    tool_names = [e["payload"]["tool_name"] for e in tool_calls]
    kb_ids: list[str] = []
    for e in events:
        if (e["event_type"] == "tool_result"
                and e["payload"]["tool_name"] == "search_knowledge_base"):
            res = e["payload"]["result"]
            if isinstance(res, list):
                kb_ids += [a.get("id") for a in res if isinstance(a, dict)]
    final = next((e for e in events if e["event_type"] == "final_answer"), None)
    history = None
    for e in reversed(events):
        if e["event_type"] == "state_transition":
            history = e["payload"]["after"].get("agent_history")
            break
    error = next((e for e in events if e["event_type"] == "error"), None)
    return {
        "ok": error is None,
        "kb_searched": "search_knowledge_base" in tool_names,
        "kb_articles": sorted(set(filter(None, kb_ids))),
        "tool_calls": len(tool_calls),
        "agent_steps": sum(1 for e in events if e["event_type"] == "agent_step"),
        "iterations": (final or {}).get("payload", {}).get("iterations_used"),
        "tokens": (final or {}).get("payload", {}).get("total_tokens"),
        "answer_chars": len((final or {}).get("payload", {}).get("answer", "")),
        "agent_history": history,
        "tool_sequence": tool_names,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Esegue lo stesso task N volte e misura il non-determinismo.")
    parser.add_argument("--config", required=True,
                        choices=["single_agent", "multi_agent"])
    parser.add_argument("--runs", type=int, default=10, help="numero di esecuzioni")
    parser.add_argument("--ticket", default=None,
                        help="id ticket per costruire il task standard (es. T-004)")
    parser.add_argument("--task", default=None, help="task esplicito (sovrascrive --ticket)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="pausa in secondi tra una run e l'altra (rate limit)")
    args = parser.parse_args()

    ticket = args.ticket or "T-004"
    task = args.task or (
        f"L'utente ha aperto il ticket {ticket}, capisci il problema e proponi "
        f"una soluzione.")

    console = Console()
    console.rule(f"[bold cyan]EXPERIMENT · {args.config} · {args.runs} run")
    console.print(f"[dim]task:[/dim] {task}")
    console.print(f"[dim]model:[/dim] {config.MODEL}  [dim]temp:[/dim] {config.TEMPERATURE}\n")

    rows: list[dict] = []
    for i in range(1, args.runs + 1):
        console.print(f"[dim]run {i}/{args.runs} …[/dim]", end="\r")
        try:
            events = _one_run(args.config, task)
            m = _metrics(events)
            m["property_status"] = {r.spec.id: r.status.value
                                    for r in evaluate_trace(events)}
        except Exception as exc:  # noqa: BLE001
            m = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                 "kb_searched": False, "kb_articles": [], "tool_calls": None,
                 "agent_steps": None, "iterations": None, "tokens": None,
                 "answer_chars": 0, "agent_history": None, "tool_sequence": [],
                 "property_status": {}}
        rows.append(m)
        if i < args.runs:
            time.sleep(args.delay)

    # --- per-run table ---------------------------------------------------
    table = Table(title="Risultati per run", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("ok"); table.add_column("KB?")
    table.add_column("articoli KB"); table.add_column("tool", justify="right")
    table.add_column("steps", justify="right"); table.add_column("iter", justify="right")
    table.add_column("token", justify="right"); table.add_column("ans", justify="right")
    for i, m in enumerate(rows, 1):
        table.add_row(
            str(i),
            "[green]✓[/green]" if m["ok"] else "[red]✗[/red]",
            "[green]sì[/green]" if m["kb_searched"] else "[yellow]no[/yellow]",
            ", ".join(m["kb_articles"]) or "—",
            str(m["tool_calls"] if m["tool_calls"] is not None else "—"),
            str(m["agent_steps"] if m["agent_steps"] is not None else "—"),
            str(m["iterations"] if m["iterations"] is not None else "—"),
            str(m["tokens"] if m["tokens"] is not None else "—"),
            str(m["answer_chars"]))
    console.print(table)

    # --- aggregates ------------------------------------------------------
    ok = [m for m in rows if m["ok"]]
    n_ok = len(ok)
    searched = sum(1 for m in ok if m["kb_searched"])
    iters = [m["iterations"] for m in ok if m["iterations"] is not None]
    toks = [m["tokens"] for m in ok if m["tokens"] is not None]
    kb_sets = Counter(", ".join(m["kb_articles"]) or "(nessuno)" for m in ok)
    trajectories = Counter(
        tuple(m["agent_history"]) if m["agent_history"] else tuple(m["tool_sequence"])
        for m in ok)

    def stat(xs):
        if not xs:
            return "—"
        return (f"min {min(xs)} · media {statistics.mean(xs):.1f} · "
                f"max {max(xs)} · stdev {statistics.pstdev(xs):.1f}")

    summary_txt = (
        f"run riuscite: [bold]{n_ok}/{len(rows)}[/bold]\n"
        f"hanno cercato in KB: [bold]{searched}/{n_ok}[/bold] "
        f"({(100*searched/n_ok if n_ok else 0):.0f}%)\n"
        f"iterazioni: {stat(iters)}\n"
        f"token: {stat(toks)}\n\n"
        f"[bold]Articoli KB recuperati (distribuzione):[/bold]\n" +
        "\n".join(f"  {cnt:>3}×  {k}" for k, cnt in kb_sets.most_common()) +
        f"\n\n[bold]Traiettorie distinte:[/bold] {len(trajectories)}\n" +
        "\n".join(f"  {cnt:>3}×  {' → '.join(t)}" for t, cnt in trajectories.most_common()))
    console.print(Panel(summary_txt, title="[bold]Aggregato (non-determinismo)",
                        border_style="cyan"))

    # --- certification properties across runs ---------------------------
    prop_fail: Counter = Counter()
    prop_appl: Counter = Counter()   # run in cui la proprietà è applicabile (non N/A)
    for m in ok:
        for pid, st in m.get("property_status", {}).items():
            if st != "na":
                prop_appl[pid] += 1
            if st == "fail":
                prop_fail[pid] += 1
    ptable = Table(title="Proprietà di certificazione (violazioni su run valutabili)",
                   show_lines=False)
    ptable.add_column("Proprietà", style="bold")
    ptable.add_column("Classe")
    ptable.add_column("FAIL / valutabili", justify="right")
    ptable.add_column("tasso", justify="right")
    for pid, spec in SPECS.items():
        appl = prop_appl.get(pid, 0)
        fail = prop_fail.get(pid, 0)
        rate = f"{(100*fail/appl):.0f}%" if appl else "—"
        style = "red" if fail else "green"
        ptable.add_row(spec.name, spec.cls,
                       f"[{style}]{fail}[/{style}] / {appl}", rate)
    console.print(ptable)

    # --- save JSON summary ----------------------------------------------
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    out = EXPERIMENTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{args.config}.json"
    out.write_text(json.dumps({
        "config": args.config, "task": task, "runs": len(rows),
        "model": config.MODEL, "temperature": config.TEMPERATURE,
        "kb_searched_count": searched, "ok_count": n_ok,
        "kb_article_distribution": dict(kb_sets),
        "trajectory_distribution": {" → ".join(t): c for t, c in trajectories.items()},
        "property_violations": {pid: {"fail": prop_fail.get(pid, 0),
                                      "applicable": prop_appl.get(pid, 0)}
                                for pid in SPECS},
        "per_run": rows,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    console.print(f"[dim]Riepilogo salvato in:[/dim] {out}")


if __name__ == "__main__":
    main()
