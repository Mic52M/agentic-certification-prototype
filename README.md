# Agentic Certification Prototype

Prototipo dimostrativo per la ricerca sulla **certificazione di sistemi LLM-based
agentic** (estensione del framework TIST 2026 al setting agentic).

Mostra due architetture agentiche su un piccolo task di troubleshooting tecnico
(assistente di posta elettronica aziendale fittizia) e produce **tracce JSONL
ispezionabili** che evidenziano i punti di variabilità, controllo e osservabilità
rilevanti per la certificazione.

> Lo scopo NON è risolvere bene il task, ma rendere visibile *come* il sistema
> opera. Per il contesto completo vedi [`PROJECT_KNOWLEDGE.md`](PROJECT_KNOWLEDGE.md).

## Configurazioni

| Config | Descrizione |
|---|---|
| `single_agent` | Un agente, loop ReAct esplicito (Thought/Action/Observation), max 10 iterazioni. |
| `multi_agent` | Orchestratore deterministico + IntentClassifier / Retriever / Responder, comunicanti solo tramite stato condiviso Pydantic. |

Stesso modello per tutto: **Qwen 3 32B** via **Groq** (`qwen/qwen3-32b`).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # inserisci la tua GROQ_API_KEY
```

La chiave Groq (free tier) si crea su <https://console.groq.com/keys>.

## Uso

```bash
python run.py --config single_agent \
  --task "L'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."

python run.py --config multi_agent \
  --task "L'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."
```

Durante l'esecuzione l'output viene stampato a video (colorato, per la demo live) e
salvato in `./traces/{timestamp}_{config}_{taskhash}.jsonl`.

Ticket di esempio: `T-001`..`T-007`. Articoli KB: `KB-001`..`KB-008`
(vedi `data/`).

## Manuale dei comandi

```bash
python manual.py        # elenco di tutti i comandi del prototipo
```

## Esperimento — N run sullo stesso task (non-determinismo)

```bash
python experiment.py --config multi_agent --ticket T-004 --runs 20
python experiment.py --config single_agent --task "..." --runs 10 --delay 1.5
```

Lancia lo stesso task N volte e quantifica il non-determinismo: tabella per-run
(KB cercata? quali articoli, iterazioni, token, lunghezza traiettoria) + aggregato
(percentuali, statistiche, distribuzione delle traiettorie e degli articoli KB).
Salva un riepilogo JSON in `./experiments/`. Flag: `--runs N` (default 10),
`--ticket ID` oppure `--task "..."`, `--delay sec` (default 1.0, per il rate limit).

## Web UI — live view (vedere gli agenti lavorare in tempo reale)

Oltre al terminale, c'è un'interfaccia web locale che mostra **in tempo reale**
quale nodo lavora, come comunica con l'orchestratore e come muta lo stato condiviso.

```bash
python -m webapp.server        # poi apri http://127.0.0.1:8000
```

Nella pagina: scegli la configurazione e il ticket, premi **Run**. Vedrai il grafo
con il nodo attivo evidenziato, gli archi orchestratore↔agente che si "accendono"
a ogni routing, il pannello dello **stato condiviso** che cambia (campi mutati
evidenziati) e lo **stream di eventi** live. È lo stesso flusso di eventi del JSONL,
inviato al browser via Server-Sent Events — non un log separato: una sola sorgente,
due sink. Richiede `GROQ_API_KEY` (esegue una run reale).

## Tracce JSONL

Prima riga = metadati del run (code hash, versioni librerie, model, sampling,
system prompt completi, schema dello stato, regole di routing). Ogni riga
successiva = un evento: `agent_step`, `tool_call`, `tool_result`,
`orchestrator_decision`, `state_transition`, `final_answer`.

Ispezione rapida:
```bash
cat traces/<file>.jsonl | jq .             # se hai jq
python -c "import json,sys; [print(json.loads(l)['event_type']) for l in open(sys.argv[1])]" traces/<file>.jsonl
```

## Smoke test (offline, senza API key)

```bash
python tests/smoke_test.py
```
Usa un LLM stub scriptato per validare data loading, tool, parsing, entrambi i
grafi e la scrittura delle tracce.

## Note

- Versioni delle dipendenze pinnate in `requirements.txt` (LangGraph cambia API
  spesso — non aggiornare alla cieca).
- Niente DB / vector store / UI: tutto in memoria e da terminale.
