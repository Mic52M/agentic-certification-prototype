# src/legacy — vecchio prototipo

Prima versione del prototipo: assistente di troubleshooting per un servizio di
posta aziendale, con due configurazioni (single agent ReAct e multi-agent con
orchestratore rule-based) e un ticket tipo "password bloccata".

**Non è usato dalla demo attuale** (che è in `src/demo/`), ma resta nel repo per:

- gli entry point CLI `run.py`, `check.py`, `experiment.py` in root;
- il property checker (`properties.py`) usato da `check.py`;
- lo smoke test `tests/smoke_test.py` che verifica offline i vecchi grafi.

Se stai lavorando alla demo (`src/demo/` + `src/instrumentation/` + `webapp/`),
puoi ignorare completamente questa cartella. Non c'è nessun import da qui a
`src/demo/` (né viceversa): le due generazioni convivono ma non si toccano.

## Contenuto

- `single_agent/agent.py` — grafo LangGraph con loop ReAct esplicito.
- `multi_agent/{agents,graph,orchestrator}.py` — orchestratore rule-based con 3
  agenti specializzati (IntentClassifier, Retriever, Responder).
- `state.py` — `MultiAgentState` / `SingleAgentState` (Pydantic).
- `tools.py` — `search_knowledge_base` + `read_ticket` sul dataset
  `data/legacy/`.
- `prompts.py` — system prompt dei vecchi agenti.
- `properties.py` — property checker con 5 proprietà non-funzionali
  (kb_search_performed, answer_groundedness, citation_faithfulness,
  bounded_termination, output_parseability).
- `logging_utils.py` — vecchio `TraceLogger` (JSONL semplificato, base della
  successiva `src/instrumentation/`).

## Dataset associato

`data/legacy/knowledge_base.json` e `data/legacy/tickets.json`.
