"""Evaluate the certification properties against a trace file.

    python check.py --latest                 # ultima traccia in ./traces/
    python check.py --trace traces/<file>.jsonl

Stampa, per ogni proprietà: classe, enunciato, verdetto (PASS/FAIL/N/A) e le
evidenze tratte dalla traccia. È la lettura "certificativa" di una singola run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.properties import Status, evaluate_trace, summarize

ROOT = Path(__file__).resolve().parent
TRACES = ROOT / "traces"

_STATUS_STYLE = {
    Status.PASS: ("[bold green]PASS[/bold green]", "green"),
    Status.FAIL: ("[bold red]FAIL[/bold red]", "red"),
    Status.NA: ("[dim]N/A[/dim]", "dim"),
}


def _load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def render_report(console: Console, events: list[dict], title: str) -> int:
    meta = next((e["payload"] for e in events
                 if e["event_type"] == "run_metadata"), {})
    console.rule(f"[bold cyan]CERTIFICATION REPORT · {title}")
    console.print(f"[dim]config:[/dim] {meta.get('configuration')}  "
                  f"[dim]model:[/dim] {meta.get('model')}  "
                  f"[dim]task:[/dim] {meta.get('task', '')[:70]}\n")

    results = evaluate_trace(events)
    table = Table(show_lines=True, expand=True)
    table.add_column("Proprietà", style="bold", no_wrap=True)
    table.add_column("Classe", no_wrap=True)
    table.add_column("Verdetto", no_wrap=True)
    table.add_column("Dettaglio + evidenze")
    for r in results:
        badge, _ = _STATUS_STYLE[r.status]
        ev = "\n".join(f"[dim]· {e}[/dim]" for e in r.evidence)
        body = r.detail + (f"\n{ev}" if ev else "")
        table.add_row(r.spec.name, r.spec.cls, badge, body)
    console.print(table)

    c = summarize(results)
    style = "red" if c["fail"] else "green"
    console.print(Panel(
        f"PASS [green]{c['pass']}[/green]   FAIL [red]{c['fail']}[/red]   "
        f"N/A [dim]{c['na']}[/dim]",
        title="Sintesi", border_style=style))
    return c["fail"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Certification property checker")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--trace", help="percorso del file .jsonl")
    g.add_argument("--latest", action="store_true", help="usa l'ultima traccia in ./traces/")
    args = parser.parse_args()

    if args.latest:
        traces = sorted(TRACES.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not traces:
            raise SystemExit("Nessuna traccia in ./traces/. Lancia prima una run.")
        path = traces[-1]
    else:
        path = Path(args.trace)

    console = Console()
    fails = render_report(console, _load(path), path.name)
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
