# src/demo — la demo attuale (incident triage)

Il use case ricco che alimenta la web UI. Caso: un tecnico di service desk apre
un incident con sintomi multipli; il sistema deve leggere il ticket, raccogliere
evidenze da fonti diverse (log, metriche, postmortem passati), classificare,
proporre un report tecnico con azioni.

L'obiettivo *demo*: produrre a ogni run un volume ricco di eventi osservabili su
tutte e tre le macro-dimensioni di ricerca (control flow, data flow,
behavioural), senza pretendere di risolvere bene il task.

## Dove sta cosa (in questa cartella)

| File | Cosa contiene |
|---|---|
| `agents.py` | I 7 agenti come funzioni-factory che restituiscono un nodo LangGraph: `build_reader_node`, `build_planner_node`, `build_log_investigator_node`, `build_metrics_analyst_node`, `build_postmortem_retriever_node`, `build_classifier_node`, `build_summarizer_node`. Chi usa LLM: planner, classifier, summarizer. Gli altri sono deterministici (tool + logica). |
| `orchestrator.py` | Le **regole di routing** (`ROUTING_RULES`, lista ordinata di predicati `(condizione, target, motivo)`), il branching non banale (metriche-first se sintomo di performance, log-first per errori) e la factory del nodo orchestratore. |
| `graph.py` | Il grafo LangGraph hub-and-spoke: `START → orchestrator → {agente scelto} → orchestrator → … → END`. |
| `tools.py` | I 4 tool: `read_incident`, `fetch_logs`, `fetch_metrics`, `query_postmortems`. Leggono da `data/demo/`. |
| `state.py` | `IncidentState` (schema Pydantic dello state del grafo) + `SharedWorkspace` (memoria condivisa C5). |
| `prompts.py` | I system prompt di ciascun agente LLM. |
| `runner.py` | Multi-run runner: esegue N run indipendenti dello stesso ticket dentro un `experiment_id` condiviso, alimenta gli `event_sink` (per lo streaming SSE alla UI) e chiama l'`Aggregator` a fine batch. |

## Dipendenze esterne al pacchetto

- `src/instrumentation/` — layer di raccolta/aggregazione delle evidenze (le
  chiamate `recorder.tool_call(...)`, `recorder.decision_point(...)`, ecc.).
- `src/config.py` — path del dataset e configurazione modello.
- `src/llm_client.py` — client Groq (planner/classifier/summarizer lo usano).
- `src/parsing.py` — estrazione JSON dagli output LLM.

Nessuna dipendenza da `src/legacy/`.

## Dataset associato

`data/demo/incidents.json`, `data/demo/app_logs.json`, `data/demo/metrics.json`,
`data/demo/postmortems.json`.
