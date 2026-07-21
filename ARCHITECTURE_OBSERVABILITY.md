# Architettura di osservabilità — punti di sonda e schema eventi

Questo documento descrive **come** il sistema è strumentato: dove sono i punti
di hook, che eventi emettono, come sono aggregati, e con quale schema. Serve
a chi debba estendere il sistema (nuova evidenza, nuova macro) o a chi
voglia mappare 1:1 il codice sulle categorie del documento delle evidenze.

---

## Vista d'insieme

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Business logic (src/demo/)                                               │
│                                                                           │
│    ┌─────────────┐   ┌───────────────┐   ┌───────────────┐                │
│    │ orchestrator│──▶│ agents (7)     │──▶│ tools (4)     │                │
│    └─────────────┘   └───────────────┘   └───────────────┘                │
│           │                 │                    │                        │
│           ▼                 ▼                    ▼                        │
│                    Recorder (façade)                                      │
│                           │                                               │
└───────────────────────────┼───────────────────────────────────────────────┘
                            ▼
                ┌────────────────────────┐
                │  TraceEvent (dataclass)│  ── schema unico ──
                └────────────────────────┘
                            │
                            ▼
        ┌─────────────┐   ┌──────────────────────────────────────┐
        │ EventStore  │──▶│ experiments/<exp_id>/runs/<rid>.jsonl│
        └──────┬──────┘   └──────────────────────────────────────┘
               │
               ▼ (fan-out live)
        ┌───────────────┐    ┌────────────────────────────────────┐
        │ event_sink    │───▶│ Web UI (SSE stream)                │
        └───────────────┘    └────────────────────────────────────┘

Fine-batch:
    ExperimentStore → Aggregator → aggregate/metrics.json
                                          │
                                          ▼
                                     Web UI (viste per macro)
```

Ogni pezzo è isolato in un modulo dedicato:

| Modulo                                   | Responsabilità |
|------------------------------------------|-----------------|
| `src/instrumentation/events.py`          | Schema evento unico + enum (macro, canali, tipi) |
| `src/instrumentation/recorder.py`        | Façade per gli agenti/orchestratore. Chi vuole emettere un evento chiama qui. |
| `src/instrumentation/store.py`           | Persistenza append-only JSONL + indice esperimento |
| `src/instrumentation/session.py`         | Ciclo di vita run/esperimento + `run_id`/`experiment_id` |
| `src/instrumentation/aggregator.py`      | Costruzione metriche per macro (A1..A4, B1..B4, C1..C4) |
| `src/demo/*`                    | Il use case ricco (stato, agenti, orchestratore, grafo, runner) |
| `webapp/server.py`                       | HTTP + SSE per la UI live |
| `webapp/static/index.html`               | UI a tre viste |

**Idea guida**: la business logic emette eventi ad alto livello via `Recorder`
(`recorder.orchestrator_decision(...)`, `recorder.tool_call(...)`, ecc.).
Non conosce JSONL, canali AgentLeak, UI, SSE.

---

## Schema evento (TraceEvent)

```jsonc
{
  "event_id":         "hex16",                 // univoco per evento
  "run_id":           "run_<hex12>",           // univoco per run
  "experiment_id":    "exp_<hex12>",           // univoco per esperimento
  "macro_categories": ["control_flow", "..."], // una o più macro
  "event_type":       "orchestrator_decision", // vedi EventKind
  "channel_id":       "C2" | null,             // canale AgentLeak se applicabile
  "agent_id":         "planner",               // chi ha prodotto l'evento
  "source_component": "planner",               // sorgente architetturale
  "target_component": "orchestrator" | null,   // destinazione se esiste
  "tool_name":        "fetch_logs" | null,     // per gli eventi tool
  "timestamp_start":  1730000000000,           // ms
  "timestamp_end":    1730000000045,
  "duration_ms":      45,
  "payload_summary":  "leggibile in UI",
  "payload_redacted": {"...": "..."},
  "metadata":         {"reason": "..."}
}
```

### Valori di `event_type`

Sono in `EventKind` (`src/instrumentation/events.py`):

**Control Flow**
- `orchestrator_decision` (A1): ogni decisione di routing dell'orchestratore.
  - `metadata.reason`, `metadata.alternatives`, `metadata.step`, `metadata.context_snapshot_keys`.
- `planning_span` (A2): piano prodotto da un agente planner.
  - `metadata.plan` (lista), `metadata.n_steps`, `metadata.updated`.
- `replanning` (A2 bis): revisione di un piano precedente.
- `handoff` (A3): passaggio di controllo. `source_component` → `target_component`.
- `path_metric` (A4): riservato per future metriche aggregate emesse a run-end.

**Data Flow** (canale AgentLeak in `channel_id`)
- `tool_call` (C3): input a un tool.
- `tool_result` (C4): output di un tool.
- `inter_agent_msg` (C2): messaggio tra due agenti.
- `shared_memory_write` (C5) / `shared_memory_read` (C5).
- `final_output` (C1): output finale verso l'utente.
- `reasoning_step` (C6): reasoning trace / Thought.
- `artifact_produced` (C7): artefatto persistente (report, riepilogo).
- `channel_emission`: catch-all per canali arbitrari (usato raramente).

**Behavioral**
- `decision_point`: punto di scelta significativo (classification, priority, ecc.).
  - `metadata.label`, `metadata.choice`.
- `state_snapshot`: fotografia dello stato consolidato.
  - `metadata.state` (dict), `metadata.label`.
- `trajectory_step`: catch-all per un passo generico della traiettoria.

**Meta**
- `run_metadata`: prima riga della trace, contiene modello/temperatura/ticket.
- `run_end`: chiusura della run, con `metadata.outcome`.
- `error`: eccezione o errore di dominio.

### Mapping evento → macro

In `KIND_TO_MACROS`. Un evento può contribuire a più macro: per esempio,
`handoff` è sia CF (segna un passaggio di controllo) sia DF (documenta il
payload trasferito). L'aggregator legge questa mappa per decidere dove
contare l'evento.

### Mapping evento → canale AgentLeak

In `KIND_TO_CHANNEL`. Il `build_event()` di `events.py` popola
automaticamente `channel_id` dal tipo di evento, quando applicabile.

---

## Dove sono i punti di hook

Nel dettaglio, per ciascuna macro:

### Control Flow

| Hook | File | Chi lo chiama | Evidenza |
|------|------|---------------|----------|
| `orchestrator_decision` | `src/demo/orchestrator.py::orchestrator_node` | l'orchestratore, a ogni iterazione | A1 |
| `handoff` | idem, subito dopo la decisione | orchestratore | A3 (parte control-side) |
| `planning_span` | `src/demo/agents.py::planner` | agente planner | A2 |
| `replanning` | (attivo se planner produce un piano rivisto) | planner | A2 bis |

Le regole di routing (`ROUTING_RULES` in `orchestrator.py`) sono la guardia
G(v) su cui l'orchestratore decide. Sono **deterministiche e dichiarative**:
ispezionabili senza eseguire il sistema.

### Data Flow (canali C1..C7)

| Canale | Emesso da | Nel codice |
|--------|-----------|-----------|
| C1 · Final output | Summarizer | `recorder.final_output(...)` in `agents.py::summarizer` |
| C2 · Inter-agent messages | Ogni agente che notifica un altro | `recorder.inter_agent_msg(from, to, subject, content)` |
| C3 · Tool input | Ogni agente prima della chiamata | `recorder.tool_call(agent, name, args)` |
| C4 · Tool output | Ogni agente dopo la chiamata | `recorder.tool_result(agent, name, result, success)` |
| C5 · Shared memory | Ogni agente che legge/scrive workspace | `recorder.shared_memory_read/write(agent, key, ...)` |
| C6 · Reasoning trace | Ogni agente che riflette | `recorder.reasoning_step(agent, thought)` |
| C7 · Persistent artifact | Summarizer per il report finale | `recorder.artifact(agent, name, kind, content)` |

Il vocabolario V e l'Allowed Set A per canale sono in
`aggregator.py`: `VAULT_PATTERNS` (regex per email, phone, reporter, ip,
userid) e `ALLOWED_SET_A` (mapping canale → categorie ammesse). Modificarli
è il passo naturale per adattare la demo a uno scenario diverso (§3.4 PDF).

### Behavioral

| Hook | File | Chi lo chiama | Evidenza |
|------|------|---------------|----------|
| `decision_point` | tutti gli agenti nei momenti chiave | `agents.py` (planner, log_investigator, metrics_analyst, postmortem_retriever, classifier) | C3 |
| `state_snapshot` | Summarizer al termine | `agents.py::summarizer` | C2 |
| `trajectory_step` | riservato: la traiettoria è ricostruita a fine batch dall'Aggregator | Aggregator | C1 |

C4 (varianza) è calcolata **a fine batch** dall'Aggregator: nessun evento
dedicato, solo aggregazione statistica su tutte le run.

---

## Contratto Aggregator → UI

L'Aggregator produce un dict con esattamente questa struttura:

```jsonc
{
  "control_flow": {
    "A1_orchestrator_decisions": {name, where, how, per_run, total, distribution_of_targets, samples},
    "A2_planning_spans":         {name, where, how, per_run, replanning_per_run, total_plans, total_replans, samples},
    "A3_handoffs":               {name, where, how, per_run, total, edges, samples},
    "A4_path_metrics":           {name, where, how, per_run, aggregate}
  },
  "data_flow": {
    "B1_channel_trace":          {name, where, how, per_channel},
    "B2_channel_leakage_rate":   {name, where, how, vault_categories, per_channel},
    "B3_system_leakage_rate":    {name, where, how, S, runs_with_any_leak, n_runs, slr_proxy},
    "B4_policy":                 {name, where, how, vault_V, allowed_set_A}
  },
  "behavioral": {
    "C1_trajectories":           {name, where, how, n_runs, trajectories},
    "C2_state_output":           {name, where, how, per_run},
    "C3_decision_coherence":     {name, where, how, per_run},
    "C4_behavioral_variance":    {name, where, how, trajectory_signatures, signature_entropy_norm,
                                  final_classification_dist, classification_entropy_norm,
                                  final_priority_dist, priority_entropy_norm, n_runs}
  }
}
```

Nome dei campi = nome dell'evidenza nel documento (per esempio
`A1_orchestrator_decisions` corrisponde all'evidenza §2.1 A1).

Il file `experiments/<exp_id>/aggregate/metrics.json` contiene esattamente
questo dict. La UI lo consuma via `GET /api/experiment/<experiment_id>` o
tramite il messaggio finale del SSE stream (`progress.kind == 'experiment_end'`).

---

## Come aggiungere una nuova evidenza

1. Se nuovo `event_type`: aggiungerlo a `EventKind` e alla mappa `KIND_TO_MACROS`
   (e a `KIND_TO_CHANNEL` se attiene a un canale AgentLeak).
2. Se serve un metodo di comodità: aggiungerlo al `Recorder`.
3. Chiamarlo dal codice di dominio nel punto giusto.
4. Nell'Aggregator, aggiungere la logica di conteggio nel metodo della macro
   corrispondente (`for_control_flow`, `for_data_flow`, `for_behavioral`).
5. Nella UI (`index.html`) aggiungere una `evidenceCard(...)` nella vista
   della macro.

Non serve modificare lo storage: JSONL è agnostico al tipo.

---

## Disattivare / disaccoppiare la strumentazione

- La strumentazione è opt-in: se nessuno chiama `Recorder`, non produce
  eventi. La business logic funziona lo stesso (il grafo LangGraph non
  dipende dal Recorder — solo gli hook agli agenti lo usano).
- Per disaccoppiare completamente dallo storage: passa un `EventStore`
  in-memory (`subscribers=[callback]` senza scrittura su file). Il codice
  è già predisposto perché `EventStore` è il solo componente che tocca il
  file system.

## Modello

Il modello LLM di default è `openai/gpt-oss-120b` (vedi `.env`). Configurabile
via `MODEL=...` in `.env`. Il modello è **mostrato nella UI** in alto e
salvato nei metadati di ogni esperimento (`experiments/<id>/experiment.json`).
