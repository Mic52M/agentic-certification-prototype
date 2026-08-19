# Paper Draft — Tassonomia delle Evidenze per la Certificazione di Sistemi Agentici

Documento vivo dedicato al **primo paper** del filone di ricerca:
una **tassonomia degli oggetti** che il framework di certificazione
utilizza per definire, raccogliere e caratterizzare le evidenze
necessarie a certificare un sistema agentico multi-agente.

Complementare (non duplicativo) rispetto a
[RESEARCH_DECISIONS.md](RESEARCH_DECISIONS.md): quel documento raccoglie
tutte le scelte del prototipo con razionale; questo tiene la
**spina dorsale** del primo paper e la manteniamo pronta per la scrittura.

**Scope autorizzato**: primo paper esclusivamente sulla tassonomia
(riferimento supervisore). Non tocca la questione "singolo agente vs
composizione" che è materia del [secondo paper pianificato].

---

## 0 · Meta

- **Autori previsti**: Bena, Anisetti, Damiani, Della Bruna, Yeun,
  Ardagna, Mastroberti.
- **Referente bibliografico prioritario**: Burkhard Stiller (tassonomie
  di verifica).
- **Target venue**: da definire (LNCS o journal focalizzato su
  service/agent certification).
- **Stato**: bozza in costruzione, contemporanea al prototipo.

---

## 1 · Contributo dichiarato

Il paper propone una **tassonomia formale** delle evidenze osservabili
necessarie a certificare un sistema agentico multi-agente. Nessuno degli
approcci correnti (agent evaluation, process mining su LLM, AgentLeak
per data-flow) fornisce una tassonomia unificata; il paper la introduce
articolando tre livelli:

1. Le **tre macro-dimensioni** di ricerca (Control Flow, Data Flow,
   Behavioral Flow) come **categorie ontologiche** della tassonomia.
2. Le **evidenze atomiche** all'interno di ciascuna macro (A1..A4 per
   CF, canali C1..C7 di AgentLeak per DF, C1..C4 per BH).
3. I **sette attributi tassonomici** che ogni evidenza deve dichiarare
   per essere trattata dal processo di certificazione (§ 5).

Il contributo scientifico è duplice:
- **Formale**: la tassonomia stessa come artefatto discutibile.
- **Empirico**: un prototipo funzionante (l'incident-triage
  multi-agente in questo repo) che dimostra tutti gli attributi sulla
  quasi totalità delle evidenze, con evidenza empirica delle celle
  scoperte e di quelle vuote.

---

## 2 · Sezioni previste del paper (bozza)

Struttura LaTeX proposta: sezioni con **due righe introduttive**
ognuna ("parleremo di A", "specificheremo B"), poi discussione articolata.

### §1 · Introduction
Introduciamo il problema della certificazione di sistemi agentici
multi-agente e argomentiamo perché una tassonomia unificata delle
evidenze è precondizione a qualunque schema di certificazione.

### §2 · Background
Riassumiamo tre filoni: agent evaluation (Confident AI, LangChain
observability), process mining classico (van der Aalst, Polyvyanyy),
data-flow governance per LLM-based systems (AgentLeak); mostreremo
perché nessuno da solo copre il setting agentico.

### §3 · Ontological Framing
Argomentiamo il salto ontologico ("proprietà probabilistica su
distribuzione di traiettorie" vs "predicato deterministico su singola
esecuzione") e la conseguente distinzione strutturale vs
comportamentale.

### §4 · The Three Categories (CF · DF · BH)
Definiamo le tre macro-dimensioni come categorie ontologiche della
tassonomia; motiviamo la scelta ternaria (non binaria, non
quaternaria).

### §5 · The Seven Attributes
Il cuore del paper: introduciamo lo schema a sette attributi (hook,
misura, momento, cadenza, ciclo di vita, regime statistico, radice
bibliografica) e discutiamo ciascuno come dimensione ortogonale.

### §6 · The Taxonomy Matrix
Presentiamo la matrice `evidenza × attributo` sulle
evidenze del prototipo. Discutiamo celle coperte, celle degenerate
(es. "one-shot per proprietà del modello"), celle vuote (buchi di
ricerca).

### §7 · Evidence Lifecycle
Discutiamo il **ciclo di vita** delle evidenze nel tempo:
stabili-in-run, monotone-crescenti, volatili, decaying. Argomentiamo
perché è dimensione centrale del framework: la certificazione dinamica
richiede di sapere *quando* un'evidenza smette di essere
rappresentativa.

### §8 · Evidence Collection Process
Discutiamo il **processo di collezione**: dove si aggancia la sonda,
qual è il punto architetturale corretto per ogni categoria, dove il
sistema smette di essere osservabile (blind spots).

### §9 · Empirical Validation
Mostriamo il prototipo che implementa la tassonomia: architettura
di raccolta, batch di run reali, dashboard che espone gli attributi
tassonomici. Screenshot commentati.

### §10 · Discussion & Limitations
Discutiamo limiti (proxy lessicali, PII detection baseline, singolo
dominio validato), rapporto col secondo paper (composizione vs
singolo).

### §11 · Related Work
Confronto puntuale con: Confident AI trace-based evals, RAGAS
groundedness, AgentLeak channels, van der Aalst conformance
checking, agent observability commerciale (LangSmith, Arize
Phoenix).

### §12 · Conclusion & Future Work
Riassumiamo il contributo tassonomico e delineiamo le direzioni:
metriche sliding-window (assenti nel prototipo), quasi-identifier
detection su data flow, tassonomia estesa alla composizione (paper 2).

---

## 3 · Le tre categorie della tassonomia

Le tre macro-dimensioni non sono un'invenzione ex-novo: sono già le
categorie di ricerca del framework TIST 2026. La novità del paper è
formalizzarle come **categorie ontologiche della tassonomia** e
riconoscere che ognuna ha caratteristiche distintive.

### 3.1 · Control Flow (CF)
Cattura la **struttura del percorso** che il sistema segue: quali
regole di routing vengono attivate, quali handoff avvengono, quali
pattern di orchestrazione emergono. Prevalentemente strutturale:
molte evidenze sono **verificabili classicamente** (conformance del
sottografo osservato al dichiarato).

### 3.2 · Data Flow (DF)
Cattura **cosa viaggia** sui canali di comunicazione fra agenti
(C1..C7 di AgentLeak). Prevalentemente *governance-oriented*: le
evidenze verificano l'aderenza a policy di data-minimization
dichiarate ex-ante (Vault V + Allowed Set A).

### 3.3 · Behavioral Flow (BH)
Cattura **come si comporta il sistema** a valle delle sue decisioni:
coerenza state ↔ output, sequenza intenzione ↔ comportamento,
stabilità cross-run. Prevalentemente statistico: le evidenze
richiedono N run e intervalli di confidenza.

**Perché ternaria e non binaria**: CF e DF potrebbero sembrare
riconducibili a "struttura vs dato". Ma BH non è né l'una né l'altra:
è la macro che rende osservabile il "control flow agentico interno
al singolo agente" (allineamento Anisetti), che né CF classico né
DF classico catturano. La ternarietà è ontologica, non didattica.

---

## 4 · Le evidenze atomiche

Elenchiamo le evidenze del prototipo, ordinate per macro. Il
dettaglio tecnico vive in [CONTROL_FLOW_METRICS.md](CONTROL_FLOW_METRICS.md);
qui riportiamo solo la lista come **oggetti** della tassonomia.

### 4.1 · CF: 22 metriche puntuali (A1..A4)
- A1 · Decisioni dell'orchestratore (A1.1..A1.5)
- A2 · Spans di pianificazione (A2.1..A2.5)
- A3 · Handoff fra agenti (A3.1..A3.6)
- A4 · Metriche di percorso (A4.1..A4.6)

### 4.2 · DF: 7 canali AgentLeak + 3 aggregati
- B1 · Tracce per canale (C1..C7)
- B2 · Channel Leakage Rate per canale
- B3 · System Leakage Rate aggregato
- B4 · Policy dichiarata (V, A, REDACTION derivata)

### 4.3 · BH: 4 evidenze (C1..C4)
- C1 · Trace end-to-end (regime substrato)
- C2 · Coerenza state ↔ output (regime coerenza per-run)
- C3 · Sequenza decisioni (regime coerenza per-run, tre check pairwise)
- C4 · Stabilità comportamentale (regime distribuzione cross-run)

---

## 5 · Gli undici attributi tassonomici (livello: DATO GREZZO)

**Correzione di framing rispetto alla bozza precedente**: la tassonomia
non è sulle metriche aggregate (A1.1, C4.8, ecc.) ma sui **dati grezzi
elementari** che alimentano quelle metriche. Le metriche sono il
risultato del processo di certificazione; la tassonomia caratterizza
la materia prima da cui le costruiamo.

Esempio concreto per chiarire il livello. La metrica A3.4
(anti-pattern bounces) non è oggetto della tassonomia. Sono oggetti
della tassonomia i **campi elementari** catturati ad ogni evento
`orchestrator_decision` per costruirla:

- `source_component: string`
- `target_component: string`
- `timestamp_start: int64 (ms)`
- `metadata.reason: string`
- `metadata.alternatives: list[string]`
- `metadata.step: int`
- `metadata.context_snapshot_keys: list[string]`

Ognuno di questi campi è un **dato grezzo** e riceve la propria scheda
tassonomica con gli undici attributi che seguono. Un'evidenza è
"caratterizzata" dalla scheda tassonomica di tutti i suoi dati grezzi.

Gli attributi sono **ortogonali**: ognuno risponde a una domanda
distinta del processo di certificazione.

### 5.1 · Name — nome del campo
La stringa che identifica il dato nel JSONL e nel codice
(`source_component`, `metadata.reason`, `payload_redacted.result`,
ecc.). Rilevante perché l'audit dev'essere ancorato al file reale, non
a un'astrazione documentale.

### 5.2 · Type — tipo dato
Dominio: `{string, int, float, timestamp_ms, boolean, list[T],
dict, categorical<enum>, text_free}`. `categorical<enum>` è il caso
in cui il dominio è chiuso (es. `outcome ∈ {completed, error, unknown}`);
`text_free` distingue il testo prosaico (thought, final_output) dal
resto perché ha implicazioni PII e di analisi diverse.

### 5.3 · Hook — sorgente architetturale
Chi produce il dato e a quale evento è agganciato. Dominio:
`{orchestrator, agent:<name>, tool_adapter:<name>, event_store,
recorder-builtin}`. `recorder-builtin` sono i campi che il recorder
aggiunge automaticamente (event_id, run_id, timestamps): sono presenti
ma non richiedono cooperazione del codice applicativo.

### 5.4 · Moment — momento di cattura
Quando nel flusso operativo il dato viene reso disponibile. Dominio:
- `pre-event`: prima che l'evento sorgente accada (es. `alternatives`
  è calcolato *prima* della scelta orchestrator).
- `during-event`: durante (es. args tool call).
- `post-event`: subito dopo (es. tool result, duration).
- `end-of-run`: a chiusura run (es. outcome, final state snapshot).
- `end-of-batch`: solo alla fine di N run (aggregati con IC).

### 5.5 · Cardinality — cardinalità per run
Quante volte il dato viene emesso in una singola run. Dominio:
- `1`: esattamente uno (es. `run_end.outcome`).
- `N=k`: costante conosciuta (es. in questo scenario 8
  `orchestrator_decision` per run).
- `variable-bounded`: dipende dallo scenario ma con bound (es. tool
  call ≤ MAX_ITERATIONS).
- `variable-unbounded`: teoricamente illimitato (es. reasoning steps
  in ReAct loops).

### 5.6 · Lifecycle — ciclo di vita del dato
La dimensione **cutting-edge** della tassonomia. Come si comporta il
dato nel tempo dopo la cattura. Dominio:
- `snapshot`: valore istantaneo al momento della cattura, non
  ricalcolabile identico (es. `timestamp_start`, `payload_size` dopo
  la scrittura).
- `stable-in-run`: una volta valorizzato non cambia durante la run
  (es. `run_id`, `incident_id`).
- `derived-deterministic`: calcolato da altri dati, ri-derivabile
  identico dai dati sorgente (es. `duration_ms = timestamp_end −
  timestamp_start`; `metadata.n_steps = len(plan)`).
- `volatile`: cambia continuamente durante la vita dell'entità
  osservata (es. token count crescente lato provider, non emesso oggi
  ma esempio didattico).
- `decaying`: mantiene rilevanza per una finestra limitata poi si
  deteriora (es. freshness del contesto RAG, non ancora modellato).

### 5.7 · Reproducibility — riproducibilità
Se rilanciamo lo stesso scenario, otteniamo lo stesso valore? Dominio:
- `re-collectable-identical`: sì, bit-identico (es. `reason` dal
  ROUTING_RULES, `hub_nodes` dalla topologia).
- `re-collectable-analogous`: sì ma con varianza attesa (es.
  `timestamp_start`: analogo istante, valore diverso; `duration_ms`:
  analogo range).
- `one-shot`: no, è unica opportunità di prendere *questo* dato
  specifico. È il caso di tutti i dati che dipendono dal comportamento
  LLM: `metadata.choice` del classifier, `text` del final_output,
  `thought` del reasoning_step. Rilanciando ottengo *un altro* valore
  della stessa distribuzione, ma il valore di *questa* run è perduto
  se non lo raccolgo ora.

Questa dimensione è **al cuore** della certificazione agentic:
distingue proprietà verificabili classicamente (re-collectable) da
proprietà che richiedono cattura on-the-fly (one-shot).

### 5.8 · Cadence — cadenza di raccolta possibile
Come si potrebbe raccogliere il dato (non come lo facciamo oggi).
Dominio:
- `event-triggered`: emesso solo quando l'evento sorgente accade (la
  quasi-totalità dei nostri dati).
- `polling-able`: potenzialmente interrogabile a intervalli (es.
  token remaining dell'API, memory usage del processo Python).
- `on-demand`: recuperabile in qualunque momento dallo stato
  osservabile (es. dimensione corrente della shared memory).
- `sliding-window`: aggregabile su finestra scorrevole di N eventi
  recenti (nessun dato del prototipo lo usa oggi — è il **buco
  principale** della raccolta attuale, da menzionare nel paper).

### 5.9 · Persistence — dove il dato è persistito
Dominio: `{jsonl.event.payload_summary,
jsonl.event.payload_redacted, jsonl.event.metadata,
jsonl.event.field, experiment.json, aggregate/metrics.json,
in-memory-only}`. `in-memory-only` marca i dati transienti che il
sistema NON persiste (es. token remaining nell'header HTTP, letto e
usato ma non salvato — buco osservabile).

### 5.10 · PII sensitivity — sensibilità PII
Dominio: `{none} ∪ V = {email, phone, reporter, ip, userid}`. Se
diverso da `none`, il dato attiva la policy `REDACTION_POLICY` sul
canale AgentLeak associato all'evento.

### 5.11 · Unit — unità di misura
Solo per `type ∈ {int, float, timestamp_ms}`. Dominio libero: `ms`,
`chars`, `bytes`, `tokens`, `count`, ecc. Rilevante per la
comparabilità cross-metrica (CV di § C4.8 e C4.9 sono confrontabili
proprio perché adimensionali dopo la normalizzazione, ma i valori
grezzi hanno unità diverse).

---

## 6 · Inventario dei dati grezzi per macro (matrice completa)

L'inventario è ricavato dal codice sorgente del prototipo
(`src/instrumentation/recorder.py`, `events.py`, `aggregator.py`,
`agents.py`) e verificato sul batch `exp_79cb00d472bf` (20 run
INC-2026-015, temp=0, gpt-oss-120b).

Ogni tabella lista i **dati grezzi elementari** che alimentano le
evidenze di una macro. Le sigle di attributi seguono § 5.

**Campi comuni a TUTTI gli eventi** (`recorder-builtin`, cardinalità
scala col numero di eventi):

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E0.1 | event_id | string(uuid16) | recorder-builtin | during-event | =events | stable-in-run | re-collectable-analogous | event-triggered | jsonl.event.field | none | – |
| E0.2 | run_id | string | recorder-builtin | during-event | =events | stable-in-run | re-collectable-analogous | event-triggered | jsonl.event.field | none | – |
| E0.3 | experiment_id | string | recorder-builtin | during-event | =events | stable-in-run | re-collectable-analogous | event-triggered | jsonl.event.field | none | – |
| E0.4 | event_type | categorical<EventKind> | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.5 | channel_id | categorical<C1..C7,null> | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.6 | macro_categories | list[categorical] | recorder-builtin | during-event | =events | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.7 | timestamp_start | int64 | recorder-builtin | during-event | =events | snapshot | re-collectable-analogous | event-triggered | jsonl.event.field | none | ms |
| E0.8 | timestamp_end | int64 | recorder-builtin | post-event | =events | snapshot | re-collectable-analogous | event-triggered | jsonl.event.field | none | ms |
| E0.9 | duration_ms | int | recorder-builtin | post-event | =events | derived-deterministic | re-collectable-analogous | event-triggered | jsonl.event.field | none | ms |
| E0.10 | agent_id | string | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.11 | source_component | string | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.12 | target_component | string\|null | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |
| E0.13 | tool_name | string\|null | recorder-builtin | during-event | =events | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.field | none | – |

Queste 13 celle non si ripetono nelle tabelle successive per non
saturare la matrice; si assume la loro presenza in ogni evento.

---

### 6.1 · Macro CONTROL FLOW — dati grezzi per evidenza

#### A1 · Decisioni dell'orchestratore (evento `orchestrator_decision`)

Alimenta A1.1..A1.5 (rule coverage, distribuzione + entropia, routing
determinism, branching factor, decisioni per run) e in parte A3
(sequenza edge orchestrator→target).

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1.d1 | metadata.reason | string | orchestrator | pre-event | =decisions | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A1.d2 | metadata.alternatives | list[string] | orchestrator | pre-event | =decisions | snapshot | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A1.d3 | metadata.step | int | orchestrator | during-event | =decisions | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.metadata | none | count |
| A1.d4 | metadata.context_snapshot_keys | list[string] | orchestrator | pre-event | =decisions | snapshot | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | – |

**Nota di raccolta**: il campo `alternatives` è calcolato *prima* della
scelta (le regole vere al momento t), quindi ha `moment=pre-event`.
`reason` viene dalla `ROUTING_RULES` matched → `derived-deterministic`.
`step` è contatore ordinato in-run.

#### A2 · Pianificazione (eventi `planning_span` e `replanning`)

Alimenta A2.1..A2.5. Il planning_span è emesso dopo la chiamata LLM
al planner.

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A2.d1 | metadata.plan | list[text_free] | agent:planner | post-event | 1 per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A2.d2 | metadata.n_steps | int | agent:planner | post-event | 1 per run | derived-deterministic | one-shot | event-triggered | jsonl.event.metadata | none | count |
| A2.d3 | metadata.updated | boolean | agent:planner | post-event | 1 per run | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A2.d4 | duration_ms | int | agent:planner | post-event | 1 per run | snapshot | re-collectable-analogous | event-triggered | jsonl.event.field | none | ms |
| A2.d5 | metadata.llm_provider | categorical<groq,cerebras> | agent:planner | post-event | 1 per run | stable-in-run | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | – |
| A2.d6 | metadata.llm_model | string | agent:planner | post-event | 1 per run | stable-in-run | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | – |
| A2.d7 | metadata.llm_fingerprint | string(sha256) | agent:planner | post-event | 1 per run | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A2.d8 | metadata.llm_latency_ms | int | agent:planner | post-event | 1 per run | snapshot | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | ms |
| A2.d9 | metadata.llm_prompt_tokens | int | agent:planner | post-event | 1 per run | snapshot | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | tokens |
| A2.d10 | metadata.llm_completion_tokens | int | agent:planner | post-event | 1 per run | snapshot | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | tokens |
| A2.r1 | metadata.old_plan (replanning) | list[text_free] | agent:planner | post-event | 0..k per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A2.r2 | metadata.new_plan (replanning) | list[text_free] | agent:planner | post-event | 0..k per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A2.r3 | metadata.reason (replanning) | text_free | agent:planner | post-event | 0..k per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |

**Nota critica**: `plan` è `one-shot` perché generato dal LLM ex-novo
ogni run. `n_steps` è `derived-deterministic` perché deriva da `plan`
via `len()`. La distinzione one-shot vs derived è centrale: A2.d1
richiede cattura on-the-fly, A2.d2 può essere ricalcolata ex-post.

#### A3 · Handoff (eventi `handoff` E derivati da `orchestrator_decision`)

Alimenta A3.1..A3.6.

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A3.d1 | metadata.reason | string | orchestrator/agent | during-event | =handoffs | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A3.d2 | metadata.context_summary | text_free | orchestrator/agent | during-event | =handoffs | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A3.d3 | metadata.payload_size | int | orchestrator/agent | during-event | =handoffs | snapshot | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | bytes |

**Blind spot dichiarato**: il runtime attuale NON emette eventi
`handoff` espliciti (l'orchestratore emette solo
`orchestrator_decision`). A3 è quindi ricostruito dai target di
quest'ultimo. In una topologia non hub-and-spoke servirebbe emettere
`handoff` espliciti — pattern raccomandato per il paper.

#### A4 · Metriche di percorso (aggregazione su tutti gli eventi + `run_end`)

Alimenta A4.1..A4.6. Non ha un evento sorgente proprio: deriva
dall'insieme degli eventi + `run_end`.

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A4.d1 | metadata.outcome (run_end) | categorical<completed,error,unknown> | recorder | end-of-run | 1 per run | stable-in-run | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A4.d2 | metadata.classification (run_end) | categorical<...> | recorder | end-of-run | 1 per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A4.d3 | metadata.priority (run_end) | categorical<P1..P4> | recorder | end-of-run | 1 per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A4.d4 | metadata.affected_service (run_end) | categorical<...> | recorder | end-of-run | 1 per run | one-shot | one-shot | event-triggered | jsonl.event.metadata | none | – |
| A4.d5 | metadata.total_tokens (run_end) | int | recorder | end-of-run | 1 per run | derived-deterministic | re-collectable-analogous | event-triggered | jsonl.event.metadata | none | tokens |
| A4.d6 | metadata.agent_history (run_end) | list[string] | recorder | end-of-run | 1 per run | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| A4.d7 | run_duration | int (derivato) | aggregator | end-of-batch | 1 per run | derived-deterministic | re-collectable-analogous | on-demand | aggregate/metrics.json | none | ms |
| A4.d8 | tool_call_count | int (derivato) | aggregator | end-of-batch | 1 per run | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | count |
| A4.d9 | error_count | int (derivato) | aggregator | end-of-batch | 1 per run | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | count |

**Nota epistemologica**: `outcome` è stable-in-run ma one-shot (se
questa run è "completed", rilanciando potrebbe essere "error"). La
combinazione stable+one-shot esiste ed è tipica dei dati LLM-driven.

---

### 6.2 · Macro DATA FLOW — dati grezzi per evidenza

Il data flow non ha un evento proprio: **ogni evento con `channel_id`
valorizzato contribuisce**. La tassonomia è quindi verticalizzata
sui campi che veicolano potenzialmente PII.

#### B1..B3 · Emissione, CLR, SLR (basati su `payload_summary` e `payload_redacted`)

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B.d1 | payload_summary | text_free | any event with channel | during-event | =events | one-shot | analogous se LLM, identical altrimenti | event-triggered | jsonl.event.field | scan V | chars |
| B.d2 | payload_redacted (ricorsivo) | dict\|list\|text_free | any event with channel | during-event | =events | one-shot | analogous se LLM, identical altrimenti | event-triggered | jsonl.event.field | scan V | – |
| B.d3 | metadata.pii_redaction_hits | dict[category→int] | event_store (adapter) | during-event | events with hits | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | audit-only | count |
| B.d4 | metadata.namespace (shared_memory) | string | agent | during-event | =memory ops | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| B.d5 | metadata.key (shared_memory) | string | agent | during-event | =memory ops | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| B.d6 | metadata.success (tool_result) | boolean | tool_adapter | post-event | =tool_results | stable-in-run | analogous | event-triggered | jsonl.event.metadata | none | – |
| B.d7 | metadata.subject (inter_agent_msg) | string | agent | during-event | =messages | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |

#### B4 · Policy dichiarata (statica, non evento-driven)

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B4.d1 | VAULT_PATTERNS (V) | dict[string→regex] | source code | end-of-batch | 1 per batch | stable-in-run | re-collectable-identical | on-demand | aggregate/metrics.json | schema | – |
| B4.d2 | ALLOWED_SET_A[channel] | dict[C1..C7→set[string]] | source code | end-of-batch | 1 per batch | stable-in-run | re-collectable-identical | on-demand | aggregate/metrics.json | schema | – |
| B4.d3 | REDACTION_POLICY (derivata V-A) | dict[C1..C7→set[string]] | source code | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | schema | – |
| B4.d4 | mitigation.per_channel.redactions_by_category | dict[category→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | count |
| B4.d5 | mitigation.events_with_redaction | int | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | count |

**Osservazione tassonomica**: B4 sono dati `stable-in-run` /
`derived-deterministic` con `hook=source_code` — dichiarati ex-ante,
la loro re-collection è banale. Sono la parte "specifica di
certificazione" del data flow.

---

### 6.3 · Macro BEHAVIORAL — dati grezzi per evidenza

#### C1 · Trace end-to-end (aggregato su tutti gli eventi della run)

Non ha dati grezzi propri: usa **l'intera timeline** già catturata
dagli altri eventi. È l'unica evidenza puramente "aggregativa".

#### C2 · Coerenza state ↔ output (eventi `state_snapshot` e `final_output`)

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2.d1 | metadata.state (state_snapshot) | dict | agent:summarizer | end-of-run | 1 per run | stable-in-run | one-shot | event-triggered | jsonl.event.metadata | may contain V | – |
| C2.d2 | metadata.label (state_snapshot) | string | agent:summarizer | end-of-run | 1 per run | stable-in-run | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| C2.d3 | payload_summary (final_output) | text_free | agent:summarizer | end-of-run | 1 per run | one-shot | one-shot | event-triggered | jsonl.event.field | may contain V | chars |

**Nota**: C2 è calcolata come coverage lessicale dei campi chiave di
`state.classification/priority/affected_service` (C2.d1) nel testo di
`final_output` (C2.d3). Sono entrambi one-shot, richiedono cattura
al momento della run.

#### C3 · Sequenza decisioni (evento `decision_point` + `tool_result`)

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C3.d1 | metadata.label | categorical<affected_service, log_depth, critical_component, classification, ...> | agent | during-event | ≈5 per run | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.metadata | none | – |
| C3.d2 | metadata.choice | string | agent | during-event | ≈5 per run | one-shot (se LLM) / deterministic (se rule) | dipende | event-triggered | jsonl.event.metadata | none | – |
| C3.d3 | payload_redacted.inputs | dict | agent | during-event | ≈5 per run | one-shot | one-shot | event-triggered | jsonl.event.payload_redacted | may contain V | – |
| C3.d4 | payload_redacted.result[i].id (tool_result postmortems) | string | tool_adapter:query_postmortems | post-event | k pm per run | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.payload_redacted | none | – |
| C3.d5 | payload_redacted.result[i].tags (tool_result postmortems) | list[string] | tool_adapter:query_postmortems | post-event | k pm per run | derived-deterministic | re-collectable-identical | event-triggered | jsonl.event.payload_redacted | none | – |

**Nota**: C3.d2 ha lifecycle misto: se il decision_point è emesso dal
planner o classifier (LLM), è `one-shot`; se emesso da
log_investigator/metrics_analyst (deterministici), è
`derived-deterministic`. Questa **eterogeneità intra-attributo** è
un caso da discutere nel paper: la stessa "colonna" della tabella
può avere celle con lifecycle diverso a seconda del produttore.

#### C4 · Stabilità cross-run (aggregazione end-of-batch)

Tutti i dati di C4 sono `derived-deterministic` dall'aggregato dei
dati already-collected. Il loro `hook` è `aggregator`, `moment` è
`end-of-batch`, `cadence` è `on-demand` sul batch chiuso.

| # | Name | Type | Hook | Moment | Cardinality | Lifecycle | Reproducibility | Cadence | Persistence | PII | Unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C4.d1 | node_signatures (Counter) | dict[tuple[string]→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d2 | edge_signatures (Counter) | dict[tuple[tuple]→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d3 | tool_signatures (Counter) | dict[tuple[string]→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d4 | final_classification (Counter) | dict[string→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d5 | final_priority (Counter) | dict[string→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d6 | final_affected_service (Counter) | dict[string→int] | aggregator | end-of-batch | 1 per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |
| C4.d7 | step_counts (list) | list[int] | aggregator | end-of-batch | N per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | count |
| C4.d8 | output_lengths (list) | list[int] | aggregator | end-of-batch | N per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | chars |
| C4.d9 | durations_ms (list) | list[float] | aggregator | end-of-batch | N per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | ms |
| C4.d10 | postmortem_sets (list) | list[set[string]] | aggregator | end-of-batch | N per batch | derived-deterministic | re-collectable-identical | on-demand | aggregate/metrics.json | none | – |

**Osservazione**: C4 è interamente `re-collectable-identical` da JSONL
già chiuso. Questo lo rende **ri-eseguibile** su qualunque batch
storico, proprietà preziosa: se aggiungiamo nuovi assi C4 in futuro,
possiamo rigenerarli su esperimenti passati senza rilanciare le run.

---

### 6.4 · Sintesi quantitativa della matrice

- **Campi comuni recorder-builtin**: 13
- **Control Flow**: 4 (A1) + 13 (A2) + 3 (A3) + 9 (A4) = **29**
- **Data Flow**: 7 (B1-B3) + 5 (B4) = **12**
- **Behavioral**: 3 (C2) + 5 (C3) + 10 (C4) = **18**
- **Totale dati grezzi tassonomizzati**: **72 righe × 11 attributi = 792 celle**

Distribuzione per `lifecycle`:
- `stable-in-run`: dominante nei campi identificativi e nelle policy.
- `derived-deterministic`: dominante nell'aggregato C4 e in tutte le
  metriche di batch.
- `snapshot`: campi temporali (timestamp, duration).
- `one-shot`: quasi tutti i campi LLM-driven (plan, choice del
  classifier, final_output text, thought del reasoning).
- `decaying`: **ZERO occorrenze** — è il buco più significativo del
  prototipo attuale.
- `volatile`: **ZERO occorrenze** nei dati persistiti (esiste in
  memoria: token remaining lato provider, ma non lo salviamo).

Distribuzione per `cadence`:
- `event-triggered`: ~90% dei dati.
- `on-demand`: aggregati e policy dichiarate.
- `polling-able`: **ZERO occorrenze** — anch'esso un buco.
- `sliding-window`: **ZERO occorrenze** — il buco più discusso del paper.

Distribuzione per `reproducibility`:
- `re-collectable-identical`: policy, campi derivati deterministicamente,
  campi da ROUTING_RULES.
- `re-collectable-analogous`: timestamp, latency, token count.
- `one-shot`: **tutti i dati che dipendono dall'output LLM**. Il
  conteggio esatto è **una metrica di primo piano del paper**: ~15
  campi su 72 sono one-shot. Ogni certificazione agentic deve fare i
  conti con questa frazione.

---

## 7 · Ciclo di vita del dato: cutting-edge concepts

La letteratura di agent observability tratta oggi le evidenze come
**punti** (una metrica ha un valore), non come **oggetti temporali**
che si comportano diversamente nel tempo. La tassonomia proposta
(§ 5.6 lifecycle, § 5.7 reproducibility, § 5.8 cadence) rende questa
temporalità esplicita. Da qui derivano tre concetti originali che il
paper introduce come contributo teorico.

### 7.1 · Observability boundary

Definiamo l'**observability boundary** come l'insieme delle proprietà
del sistema che il framework di raccolta NON riesce a osservare, per
scelta o per limite architetturale. I blind spot del prototipo (§ 8)
sono la sua manifestazione empirica.

Formalmente, dato un sistema agentico S e un framework di raccolta F,
l'observability boundary `∂(S, F)` è il complementare, nell'insieme
delle proprietà osservabili in linea di principio su S, di quelle
effettivamente catturate da F. Un paper di certificazione onesto
deve **dichiararlo esplicitamente**, non nasconderlo.

### 7.2 · Deterioration curve dei dati one-shot

Un dato `one-shot` (§ 5.7) ha valore massimo al momento t₀ di cattura
e valore residuo decrescente dopo t₀:

- t₀ (istante): valore = "esatto per questa esecuzione"
- t₀ + Δ (con modello LLM immutato, codice invariato): valore =
  "rappresentativo della distribuzione di risposte", ma non "quel
  valore specifico"
- t₀ + Δ (con drift lato provider — cambio modello, batch composition
  molto diversa): valore = "irrilevante per certificare lo stato
  attuale"

Il paper può proporre una **taxonomy of decay** — categorie di
deterioramento — e distinguerla dai dati `re-collectable-identical`
che non decadono per definizione. Nel nostro prototipo la cache LLM
rimossa (§ 6.1 RESEARCH_DECISIONS.md) era un tentativo mal posto di
mitigare il decay che ha finito per sopprimere il segnale scientifico
sottostante.

### 7.3 · Re-certifiability window

La **re-certifiability window** è l'intervallo temporale entro il
quale una certificazione basata sui dati raccolti in t₀ resta valida.
Dipende da:

- la frazione di dati `one-shot` nella tassonomia (più è alta,
  finestra più stretta);
- la frazione di dati `decaying` (più è alta, finestra ha un half-life
  definibile);
- la stabilità del substrato (modello LLM, codice degli agenti,
  policy dichiarate).

Nel prototipo attuale, con ~20% di dati one-shot e 0% di dati decaying
esplicitamente modellati, la re-certifiability window è dominata dalla
stabilità del provider LLM: se Groq/Cerebras aggiornano il modello,
la certificazione precedente non è più garantita. Il paper può
proporre di **tracciare esplicitamente** questa dipendenza (già
parzialmente fatto via `llm_fingerprint` e `native_model` nei
metadata degli eventi).

### 7.4 · Domande di ricerca aperte

Nessuna di queste ha risposta pulita in letteratura:

- **Composizione temporale**: come si combinano evidenze raccolte in
  finestre temporali diverse per produrre un verdetto attuale? Se la
  policy dichiarata (B4) è di 6 mesi fa ma le misure C4 sono di ieri,
  cosa certifichiamo?
- **Trigger di ri-raccolta**: quando va rieseguita la raccolta?
  Per-commit del codice degli agenti? Per-deploy in produzione?
  Per-cambio-modello del provider? On-demand?
- **Composizione multi-hook**: dati emessi da hook diversi (agent
  vs tool_adapter vs event_store) possono avere lifecycle diversi
  per la *stessa* semantica — come si trattano nell'aggregato?

---

## 8 · Processo di collezione e blind spots (observability boundary)

Il § 8 del paper discuterà **come** ogni evidenza viene raccolta, con
particolare attenzione ai **blind spot**: la manifestazione empirica
dell'observability boundary (§ 7.1) sul prototipo attuale.

### 8.1 · Blind spot noti (mappati sulla matrice § 6)

- **Prompt fingerprint post-templating**: osserviamo il fingerprint
  del prompt inviato al provider (`llm_fingerprint`, § 6.1
  A2.d7), non il prompt effettivamente processato dal modello dopo il
  template interno del provider. Lifecycle atteso: `snapshot`,
  cadence: `event-triggered`; nel prototipo assente.
- **Batch composition lato provider**: sappiamo che varia (§ 6.1
  RESEARCH_DECISIONS.md), non possiamo osservarla direttamente. È
  la causa nota della varianza residua a temp=0. Nessun campo la
  cattura.
- **Aggiornamenti silenziosi del modello**: rilevabili solo
  indirettamente via divergenza dei fingerprint su cache-hit
  verificati (funzionalità rimossa insieme alla cache; da ripensare).
- **Token remaining / usage lato provider (volatile)**: leggibile
  dagli header HTTP di Groq/Cerebras, usato dal client per
  l'adaptive sleep, ma **non persistito** negli eventi. Lifecycle
  `volatile`, cadence `polling-able` — perfetto candidato per una
  sonda nuova.
- **Quasi-identifier PII**: la detection su V è per-categoria, non
  cattura combinazioni di attributi non-sensibili che identificano
  un individuo (es. nome + servizio + orario). Buco di sicurezza
  dichiarato.
- **Emergenza cross-run**: comportamenti emergenti visibili solo a N
  grande non catturati con N piccolo (limite del regime statistico).
  Non è un blind spot del *cosa* raccogliamo ma del *quanto*.
- **Decaying data (freshness contesto RAG)**: nessun dato del
  prototipo ha lifecycle `decaying` esplicito. In un sistema
  RAG-based sarebbe centrale (freshness dei documenti indicizzati).
- **Sliding-window aggregates**: nessuna metrica del prototipo ha
  cadence `sliding-window`. È il buco più discusso in § 7.

### 8.2 · Blind spot dichiarati come future work

Un paper onesto **elenca esplicitamente** i blind spot come limiti
dichiarati. Il paper 2 (composizione vs singolo agente) toccherà in
particolare:
- comportamenti emergenti a livello di composizione multi-agente non
  osservabili nei singoli agenti;
- osservabilità delle policy dinamiche (che cambiano durante
  l'esecuzione).

---

## 9 · Rapporto col prototipo

Il prototipo (`src/`, `data/demo/`, `webapp/`) **implementa la
tassonomia**. Ogni evidenza ha già i propri attributi codificati (root
è già presente nel metadata di molte metriche); l'implementazione
completa dei 7 attributi come metadata standardizzato è la roadmap
imminente (§ 10 di questo doc).

La dashboard rinnovata (roadmap § 10) esporrà per ogni evidenza gli
attributi in forma leggibile, così che gli screenshot della dashboard
diventino direttamente le figure del paper.

---

## 10 · Roadmap di scrittura (parallela al prototipo)

Milestone di scrittura, allineate al lavoro sul prototipo:

1. **Fix di consistenza sulle 3 metriche deboli** — ✅ chiuso
   (A3.4 anti_pattern_bounces / structural_bounces; A4.5 cyclomatic sul
   grafo DICHIARATO; C4 risoluzione multi-asse con 10 sotto-metriche).
   Vedi §§ 11.4-11.6 di RESEARCH_DECISIONS.md.
2. **Implementazione dei 7 attributi come metadata standardizzato**
   su tutte le metriche del prototipo — prossimo step.
3. **Redesign della dashboard** con attributi tassonomici visibili.
4. **Compilazione completa della matrice** (§ 6, 252 celle).
5. **Bozza § 1-4 del paper** (Introduction, Background, Framing,
   Categories).
6. **Bozza § 5-6** (Attributi, Matrice).
7. **Bozza § 7-8** (Lifecycle, Collection Process) — sezioni originali.
8. **Bozza § 9-12** (Validation, Discussion, Related, Conclusion).
9. **Iterazione con i supervisori** (Bena, Anisetti, Ardagna).
10. **Sottomissione**.

---

## 11 · Riferimenti bibliografici (nucleo iniziale)

- Stiller B. — riferimento prioritario indicato in call (tassonomie
  di verifica; da recuperare pubblicazioni recenti).
- van der Aalst W. — *Process Mining: Data Science in Action*, Springer.
- Polyvyanyy A. et al. — *Entropia: A Family of Entropy-Based
  Conformance Checking Measures for Process Mining*, arXiv:2008.09558.
- McCabe T. J. (1976) — *A Complexity Measure*, IEEE TSE.
- Brown L. D., Cai T. T., DasGupta A. (2001) — *Interval Estimation
  for a Binomial Proportion*, Statistical Science.
- Legay A., Delahaye B., Bensalem S. (2010) — *Statistical Model
  Checking: An Overview*, RV'10.
- AgentLeak — canali C1..C7 (paper da citare puntualmente).
- Confident AI — *LLM Agent Evaluation*.
- RAGAS — groundedness/context adherence.
- Bena, Anisetti, Damiani, Della Bruna, Yeun, Ardagna — *A
  Certification Scheme for Large Language Models-Based Applications*,
  TIST 2026 (framework di riferimento).

---

## Appendice · Regola di manutenzione

Ogni nuova scelta di ricerca che tocchi la **tassonomia** (aggiunta/
modifica di attributi, nuova macro, nuova evidenza) va riflessa qui.
Le scelte di *implementazione* restano in `RESEARCH_DECISIONS.md`.
Le scelte di *tassonomia* stanno in questo doc.

In dubbio: se cambia la matrice del § 6, cambia il paper → va qui.
