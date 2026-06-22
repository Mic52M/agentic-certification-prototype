"""Command reference for the prototype — a small built-in man page.

    python manual.py            # stampa l'elenco dei comandi
    python manual.py --man      # idem (alias)

Tienilo aggiornato quando aggiungi un nuovo entry point.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

COMMANDS = [
    ("Setup (una tantum)",
     "python -m venv .venv && source .venv/bin/activate\n"
     "pip install -r requirements.txt\n"
     "cp .env.example .env   # poi inserisci GROQ_API_KEY",
     "Crea l'ambiente, installa le dipendenze pinnate, configura la API key Groq."),

    ("Run singola — agente singolo",
     'python run.py --config single_agent \\\n'
     '  --task "L\'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."',
     "Esegue una run del loop ReAct mono-agente. Stampa la traccia a video (rich) "
     "e salva il JSONL in ./traces/."),

    ("Run singola — multi-agente",
     'python run.py --config multi_agent \\\n'
     '  --task "L\'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."',
     "Esegue una run con orchestratore deterministico + IntentClassifier/Retriever/"
     "Responder. Stessa traccia JSONL + eventi handoff e state_transition."),

    ("Web UI — live view",
     "python -m webapp.server      # poi apri http://127.0.0.1:8000",
     "Interfaccia web locale: grafo con nodo attivo, archi orchestratore↔agente che "
     "si accendono, stato condiviso live, stream eventi. Richiede GROQ_API_KEY."),

    ("Esperimento — N run sullo stesso task",
     "python experiment.py --config multi_agent --ticket T-004 --runs 20\n"
     "python experiment.py --config single_agent --task \"...\" --runs 10 --delay 1.5",
     "Lancia lo stesso task N volte e quantifica il non-determinismo: tabella per-run "
     "(KB cercata? quali articoli, iterazioni, token) + aggregato. Salva in ./experiments/.\n"
     "Flag: --runs N (default 10), --ticket ID | --task \"...\", --delay sec (default 1.0)."),

    ("Smoke test (offline, senza API key)",
     "python tests/smoke_test.py",
     "Valida data/tool/parsing/grafi/tracce con un LLM stub. Non chiama Groq."),

    ("Questo manuale",
     "python manual.py",
     "Stampa questo elenco di comandi."),
]

NOTES = (
    "[bold]Output[/bold]\n"
    "  ./traces/       una traccia JSONL per ogni run (prima riga = metadati).\n"
    "  ./experiments/  riepiloghi JSON degli esperimenti N-run.\n\n"
    "[bold]Configurazioni[/bold]\n"
    "  single_agent  — un agente, loop ReAct esplicito (max 10 iterazioni).\n"
    "  multi_agent   — orchestratore deterministico + 3 agenti specializzati.\n\n"
    "[bold]Modello[/bold]  Qwen 3 32B via Groq (qwen/qwen3-32b), temperature 0.0."
)


def main() -> None:
    console = Console()
    console.print(Panel.fit(
        "[bold cyan]Agentic Certification Prototype[/bold cyan] — comandi disponibili",
        border_style="cyan"))
    table = Table(show_lines=True, expand=True)
    table.add_column("Cosa", style="bold", no_wrap=True)
    table.add_column("Comando", style="green")
    table.add_column("Descrizione")
    for name, cmd, desc in COMMANDS:
        table.add_row(name, cmd, desc)
    console.print(table)
    console.print(Panel(NOTES, title="Note", border_style="dim"))


if __name__ == "__main__":
    main()
