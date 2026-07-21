# Struttura del progetto — mappa "dove sta cosa"

Il repo contiene due generazioni di codice, e questa guida serve a distinguerle
a colpo d'occhio.

```
agentic-certification-prototype/
├── src/
│   ├── demo/               ← LA DEMO ATTUALE (incident triage)
│   ├── instrumentation/    ← layer di raccolta eventi + aggregazione per macro
│   ├── legacy/             ← vecchio prototipo (mail troubleshooting)
│   ├── config.py           ← paths, modello, N run, temperatura
│   ├── llm_client.py       ← client Groq (usato da demo e legacy)
│   └── parsing.py          ← utility JSON per ReAct (usata da entrambi)
├── data/
│   ├── demo/               ← dataset della demo attuale
│   └── legacy/             ← dataset del vecchio prototipo
├── webapp/                 ← UI a 4 tab della demo attuale
├── tests/                  ← smoke test (uno per legacy, uno per demo)
├── experiments/            ← output runtime degli esperimenti (gitignored)
├── traces/                 ← output runtime del legacy (gitignored)
└── run.py, check.py, experiment.py, manual.py  ← entry point legacy CLI
```

---

## LA DEMO ATTUALE — `src/demo/`

È il use case usato dalla web UI, dove giri gli esperimenti multi-run.
Caso d'uso: incident triage multi-agente con orchestratore rule-based.

```
src/demo/
├── agents.py         ← i 7 AGENTI: Reader, Planner, Log Investigator,
│                       Metrics Analyst, PM Retriever, Classifier, Summarizer
├── orchestrator.py   ← LE REGOLE DI ROUTING (ROUTING_RULES list-based)
├── graph.py          ← grafo LangGraph (topologia hub-and-spoke)
├── tools.py          ← i 4 TOOL: read_incident, fetch_logs, fetch_metrics,
│                       query_postmortems
├── state.py          ← IncidentState + SharedWorkspace (memoria condivisa C5)
├── prompts.py        ← system prompt di ciascun agente LLM
└── runner.py         ← multi-run runner (N run dello stesso ticket)
```

## LA STRUMENTAZIONE — `src/instrumentation/`

Layer trasversale che raccoglie e aggrega le evidenze per le tre macro.

```
src/instrumentation/
├── events.py         ← schema unico TraceEvent + EventKind + canali C1..C7
├── recorder.py       ← façade: gli agenti chiamano recorder.tool_call(),
│                       recorder.handoff(), ecc. senza sapere di JSONL/UI
├── store.py          ← EventStore (JSONL append-only per-run) e
│                       ExperimentStore (indice esperimento + persistenza)
├── session.py        ← RunSessionManager: experiment_id / run_id / meta
└── aggregator.py     ← calcola LE METRICHE PER MACRO:
                          Control Flow  → A1 A2 A3 A4
                          Data Flow     → B1 B2 B3 B4 (canali C1..C7 AgentLeak)
                          Behavioural   → C1 C2 C3 C4
```

## I DATI — `data/demo/`

Dataset seed della demo attuale. Nomi parlanti.

```
data/demo/
├── incidents.json    ← i TICKET INCIDENT (INC-2026-014, INC-2026-015)
├── app_logs.json     ← log applicativi per servizio (mail-gateway, webmail)
├── metrics.json      ← metriche di sistema (CPU/mem/latency per componente)
└── postmortems.json  ← knowledge base di 5 postmortem passati
```

## LA WEBAPP — `webapp/`

Interfaccia a 4 tab (Trace agenti · Control Flow · Data Flow · Behavioural Flow).

```
webapp/
├── server.py         ← FastAPI + SSE (endpoint /api/experiment/stream)
└── static/
    └── index.html    ← UI a 4 tab, live stream degli eventi, viste per macro
```

---

## IL VECCHIO PROTOTIPO — `src/legacy/`

Prototipo iniziale (mail troubleshooting, ticket password). Non è usato dalla
demo attuale ma resta nel repo perché ha ancora entry point CLI utili
(`run.py`, `check.py`, `experiment.py`) e i suoi smoke test. Se non ti serve,
puoi ignorarlo.

```
src/legacy/
├── single_agent/     ← configurazione 1 del vecchio prototipo (ReAct loop)
├── multi_agent/      ← configurazione 2 del vecchio prototipo
├── state.py          ← MultiAgentState / SingleAgentState (vecchi)
├── tools.py          ← search_knowledge_base + read_ticket (vecchi)
├── prompts.py        ← system prompt del vecchio prototipo
├── properties.py     ← property checker (5 proprietà: kb_search_performed,
│                       answer_groundedness, citation_faithfulness,
│                       bounded_termination, output_parseability)
└── logging_utils.py  ← vecchio TraceLogger (JSONL semplificato)
```

Vedi anche `src/legacy/README.md` per il contesto storico.

---

## Comandi essenziali

```bash
# Setup (una volta)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # inserisci GROQ_API_KEY

# La demo attuale (l'unica cosa rilevante per il lavoro corrente)
python -m webapp.server        # http://127.0.0.1:8000

# Smoke test (offline, senza API key)
python tests/smoke_demo.py     # nuovo: strumentazione
python tests/smoke_test.py     # legacy: ancora verde

# Entry point legacy (se ancora ti servono)
python run.py --config multi_agent --task "..."
python check.py --latest
python experiment.py --config multi_agent --runs 20
python manual.py               # elenco comandi
```

---

## "Dove trovo…" — cheat sheet

| Cerchi… | Guarda qui |
|---|---|
| Le **regole** dell'orchestratore (routing) | `src/demo/orchestrator.py` → `ROUTING_RULES` |
| I **7 agenti** e i loro ruoli | `src/demo/agents.py` |
| I **4 tool** (incident, logs, metrics, postmortems) | `src/demo/tools.py` |
| I **prompt** di sistema | `src/demo/prompts.py` |
| I **ticket** incident | `data/demo/incidents.json` |
| I **log** applicativi (dataset seed) | `data/demo/app_logs.json` |
| Le **metriche** di sistema (dataset seed) | `data/demo/metrics.json` |
| I **postmortem** passati (KB) | `data/demo/postmortems.json` |
| Il calcolo delle **metriche per macro** | `src/instrumentation/aggregator.py` |
| Lo **schema evento** unificato | `src/instrumentation/events.py` |
| I **canali AgentLeak** C1..C7 (mapping) | `src/instrumentation/events.py` → `KIND_TO_CHANNEL` |
| La **UI** (HTML+CSS+JS) | `webapp/static/index.html` |
| Il **server** HTTP + SSE | `webapp/server.py` |
| I **path e la config** (modello, N run) | `src/config.py` |

## Convenzioni

- Ogni file dentro `src/` ha una docstring in cima che spiega il suo ruolo.
- I moduli sotto `src/legacy/` non importano nulla di `src/demo/` (né viceversa).
- L'unica dipendenza condivisa: `src/config.py`, `src/llm_client.py`, `src/parsing.py`.
- I dataset non sono modificati a runtime: sono in `data/` e sola lettura.
- L'output di runtime va in `traces/` (legacy) e `experiments/` (demo),
  entrambi gitignored.
