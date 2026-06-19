# PROJECT_KNOWLEDGE — Agentic Certification Prototype

> Handover doc. Read this first when resuming the project. Complete but synthetic.
> Last updated: 2026-06-19.

## 1. Contesto del progetto

Parte di ricerca di un paper accademico sulla **certificazione di sistemi
LLM-based agentic**. Il lavoro estende un framework di certificazione esistente
(TIST 2026 — Anisetti/Ardagna/Bena, Università di Milano) al setting agentic.

Il paper finale confronterà tre configurazioni architetturali — **agente singolo**,
**agente replicato in parallelo**, **multi-agente con orchestratore** — rispetto a
proprietà non-funzionali (robustness, safety, privacy).

**Questo repo NON è il paper.** È un **prototipo dimostrativo** per un meeting con i
supervisori (lunedì **23 giugno 2026**). Scopo unico: mostrare in modo *ispezionabile*
COME funzionano operativamente un agente singolo e un multi-agente con orchestratore,
e DOVE si inseriscono i punti di osservazione per la futura certificazione:

- **punti di variabilità** — dove il comportamento può divergere;
- **punti di controllo** — dove possiamo intervenire/vincolare;
- **hook di osservabilità** — dove possiamo "leggere" cosa succede.

Il prototipo **non deve risolvere bene il task**. Una traccia di esecuzione ricca e
leggibile vale più di una risposta finale corretta.

## 2. Stack tecnico (fissato — non rinegoziare)

- Python 3.11+ (sviluppato/testato su 3.13).
- **LangGraph 1.2.6** come libreria di orchestrazione (pinnata in `requirements.txt`).
- Modello LLM: **Qwen 3 32B** via **Groq API** (free tier, OpenAI-compatible).
  - Endpoint `https://api.groq.com/openai/v1`, model id Groq `qwen/qwen3-32b`.
  - API key da env `GROQ_API_KEY`.
- **ReAct ESPLICITO**: Thought-Action-Observation loggati a ogni iterazione. NIENTE
  function calling opaco — il modello emette JSON che parsiamo noi, così ogni
  decisione finisce nella traccia.
- Logging: ogni run produce un file **JSONL** in `./traces/`.
- **Pydantic 2.13.4** per gli schemi dei dati strutturati.
- Console output con **rich 14.2.0**.
- Niente DB, vector store, embedding, UI grafica. Tutto da terminale.

## 3. Le due configurazioni implementate

### Config 1 — Single agent (`src/single_agent/`)
Grafo LangGraph a ciclo: `START → agent → (final? finalize : tool) → agent`.
Un solo modello, un solo system prompt (`prompts.SINGLE_AGENT_SYSTEM`), gioca tutti
i ruoli. Loop ReAct esplicito, bounded da `MAX_ITERATIONS=10` (control point).
Rappresenta la baseline mono-agente del confronto del paper.

### Config 2 — Multi-agent con orchestratore (`src/multi_agent/`)
Grafo hub-and-spoke: `START → orchestrator → {intent_classifier | retriever |
responder} → orchestrator → … → END`.
- **Orchestrator** (`orchestrator.py`): routing **deterministico, rule-based** (NON
  LLM-driven). Le regole sono una lista ordinata dichiarativa `ROUTING_RULES` di
  `(predicato, next_node, reason)` — ispezionabile e riproducibile.
- **IntentClassifier / Retriever / Responder** (`agents.py`): stesso modello, system
  prompt diversi. Comunicano **solo** tramite lo stato condiviso Pydantic
  (`MultiAgentState`); nessun messaggio diretto agente→agente.
Rappresenta la configurazione multi-agente del confronto.

## 4. Logging JSONL — IL DELIVERABLE PIÙ IMPORTANTE

Un file per run in `./traces/`, nome `{timestamp}_{config}_{taskhash}.jsonl`.
Prima riga = metadati di run; ogni riga successiva = un evento.

Schema evento:
```json
{ "timestamp", "run_id", "configuration", "event_type",
  "node_name", "iteration", "payload": { ... } }
```

`event_type` e payload (vedi `src/logging_utils.py`, lista in `EVENT_TYPES`):
- `run_metadata` — prima riga. payload: code_hash, versioni librerie, model, sampling,
  `system_prompts` completi di tutti gli agenti, `state_schema`, (multi) `routing_rules`.
- `agent_step` — { thought, action{tool,args}, raw_llm_output, model, temperature }.
- `tool_call` — { tool_name, args }.
- `tool_result` — { tool_name, result, success }.
- `orchestrator_decision` (solo multi) — { next_node, reason, state_snapshot_keys }.
- `state_transition` (solo multi) — { before, after, diff }.
- `final_answer` — { answer, iterations_used, total_tokens }.

La stessa informazione è stampata a video colorata (rich) per la demo live.

### Mappa: dove sono i punti di certificazione
- **Variabilità**: ogni `agent_step` (output del modello, non deterministico anche a
  temp=0); il numero di iterazioni del loop; le query generate dal Retriever.
- **Controllo**: `MAX_ITERATIONS` (single); `ROUTING_RULES` (multi, deterministiche);
  `tools.execute_tool` (unico dispatch point dei tool); `llm_client.LLMClient.complete`
  (unico choke point verso il modello).
- **Osservabilità**: l'intero JSONL; in particolare `state_transition.diff` (multi)
  rende esplicita ogni mutazione dello stato condiviso.

## 5. Come lanciare

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # poi inserisci GROQ_API_KEY

python run.py --config single_agent --task "L'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."
python run.py --config multi_agent  --task "L'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."

python tests/smoke_test.py      # offline, NON serve la API key
```
Ticket disponibili: T-001..T-007 (`data/tickets.json`). KB: KB-001..KB-008.

## 5b. Web UI — live view (`webapp/`)

Aggiunta su richiesta esplicita (2026-06-19), **rilassando** il vincolo originale
"tutto da terminale". Interfaccia web locale per la demo: mostra in tempo reale
il grafo con il nodo attivo, gli archi orchestratore↔agente che si accendono a
ogni routing, il pannello dello stato condiviso (con campi mutati evidenziati) e
lo stream di eventi.

- `webapp/server.py`: FastAPI + uvicorn. `GET /api/run-stream` lancia una run in
  un thread e ne fa lo streaming via **Server-Sent Events**. Un `queue.Queue`
  fa da ponte tra il thread (bloccante) e la response async.
- `webapp/static/index.html`: pagina singola (SVG + JS vanilla, nessun framework).
- **Riusa esattamente lo stesso flusso di eventi del JSONL**: il `TraceLogger` ora
  accetta un `event_sink` opzionale (callback chiamata per ogni evento, oltre alla
  scrittura su file). Il web server passa `event_sink=queue.put`. Una sola sorgente
  di verità, due sink (file + browser). Non altera in alcun modo gli agenti.
- Avvio: `python -m webapp.server` → http://127.0.0.1:8000. Dipendenze pinnate:
  fastapi 0.137.2, uvicorn 0.49.0.

## 6. Cosa NON è (ancora) implementato e perché
- **Config "agente replicato in parallelo"** (3ª del paper): in pausa. Il prototipo
  copre le due architetture estreme (mono e multi-orchestrato); la replica parallela
  è una variazione che si aggiungerà quando serve per gli esperimenti.
- **Guardrails esterni** (filtri input/output, PII redaction, policy enforcement):
  non implementati. I choke point dove andrebbero (`execute_tool`, `LLMClient.complete`)
  sono già isolati apposta.
- **Benchmark avversari / robustness testing**: da integrare in futuro.
- **Sistema di valutazione automatica delle proprietà** (robustness/safety/privacy):
  fuori scope — verrà dopo, sopra le tracce JSONL prodotte qui.
- **Retry/rate-limiting sofisticati**: solo intercettazione base degli errori tool.
- **Test completi**: solo smoke test di plumbing (con LLM stub).

## 7. Decisioni di design (con motivazione)
- **ReAct via JSON parsato, non function calling**: il vincolo del paper è
  l'osservabilità. Il Thought deve essere prodotto in chiaro e finire nella traccia;
  il function calling lo nasconderebbe. Vedi `parsing.parse_react_action`.
- **`<think>` di Qwen3 strippato ma conservato**: Qwen3 su Groq emette blocchi
  `<think>…</think>`. Li rimuoviamo prima del parse JSON ma teniamo il `raw_llm_output`
  nella traccia (`LLMClient` conserva `raw_text`).
- **Stato Pydantic, non dict**: ogni mutazione tipata e ispezionabile; abilita gli
  eventi `state_transition` con diff. LangGraph accetta un BaseModel come state schema.
- **Routing orchestratore deterministico**: scelta di certificazione — il control flow
  tra agenti è ragionabile indipendentemente dal modello. Regole come dati (`ROUTING_RULES`).
- **Single agent come ciclo del grafo (agent↔tool)**, non loop Python opaco: il loop
  diventa parte ispezionabile del grafo; `MAX_ITERATIONS` è il control point esplicito.
- **Un solo dispatch tool (`execute_tool`) e un solo client LLM (`LLMClient`)**: choke
  point unici per futuri hook di controllo.
- **Parsing robusto con fallback osservabile**: se l'LLM non produce JSON valido, si
  emette un'action sentinella `_parse_error` invece di crashare — il fallimento stesso
  è loggato.
- **Retriever con mini-loop interno bounded** (`RETRIEVER_MAX_STEPS=4`): mostra un
  agente specializzato che usa più tool, senza loop infiniti.

## 8. Struttura file
```
run.py                      entry point CLI
src/config.py               env/.env, costanti, require_api_key()
src/llm_client.py           wrapper Groq (choke point modello)
src/tools.py                search_knowledge_base, read_ticket, execute_tool (dispatch)
src/state.py                Pydantic: SingleAgentState, MultiAgentState, ReActStep
src/parsing.py              estrazione/parse JSON ReAct
src/prompts.py              tutti i system prompt
src/logging_utils.py        TraceLogger (JSONL) + rendering rich
src/single_agent/agent.py   grafo config 1
src/multi_agent/orchestrator.py  ROUTING_RULES + nodo orchestratore
src/multi_agent/agents.py        intent_classifier, retriever, responder
src/multi_agent/graph.py         grafo config 2
data/{knowledge_base,tickets}.json   dati di esempio
tests/smoke_test.py         smoke test offline (LLM stub)
traces/                     output JSONL (gitignored)
```
