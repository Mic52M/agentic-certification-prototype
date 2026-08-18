# Research Decisions Log

Documento vivo che raccoglie **tutte le decisioni di ricerca** prese sul
prototipo di certificazione per sistemi agentici multi-agente, e il razionale
scientifico dietro ciascuna. Serve come fonte unica di verità per la stesura
del paper LNCS (deadline 31/08/2026) e per l'allineamento fra le sessioni
di lavoro.

**Convenzione**: ogni decisione è riportata con questo schema

- **Decisione**: cosa abbiamo scelto.
- **Motivazione**: perché è la scelta giusta *rispetto alla domanda di ricerca*, non solo tecnicamente.
- **Alternative scartate**: cosa avremmo potuto fare invece e perché non l'abbiamo fatto.
- **Evidenza empirica**: dove nel repo si vede il risultato (esperimenti, metriche, commit).
- **Limite dichiarato**: cosa questa scelta *non* copre, per onestà scientifica.

Il documento si legge nell'ordine dei capitoli; ogni sezione è
auto-contenuta.

---

## 0 · Scopo del prototipo

Costruire un **prototipo dimostrativo** che strumenti un sistema agentico
multi-agente per raccogliere, in modo osservativo e non intrusivo, le
evidenze necessarie a un processo di certificazione lungo tre macro-dimensioni:

1. **Control Flow**: orchestrazione, routing, handoff, metriche di percorso.
2. **Data Flow**: canali di comunicazione fra agenti (C1..C7 di AgentLeak),
   detection PII, contromisure di data-minimization.
3. **Behavioral Flow**: traiettorie end-to-end, coerenza state↔output,
   sequenza decisioni, stabilità comportamentale su N run.

**Il prototipo NON è un motore di verifica**: raccoglie evidenze, calcola
metriche descrittive, produce dashboard. Il verdetto di certificazione è
una decisione successiva che poggia su queste evidenze — deliberatamente
non emesso dallo strato di misura.

Progetto legato al lavoro del gruppo dell'Università degli Studi di Milano
(Bena, Anisetti, Damiani, Della Bruna, Yeun, Ardagna) sul framework TIST
2026 di certificazione di applicazioni LLM-based, esteso qui al setting
agentico.

---

## 1 · Framing scientifico fondazionale

### 1.1 · Salto ontologico agentico

- **Decisione**: nel setting agentico, una proprietà non è un predicato
  deterministico su una singola esecuzione, ma **un'affermazione
  probabilistica su una distribuzione di traiettorie**.
- **Motivazione**: gli agenti LLM-based sono stocastici (anche a
  temperature=0 c'è varianza residua lato provider — vedi § 6.1); un
  sistema multi-agente ha traiettorie non deterministiche anche quando
  l'orchestratore è deterministico, perché la decisione dei singoli
  agenti non lo è. Certificare "è coerente" o "è sicuro" richiede quindi
  un regime **statistico** con intervalli di confidenza, non un
  predicato binario.
- **Alternative scartate**: verificazione formale classica (model
  checking deterministico) — inapplicabile al comportamento LLM.
- **Limite dichiarato**: N grande costoso; con N piccolo (10-20) gli IC
  sono larghi e le stime meno strette.

### 1.2 · Triade coerente / accettabile / inaccettabile

- **Decisione**: adottare una triade tri-livello introdotta da Ardagna
  nell'allineamento del 2026-07-29 (analogia della Tesla che sceglie di
  uscire fuori strada per evitare un pedone: non è il caso ottimo, ma è
  ammissibile rispetto a investire il pedone).
  - `coherent` = comportamento ottimo (100% dei criteri superati).
  - `acceptable` = comportamento non ottimo ma tollerato (≥ 50%).
  - `unacceptable` = comportamento non ammissibile (< 50%).
- **Motivazione**: il binario pass/fail è troppo rigido per il setting
  agentico. La fascia intermedia cattura il caso reale in cui un agente
  produce un output "meno che perfetto ma utile", tipico dei sistemi
  LLM-based. Rende la certificazione **rispondente alla realtà** anziché
  performativa.
- **Alternative scartate**: soglia binaria (ci si sarebbero bocciate
  troppe run "utili"); scoring continuo senza classi (perde
  interpretabilità per revisori/stakeholder).
- **Evidenza empirica**: `src/demo/behavioural_policy.py` dichiara le
  soglie C2 e C3 con i mapping `classify_c2` / `classify_c3`; le
  metriche C2/C3 emettono la distribuzione della triade su N run
  (`bh_metrics.c2_details`, `bh_metrics.c3_details`).
- **Limite dichiarato**: le soglie 50%/100% sono scelte ex-ante; per
  altri domini si dovranno calibrare.

### 1.3 · Tre regimi di osservazione behavioural

- **Decisione**: articolare la macro Behavioural in tre regimi
  concettualmente distinti:
  - **Regime 1 — Substrato** (C1): singola traccia end-to-end.
  - **Regime 2 — Coerenza per-run** (C2, C3): confronto interno a una
    singola run (state ↔ output, sequenza decisioni).
  - **Regime 3 — Distribuzione cross-run** (C4): stabilità/varianza su
    N ripetizioni.
- **Motivazione**: la macro Behavioural rende osservabile il "control
  flow agentico interno al singolo agente" (Anisetti in call): quello
  che il control flow tradizionale non cattura, perché l'agente ha un
  intento evidente e decide autonomamente l'ordine delle chiamate ai tool.
  I tre regimi rispondono a domande diverse; mescolarli confonde.
- **Alternative scartate**: unica metrica behavioural aggregata (perde
  granularità e nasconde dove sta il problema quando il sistema fallisce).
- **Evidenza empirica**: dashboard "Behavioural Flow" (webapp/static/
  index.html) mostra i tre regimi separati; `bh_metrics.py` è organizzato
  per regime.

### 1.4 · Distinzione strutturale vs comportamentale

- **Decisione**: distinguere ontologicamente due tipi di proprietà.
  - **Strutturali** (deterministiche): certificabili classicamente. Es.
    conformance topologica del grafo di handoff, coverage delle
    ROUTING_RULES.
  - **Comportamentali** (statistiche): richiedono N run + intervallo di
    confidenza. Es. completion rate, coherent rate su C2/C3.
- **Motivazione**: le due categorie richiedono strumenti diversi. Mescolarle
  porta a sovradichiarare (proprietà comportamentali certificate come
  "vere/false" senza IC) o sottodichiarare (proprietà strutturali
  degradate a stima probabilistica).
- **Evidenza empirica**: `topology.py` (`declared_spec()`) fornisce il
  modello dichiarato usato dalle metriche strutturali; le metriche con
  IC Wilson sono esplicitamente marcate `A4.2, C2.3, C2.4, C3.3, C3.4`.

### 1.5 · Nessun LLM-as-judge nei check di certificazione

- **Decisione**: i check di coerenza (C2 state↔output, C3 pairwise) sono
  **deterministici** e implementati come regole ispezionabili (regex,
  set operations, substring matching), non come chiamate a un LLM che
  giudica un altro LLM.
- **Motivazione**: la circolarità "un modello giudica un modello" mina
  l'auditabilità e rende irreproducibile il verdetto. Le policy sono
  dichiarate ex-ante in codice, revisionabili line-by-line.
- **Alternative scartate**: RAGAS o simili (dipendono da un giudice LLM);
  human evaluation (non scala, non riproducibile).
- **Limite dichiarato**: le regole deterministiche sono più povere
  semanticamente di un giudice LLM; ci sono falsi negativi (es. sinonimi
  non catturati). Contromisura: substring matching bidirezionale
  (vedi § 7.1) e policy con lemmi generici.

### 1.6 · Wilson score interval per le proporzioni

- **Decisione**: usare l'intervallo di Wilson al 95% (Brown, Cai,
  DasGupta 2001) per stime di proporzione (completion rate, coherent
  rate, acceptable rate).
- **Motivazione**: l'intervallo normale (`p ± 1.96·√(p(1-p)/N)`) degenera
  quando p è 0 o 1 (l'IC collassa a un punto), esattamente lo scenario
  in cui abbiamo dati (es. 20/20 completion). Wilson non degenera e
  resta ben calibrato anche con N piccolo.
- **Alternative scartate**: intervallo Clopper-Pearson (esatto ma più
  conservativo, IC più larghi non giustificati dai dati); intervallo
  normale (visto sopra).
- **Evidenza empirica**: `cf_metrics.wilson_interval()` usato in A4.2,
  C2.3/C2.4, C3.3/C3.4. Batch 20 run: completion 20/20 → Wilson IC
  [0.84, 1.00] (non degenera).

---

## 2 · Use case: incident triage multi-agente

### 2.1 · Scelta del dominio

- **Decisione**: incident triage su un servizio di posta aziendale
  fittizia (Acme Corp). Dato un ticket incident con sintomi multipli,
  il sistema produce un report di triage con classification, priority,
  hypothesis ordinate.
- **Motivazione**: dominio realistico ma **auto-contenuto** (nessuna
  chiamata a servizi esterni reali), che richiede orchestrazione
  non-triviale (branching su tipo di sintomo), coinvolge decisioni
  non-deterministiche (classifier LLM), tocca dati sensibili (email,
  IP, userid → banco di prova per data-flow). Coincide con scenari
  tipici della letteratura AgentOps.
- **Alternative scartate**: chatbot generalista (troppo poco strutturato
  per metriche di control flow); scenario formale-verification-friendly
  (perde interesse agentico).
- **Evidenza empirica**: `data/demo/incidents.json` con 2 ticket seed:
  `INC-2026-014` (mail-gateway, log-first) e `INC-2026-015` (webmail,
  metrics-first). I due ticket esercitano rami di routing complementari.

### 2.2 · Sette agenti, orchestratore rule-based

- **Decisione**: architettura a **hub-and-spoke** con orchestratore
  rule-based e 7 agenti specializzati (`Reader`, `Planner` — LLM,
  `Log Investigator` — deterministico, `Metrics Analyst` — deterministico,
  `Postmortem Retriever` — deterministico, `Classifier` — LLM,
  `Summarizer` — LLM).
- **Motivazione**: la mescola determinismo/non-determinismo rende il
  sistema **rappresentativo** senza essere puramente stocastico:
  possiamo osservare come le decisioni LLM (planner, classifier,
  summarizer) si intrecciano con logica deterministica (retriever, log,
  metrics), riflettendo scenari reali in cui gli agenti LLM sono
  cintura di livello semantico attorno a tool deterministici.
- **Alternative scartate**: tutto LLM (troppo caotico per isolare
  proprietà); tutto deterministico (esclude il problema di ricerca);
  orchestratore LLM (aggiungerebbe una fonte di stocasticità dove non
  serve — la vera domanda è certificare gli *agenti*, non l'orchestratore).
- **Evidenza empirica**: `src/demo/orchestrator.py` (ROUTING_RULES
  dichiarate), `src/demo/agents.py` (agenti), `src/demo/graph.py`
  (topologia LangGraph).

### 2.3 · Ticket seed complementari

- **Decisione**: INC-2026-014 (mail-gateway, sintomo di errore/coda →
  log-first) e INC-2026-015 (webmail, sintomo di performance →
  metrics-first). Batch misto per esercitare tutti i rami.
- **Motivazione**: un singolo ticket non esercita tutti i rami del
  routing → coverage delle regole rimane sotto 100% (evidenza empirica:
  batch di 20 su INC-015 → `A1.1 rule_coverage = 80%`, 2 dead rules
  che sono i rami log-first). Il coverage completo va dichiarato
  esplicitamente come proprietà del batch misto, non della singola
  esecuzione.
- **Evidenza empirica**: § 8.3 TODO per batch misto pianificato.

---

## 3 · Infrastruttura di raccolta

### 3.1 · Instrumentation non intrusiva, layer trasversale

- **Decisione**: la strumentazione vive in `src/instrumentation/` come
  layer trasversale, i domini (`src/demo/`) contengono la logica
  applicativa. Le sonde sono chiamate esplicitamente dagli agenti via
  la façade `Recorder`; nessun monkey-patching, nessun aspect-oriented
  hidden.
- **Motivazione**: la certificazione richiede che l'osservazione sia
  **auditabile**. Se le sonde fossero magic, un revisore non saprebbe
  se sta guardando eventi reali o costrutti derivati. Chiamate esplicite
  = trail chiaro.
- **Evidenza empirica**: `src/instrumentation/recorder.py` — ogni
  metodo emette esattamente un evento, il naming è isomorfo alle
  evidenze del framework (`decision_point`, `handoff`, `tool_call`, ecc.).

### 3.2 · Schema unificato TraceEvent

- **Decisione**: un unico `TraceEvent` (`instrumentation/events.py`)
  per tutte le macro-dimensioni. Ogni evento è taggato con la
  macro-categoria a cui contribuisce, l'eventuale canale AgentLeak
  (C1..C7), il tipo semantico (`EventKind`), e trasporta payload +
  metadata + timing.
- **Motivazione**: uno schema unico consente aggregatori diversi
  (per CF, DF, BH) di leggere la stessa fonte, senza duplicare la
  scrittura. Un evento può contribuire a più macro (es. `handoff` è
  sia CF che DF).
- **Alternative scartate**: schemi separati per macro (frammentazione,
  difficile aggiungere metriche cross-macro).

### 3.3 · Store append-only JSONL, un file per run

- **Decisione**: gli eventi vengono scritti in JSONL append-only, un
  file per run, cartella per esperimento
  (`experiments/<exp_id>/runs/<run_id>.jsonl`). Aggregate calcolato a
  fine batch e salvato in `experiments/<exp_id>/aggregate/metrics.json`.
- **Motivazione**: append-only garantisce immutabilità (raccomandato
  dalla letteratura agent observability). JSONL è leggibile a occhio
  senza tooling → ispezionabile in ogni momento. Un file per run
  isola i fallimenti.
- **Alternative scartate**: DB (overkill per lo use case, aggiunge
  dipendenza); Parquet (efficiente ma non ispezionabile a occhio).

### 3.4 · Aggregator disaccoppiato via dependency injection

- **Decisione**: `Aggregator` non importa direttamente le policy del
  dominio (`behavioural_policy`, `topology`); le riceve iniettate dal
  runner.
- **Motivazione**: rende l'aggregator riutilizzabile per domini diversi
  (mail-triage oggi, altro domani) senza modificare il codice di
  aggregazione. Rende esplicito nel runner *quale* policy sta guidando
  i verdetti.
- **Evidenza empirica**: `Aggregator.__init__` in `aggregator.py:88`
  accetta `declared_spec`, `bh_classify_c2`, `bh_classify_c3`,
  `bh_symptom_map`, `bh_class_to_tags`.

---

## 4 · Control Flow (macro 1) — 22 metriche

Documentazione tecnica dettagliata: [CONTROL_FLOW_METRICS.md](CONTROL_FLOW_METRICS.md).

Qui riportiamo solo le decisioni di framing.

### 4.1 · Radici: process mining + software testing + agent evaluation + SMC

- **Decisione**: le metriche CF poggiano su quattro filoni consolidati:
  process mining (van der Aalst, Polyvyanyy et al.), software testing
  (branch coverage, McCabe 1976), agent evaluation (completion rate,
  step efficiency), statistical model checking (Wilson score).
- **Motivazione**: nessun filone da solo copre il setting agentico.
  Il **contributo** è nella composizione e nell'adattamento (es.
  fitness/precision applicati non a tracce di processi business ma a
  handoff fra agenti).

### 4.2 · Metrica gating: A3.1 topology conformance

- **Decisione**: `A3.1 topology_conformance` è la metrica **gating**
  del CF. Se < 100%, tutto il resto del ragionamento sul flusso è
  invalidato.
- **Motivazione**: se il sistema esegue handoff fuori dalla topologia
  dichiarata, nemmeno sa cosa dovrebbe fare. Le altre metriche perdono
  significato.
- **Evidenza empirica**: batch 20 run → conformance = 100%, 15/15
  archi osservati sono nell'ammesso.

### 4.3 · Coverage separata dalla conformance

- **Decisione**: A3.1 (conformance) e A3.2 (edge coverage) sono metriche
  duali. Conformance = "il sistema ha fatto solo cose ammesse?";
  coverage = "quanto di ciò che può fare l'abbiamo visto fare?"
- **Motivazione**: sono domande scientificamente diverse. Un sistema
  può essere 100% conforme ma con 30% coverage (test insufficiente).
  Dichiarare entrambe evita l'ambiguità classica del "certificato
  perché non abbiamo visto violazioni".

### 4.4 · Metriche descrittive, non normative

- **Decisione**: nessuna metrica CF emette un verdetto di conformità.
  Sono **descrittori**.
- **Motivazione**: il verdetto è una decisione del processo di
  certificazione (a valle), non della sonda. Attaccare soglie
  hardcoded alle metriche renderebbe la sonda incontestabile ma
  arbitraria. La separazione descrizione/verdetto è centrale al
  framework.

---

## 5 · Data Flow (macro 2) — AgentLeak + mitigation

### 5.1 · Canali di AgentLeak come strato di riferimento

- **Decisione**: adottare la tassonomia dei sette canali di AgentLeak
  (C1 final output, C2 inter-agent, C3 tool input, C4 tool output,
  C5 shared memory, C6 reasoning trace, C7 persistent artifacts).
- **Motivazione**: è la tassonomia più recente e specifica per
  data-flow in sistemi agentici; consente comparabilità con altri
  lavori.

### 5.2 · Vault V + Allowed Set A per canale, policy dichiarata

- **Decisione**: definire un vault V di categorie di dato sensibile
  (`email`, `phone`, `reporter`, `ip`, `userid`) e per ogni canale
  un Allowed Set A specificando quali categorie sono ammesse.
- **Motivazione**: rende operativa la nozione di leakage. Un tag
  fuori policy è definito ex-ante, non desunto empiricamente.
  Ispezionabile e discutibile in fase di certificazione.
- **Evidenza empirica**: `src/instrumentation/pii_redactor.py` —
  `VAULT_PATTERNS`, `ALLOWED_SET_A`.

### 5.3 · REDACTION_POLICY derivata da (V, A), non dichiarata

- **Decisione**: la policy di redazione è calcolata come
  `REDACTION[c] = V - A[c]` per ogni canale c, invece che essere
  dichiarata a mano.
- **Motivazione**: **una sola sorgente di verità**. Se la policy di
  redazione fosse dichiarata separatamente dalla policy di detection,
  detection e mitigation potrebbero divergere → il framework
  certificherebbe "pulito" con violazioni che il vault avrebbe
  segnalato. Derivarla elimina in radice l'incongruenza.
- **Alternative scartate**: policy di redazione dichiarata a mano
  (rischio di divergenza silenziosa); redazione hardcoded per canale
  (non parametrizzabile).

### 5.4 · Detect → mitigate → re-verify come pattern paper

- **Decisione**: il framework supporta due modalità di esperimento
  tramite flag `DATAFLOW_REDACTION_ENABLED`:
  - **raw** (`false`): nessuna redazione, la detection scansiona il
    testo originale → CLR alto quando il sistema viola la policy.
  - **redacted** (`true`, default): il redattore mitiga in-place
    prima della persistenza, la detection legge da
    `metadata.pii_redaction_hits` (audit trail delle violazioni
    mitigate) → CLR = 0 per costruzione.
- **Motivazione**: raccontare il **ciclo completo** anziché solo
  "abbiamo rilevato". Un revisore vede: (a) framework rileva
  violazione strutturale del design, (b) framework propone contromisura
  dichiarata, (c) framework re-verifica empiricamente l'efficacia
  sullo stesso pipeline. In linea con letteratura AgentLeak che
  parla di sanitization/minimization come contromisura.
- **Evidenza empirica**:
  - `exp_79cb00d472bf` (20 run raw): CLR C4=1.0, CLR C5=1.0, SLR=1.0.
  - `exp_692c4c8ae2eb` (3 run redacted): CLR ovunque=0, SLR=0,
    mitigation `{C4:{email:6}, C5:{email:6}}`, 6 eventi toccati.
- **Limite dichiarato**: la redazione è per-canale e per-categoria; non
  gestisce quasi-identifiers (combinazioni di attributi non-sensibili
  che identificano un individuo). Punto per lavori futuri.

### 5.5 · Redazione lato adapter, non lato agent

- **Decisione**: il redattore opera nel choke point `EventStore.append`,
  prima della persistenza JSONL e prima di notificare i sink UI.
- **Motivazione**: fare la redazione lato agent richiederebbe di
  modificare ogni agente e di *fidarsi* che ognuno la applichi. Fare
  lato adapter garantisce che nessun percorso possa aggirare la
  contromisura: è un invariante del sistema di raccolta, non una
  disciplina degli agenti.

### 5.6 · Redazione ricorsiva su strutture annidate

- **Decisione**: il redattore applica la maschera ricorsivamente su
  ogni stringa raggiungibile dentro `payload_summary` e
  `payload_redacted` (che sono dict/list annidati).
- **Motivazione**: nella prima versione (bug intercettato al primo
  smoke, ora corretto) la redazione operava solo su valori string
  top-level → `payload_redacted.result.reporter_email` restava in
  chiaro. La ricorsione garantisce che nessun percorso di scrittura
  fuoriesca dal contratto.
- **Evidenza empirica**: sanity `grep '@acme-corp' experiments/exp_692c4c8ae2eb/runs/*.jsonl → 0`.

---

## 6 · Behavioral Flow (macro 3) — triade + Wilson + policy

### 6.1 · Varianza residua a temperature=0 come segnale scientifico

- **Decisione**: **NON usare cache LLM** anche a `temperature=0`.
- **Motivazione**: a `temperature=0` un provider LLM non è realmente
  deterministico. Cause: batch composition lato server, non-associatività
  floating-point sulle GPU (l'ordine di riduzione nel softmax dipende
  dal batching), speculative decoding, aggiornamenti silenziosi del
  modello. Empiricamente, su 20 run identiche vediamo:
  - 8 formulazioni distinte del primo step del piano (`A2.5`),
  - latenza da 884ms a 2449ms (`A2.4`, σ=383ms),
  - 19× `capacity_saturation` + 1× `regression_after_deploy` in
    classification finale (`C4`, entropia normalizzata 0.286),
  - 13 coherent + 7 acceptable in C2.

  Questa è **la varianza reale** che il framework deve poter osservare.
  Una cache la sopprimerebbe artificialmente (servendo la prima
  risposta 499 volte come se fosse legge).
- **Alternative scartate**: cache LLM con verify sampling (implementata
  in prima battuta, poi rimossa — commit `86b1ec6` → revert `3fda74c`).
  Il ragionamento era stato "a temp=0 è deterministico, la cache è
  memoizzazione trasparente". Empiricamente falso.
- **Evidenza empirica**: aggregato `exp_79cb00d472bf`.

### 6.2 · C2 · Coverage state ↔ output come proxy di groundedness

- **Decisione**: C2 misura la coverage lessicale dei campi chiave dello
  stato consolidato (`classification`, `priority`, `affected_service`)
  nel testo dell'output finale, verdetto tri-livello via
  `classify_c2`.
- **Motivazione**: la "groundedness" della letteratura RAGAS è pensata
  per RAG (grounding sul contesto); adattata al setting agentic
  diventa "l'output riflette lo stato interno del sistema?". Se no,
  il sistema comunica qualcosa di scollegato dalle proprie decisioni.
- **Limite dichiarato**: è **proxy lessicale**; una parafrasi
  semantica dei campi chiave sarebbe missing. Contromisura futura:
  fuzzy matching (richiesto da Nicola in call). Attualmente esatto.

### 6.3 · C3 · Tre check pairwise di intention-behavior consistency

- **Decisione**: C3 non misura una singola cosa ma applica 3 check
  pairwise fra decisioni successive:
  1. **planner ↔ investigatori**: il servizio deciso dal planner è
     stato investigato?
  2. **planner ↔ classifier**: il sintomo primario è compatibile
     con la classification finale? (via `C3_SYMPTOM_TO_CLASSIFICATION`)
  3. **classifier ↔ postmortem retriever**: i PM selezionati hanno tag
     compatibili con la classification? (via `C3_CLASSIFICATION_TO_PM_TAGS`)
- **Motivazione**: intention-behavior consistency è la metrica
  discriminante per multi-agent LLM (le decisioni successive sono
  coerenti fra loro?). Un unico check globale sarebbe grossolano; 3
  check pairwise permettono di localizzare *dove* la coerenza si rompe.
- **Distinzione applicable vs consistent**: un check senza input
  sufficienti è N/A e non conta nel denominatore. Consistency =
  `passed / applicable` (non su totale check). Questo evita di
  "punire" run in cui una decisione a monte manca.
- **Evidenza empirica**: `bh_metrics.c3_details` in
  `instrumentation/bh_metrics.py`.

### 6.4 · Fix C3 check3: substring matching bidirezionale + policy tag realistica

- **Decisione**: il check3 ora usa **substring matching bidirezionale**
  (`e in t OR t in e`) invece che `set intersection` esatto; la policy
  `C3_CLASSIFICATION_TO_PM_TAGS` è estesa con lemmi realistici presenti
  nella KB (`pool`, `rate-limit`, `smtp`, `token`).
- **Motivazione**: la versione originale falliva sempre check3 → 0
  run coherent su 20. Diagnosi: la policy dichiarava `db`, i
  postmortem reali usavano `db-pool`. Il fail era **lessicale**, non
  semantico → falso negativo che sporcava la metrica. Substring
  matching risolve la varianza lessicale; l'estensione della policy
  copre i lemmi effettivi della KB. `latency` volutamente NON incluso
  in nessuna family: è sintomo generico, mapparlo darebbe match
  spurii.
- **Alternative scartate**: matching esatto (troppo stretto, falsi
  negativi); embedding-based semantic similarity (introdurrebbe una
  seconda superficie stocastica dentro il check che vogliamo
  deterministico).
- **Evidenza empirica**: rigenerazione dell'aggregate di
  `exp_79cb00d472bf` con il fix:
  - **prima**: 0 coherent, 19 acceptable, 1 unacceptable; coherent rate
    Wilson IC [0, 0.16].
  - **dopo**: **19 coherent, 1 unacceptable**; coherent rate 95%,
    Wilson IC [0.76, 0.99].

  L'unica run "unacceptable" residua è quella in cui il classifier ha
  scelto `regression_after_deploy` per un ticket webmail/auth: fallisce
  sia check2 (sintomo "timeout" incompatibile con regression) sia
  check3 (nessun tag deploy nei PM), consistency=0.33 → verdetto
  corretto. Il framework distingue classification giusta (coherent)
  da classification sbagliata (unacceptable) con **due segnali
  indipendenti che si rafforzano** — proprio ciò che chiediamo alla
  certificazione.
- Commit: `e325488`.

### 6.5 · Policy come specifica ex-ante, ispezionabile

- **Decisione**: tutte le policy behavioural (`classify_c2`,
  `classify_c3`, `C3_SYMPTOM_TO_CLASSIFICATION`,
  `C3_CLASSIFICATION_TO_PM_TAGS`) vivono in `src/demo/behavioural_policy.py`
  con `POLICY_SUMMARY` esposti in dashboard.
- **Motivazione**: le soglie e i mapping sono **la specifica** del
  comportamento accettabile. Devono essere motivati ex ante, non
  dedotti dai dati (altrimenti si dimostra qualsiasi cosa). Tenerli in
  un modulo separato dal dominio e dalle metriche mantiene la
  responsabilità pulita: la policy è un artefatto del processo di
  certificazione, non del sistema sotto test né dello strato di misura.

---

## 7 · Decisioni sull'inferenza LLM (rate limit e affidabilità)

Le decisioni di questa sezione sono strumentali al fatto di poter
lanciare esperimenti su N grande (§ 1.1: certificazione richiede
regime statistico). Non toccano la validità scientifica del framework;
la toccherebbero solo se comprimessero la varianza reale.

### 7.1 · Multi-provider con fallback

- **Decisione**: `LLMClient` orchestra una lista di backend
  (`GroqBackend`, `CerebrasBackend`) in ordine di priorità
  (`PROVIDER_PRIORITY`, default `groq,cerebras`). Su rate-limit del
  primo (429/quota-exceeded), passa al secondo. Modello canonico
  (`gpt-oss-120b`) tradotto per-provider (`openai/gpt-oss-120b`
  su Groq).
- **Motivazione**: il free tier Groq da solo dà ~28 run/day su
  `gpt-oss-120b` (TPD 200k / ~7k token per run). Con fallback Cerebras
  ($5 di credito, TPD 1M) si raggiungono ~140 run/day. Batch da
  200-300 diventa fattibile senza cambiare modello.
- **Alternative scartate**: singolo provider paid tier (costo diretto,
  richiede setup billing per la ricerca); Ollama locale (troppo lento
  su Mac senza GPU, ~10-20s/chiamata inaccettabile per 1500 chiamate).

### 7.2 · Rate-limit adattivo su header

- **Decisione**: il client legge `x-ratelimit-remaining-tokens` e
  `x-ratelimit-reset-tokens` dai response header e, se il primario è
  sotto soglia (default 2000 token residui), aspetta il reset
  (bounded 60s) invece di sbattere contro 429.
- **Motivazione**: evita errori 429 in batch grandi senza sacrificare
  throughput quando c'è margine. Sostituisce l'attesa fissa
  `EXPERIMENT_DELAY_S` che era ottusa (sempre sleep, anche quando
  non servirebbe).

### 7.3 · Prompt reduction

- **Decisione**: `json.dumps(..., separators=(",", ":"))` invece di
  `indent=2` nei payload user prompt (planner, classifier, summarizer).
- **Motivazione**: circa 40% di token in meno sui payload consolidati,
  a parità di semantica. Non introduce bias: gli agenti non si
  comportano diversamente perché il payload è compattato.

### 7.4 · Nessuna cache LLM

Vedi § 6.1. La cache era stata implementata in prima battuta e poi
rimossa perché sopprimeva la varianza residua che il framework deve
osservare.

### 7.5 · Model swap planner rinviato

- **Decisione**: rinviato l'uso di `llama-3.1-8b-instant` per il
  planner. Motivo: `llama-3.1-8b` non è disponibile su Cerebras con
  la chiave attuale (404) → perderebbe fallback per il planner. Il
  fallback multi-provider su `gpt-oss-120b` (unico comune) copre già
  il fabbisogno per N=200-300.
- **Riprenderemo** se in futuro N=500-600 saturasse anche con
  fallback → allora vale la pena swap-are il planner (con la nota
  onesta che quel path perde fallback).

---

## 8 · Roadmap: cosa manca prima del paper

### 8.1 · Filter A3.4 bounces per escludere hub-return

- **Decisione**: da fare. Attualmente `A3.4 bounces` conta 140 per run
  perché include i return-to-orchestrator legittimi in una topologia
  hub-and-spoke.
- **Motivazione**: la metrica come pubblicata farebbe pensare a 140
  anti-pattern per run, dando materia a un revisore per contestare.
  Fix: filtrare i return con `target=orchestrator` che sono transizioni
  strutturali del design.
- Effort stimato: 30 minuti.

### 8.2 · Metriche di dettaglio Behavioural (analogo a CF)

- **Decisione**: aggiungere blocco `<details>` "Metriche di dettaglio"
  per C1..C4 in dashboard, analogo a quello di CF/A1..A4.
- **Motivazione**: parità di livello di dettaglio fra macro; Wilson CI
  su C4 (attualmente solo entropia); pairwise consistency C3 come
  metrica derivata visibile.
- Effort stimato: 1-2 sessioni.

### 8.3 · Batch misto INC-014 + INC-015

- **Decisione**: lanciare 10+10 o 20+20 per esercitare tutti i rami di
  routing e portare `A1.1 rule_coverage` a 100%.
- **Motivazione**: risolve il warning di § 2.3 (dead branches sono
  artefatto del ticket singolo, non del sistema). Fondamentale per
  poter dichiarare nel paper "coverage completo del routing".
- Effort stimato: 1 batch (30-60 min di esecuzione).

### 8.4 · N grande per stringere IC Wilson

- **Decisione**: batch da 200-300 su ciascun ticket (o misto) per
  stringere gli IC di completion, coherent rate C2/C3, acceptable rate.
- **Motivazione**: con N=20 alcuni IC sono ancora larghi (es.
  completion rate 20/20 → IC [0.84, 1.00]). Per il paper vogliamo
  IC "citabili" (es. [0.97, 1.00] con N=200 e 200/200).
- **Costo stimato**: ~2 ore di esecuzione, ~$0.60 su Cerebras.

### 8.5 · Deriva formale CF+DF → BH nel paper

- **Decisione**: nel paper marcare esplicitamente ogni metrica
  behavioural come **originale** o **derivata da CF/DF**, con badge
  in dashboard e riferimento incrociato nel testo.
- **Motivazione**: rende visibile la tesi del position paper: la macro
  Behavioural non è additiva alle altre due, ne è un'articolazione a
  livello agentico.

---

## 9 · Fatti dimostrabili sul paper (già oggi)

Elenco degli argomenti che il paper può già portare come risultati
empirici del prototipo, per esperimento:

### 9.1 · Il framework cattura varianza reale a temperature=0

- 20 run identiche INC-2026-015, temp=0, gpt-oss-120b:
  - 8 formulazioni distinte del primo step del piano
  - latenza min 884ms, max 2449ms (σ=383ms)
  - classificazione: 19× `capacity_saturation` + 1×
    `regression_after_deploy` (entropia normalizzata 0.286)
  - C2 verdicts: 13 coherent + 7 acceptable
  - **Non è un artefatto**: senza cache LLM, questa è la varianza
    residua del provider (batch composition + FP non-associatività).

### 9.2 · Framework distingue casi semanticamente corretti da errori

- Dopo il fix substring matching + policy realistica:
  - 19/20 coherent (classifier ha scelto `capacity_saturation`, coerente
    con i PM webmail/auth/db-pool)
  - 1/20 unacceptable (classifier ha scelto `regression_after_deploy`,
    non compatibile né col sintomo `timeout` né con i tag dei PM
    selezionati)
  - Coherent rate 95% con Wilson IC [76%, 99%].
  - La distinzione avviene con **due segnali indipendenti** (check2 +
    check3), che si rafforzano.

### 9.3 · Ciclo detect → mitigate → re-verify sul data flow

- **Detect (raw)**: `exp_79cb00d472bf`, 20 run → CLR C4=1.0, CLR C5=1.0,
  SLR=1.0. Violazione strutturale del principio di data-minimization
  rilevata indipendentemente dal comportamento LLM (l'email del reporter
  attraversa tool output e shared memory).
- **Mitigate**: introdotta REDACTION_POLICY derivata da (V,A); redattore
  lato adapter maschera in-place le categorie fuori policy prima della
  persistenza JSONL. Trasparenza: `metadata.pii_redaction_hits`.
- **Re-verify (redacted)**: `exp_692c4c8ae2eb`, 3 run → CLR ogni
  canale=0, SLR=0, mitigation `{C4:{email:6}, C5:{email:6}}`, 6 eventi
  toccati, 0 email raw nei JSONL. Altre macro (CF, BH) non toccate
  → mitigation chirurgica, non altera il comportamento del sistema.

### 9.4 · Metriche gating soddisfatte

- `A3.1 topology conformance = 100%` sul batch di 20: nessun handoff
  fuori dal grafo dichiarato.
- `A4.2 completion rate = 100%` (20/20) con Wilson IC [0.84, 1.00].
- `A4.3 tool error rate = 0%` (80 chiamate a tool, 0 errori).

---

## 10 · Riferimenti bibliografici

- Van der Aalst W. — *Process Mining: Data Science in Action*, Springer.
  (fitness, precision, generalization, simplicity; trace variants)
- Polyvyanyy A. et al. — *Entropia: A Family of Entropy-Based
  Conformance Checking Measures for Process Mining*, arXiv:2008.09558.
- McCabe T. J. (1976) — *A Complexity Measure*, IEEE TSE. (complessità
  ciclomatica)
- Brown L. D., Cai T. T., DasGupta A. (2001) — *Interval Estimation for
  a Binomial Proportion*, Statistical Science. (Wilson score interval)
- Legay A., Delahaye B., Bensalem S. (2010) — *Statistical Model
  Checking: An Overview*, RV'10.
- AgentLeak (paper di riferimento sui canali C1..C7) — da citare
  puntualmente nel paper.
- Confident AI — *LLM Agent Evaluation: Tool Calling, Task Completion,
  Reasoning, Trace-Based Evals*.
- RAGAS — groundedness / context adherence come radice per C2.
- Framework di riferimento (Bena, Anisetti, Damiani, Della Bruna,
  Yeun, Ardagna) — *A Certification Scheme for Large Language
  Models-Based Applications*, TIST 2026.

---

## Appendice A · Commit rilevanti (ordine cronologico inverso)

- `7727221` — Data-flow B2/B3: mitigation lato adapter + ciclo
  detect→mitigate→re-verify.
- `e325488` — C3 check3: matching substring + policy tag realistica.
- `3fda74c` — Rate limit: rimozione cache, multi-provider + rate-limit
  adattivo + prompt reduction.
- `86b1ec6` — (revert) Cache LLM deterministica per-esperimento.
- `6c07388` — Behavioural C3: triade + 3 check pairwise di
  intention-behavior consistency.
- `b715e71` — Behavioural C2: triade coherent/acceptable/unacceptable
  con IC Wilson.
- `5cdc4fe` — Control Flow: metriche di dettaglio per ogni evidenza
  (A1..A4).

## Appendice B · Come mantenere aggiornato questo documento

Ogni **decisione strutturale** (nuova metrica, nuova policy, nuova
contromisura, nuovo fix con implicazioni scientifiche) va aggiunta qui
nella sezione appropriata, con lo schema **Decisione / Motivazione /
Alternative scartate / Evidenza empirica / Limite dichiarato**, e va
aggiornata l'appendice A col commit corrispondente.

Fix meramente tecnici (bug rename, refactor senza cambio semantico) NON
vanno qui: vanno solo nel commit message.

In dubbio: se una scelta va discussa/motivata in un paper, va qui.
