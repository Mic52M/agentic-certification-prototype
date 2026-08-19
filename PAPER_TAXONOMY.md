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

## 5 · I sette attributi tassonomici

Ogni evidenza dichiara sette attributi. Sono **ortogonali**: ognuno
risponde a una domanda distinta del processo di certificazione.

### 5.1 · Hook (punto di aggancio)
*Dove* nel sistema viene captata l'evidenza. Dominio:
`{agent, orchestrator, tool_adapter, event_store}`. Ogni evidenza è
prodotta da un componente specifico dell'architettura di raccolta.
Rilevante per il paper: il hook determina l'invasività della
strumentazione.

### 5.2 · Measure (cosa misura)
*Cosa* è la grandezza osservata. Dominio:
`{count, ratio, probability, categorical_distribution,
sequence, boolean, duration_ms}`. Determina il tipo di aggregazione
possibile e la scelta della metrica statistica.

### 5.3 · Moment (momento di raccolta)
*Quando* rispetto al flusso operativo l'evidenza è emessa. Dominio:
`{pre-event, during-event, post-event, end-of-run, end-of-batch}`.
Distingue metriche "istantanee" da metriche "aggregate".

### 5.4 · Cadence (cadenza di collezione)
La dimensione **centrale** del paper. *Come* nel tempo viene collezionata
l'evidenza. Dominio:
- `one-shot`: rilevata una sola volta, non cambia (es. topologia dichiarata).
- `per-event`: emessa ogni volta che l'evento sorgente occorre.
- `per-run`: aggregata a fine run.
- `sliding-window`: media/aggregato su finestra scorrevole di N run recenti (**buco corrente** del prototipo).
- `cross-run`: aggregata a fine batch, tipicamente con IC.

### 5.5 · Lifecycle (ciclo di vita nel tempo)
La dimensione **più nuova** del paper. *Come si comporta* l'evidenza
nel tempo dopo la raccolta. Dominio:
- `stable-in-run`: fissata all'inizio della run, non cambia.
- `monotone-growing`: cresce nel tempo (es. cumulative token count).
- `volatile`: cambia a ogni tick senza pattern (es. reasoning trace).
- `decaying`: perde rilevanza col tempo (es. freshness del contesto —
  non ancora modellato dal prototipo).

### 5.6 · Statistical Regime (regime statistico)
*Come va interpretata*. Dominio:
- `deterministic`: predicato binario, verificabile classicamente.
- `stochastic-single-run`: osservata su una run, con varianza intrinseca.
- `stochastic-need-CI`: richiede N run e intervallo di confidenza per
  essere significativa.

### 5.7 · Root (radice bibliografica)
*Da dove viene*. Dominio delle famiglie note:
`{process-mining, software-testing, agent-evaluation,
statistical-model-checking, groundedness-adherence,
agentleak-datachannels, custom-agentic}`. Rende esplicito il debito
intellettuale.

---

## 6 · La matrice tassonomica (bozza)

Costruiremo nel paper una matrice `evidenza × attributo`. Bozza per
alcune evidenze illustrative (verrà completata nel prototipo prima di
essere pubblicata):

| Evidenza | Hook | Measure | Moment | Cadence | Lifecycle | Regime | Root |
|---|---|---|---|---|---|---|---|
| A1.1 rule coverage | orchestrator | ratio | end-of-batch | per-run→cross-run | stable-post-run | deterministic | software-testing |
| A3.1 topology conformance | orchestrator | ratio | end-of-batch | per-run→cross-run | stable-post-run | deterministic | process-mining |
| A4.2 completion rate | orchestrator | probability | end-of-batch | cross-run | stable-post-batch | stochastic-need-CI | statistical-model-checking |
| B2 CLR per canale | tool_adapter | ratio | during-event→end-of-batch | per-event→cross-run | monotone-growing→stable | deterministic | agentleak-datachannels |
| C2 coverage state↔output | agent | probability | end-of-run | per-run→cross-run | stable-post-run | stochastic-need-CI | groundedness-adherence |
| C3 pairwise consistency | agent | ratio | end-of-run | per-run→cross-run | stable-post-run | stochastic-need-CI | custom-agentic |
| C4 trajectory signature entropy | event_store | probability | end-of-batch | cross-run | stable-post-batch | stochastic-need-CI | process-mining |

Nella matrice completa: 22+10+4 = **36 righe**, 7 colonne = 252 celle
da riempire con onestà.

---

## 7 · Ciclo di vita e collezione: il vero cuore del paper

Le sezioni § 5.4 (cadence) e § 5.5 (lifecycle) sono le più nuove: la
letteratura di agent observability oggi tratta le evidenze come
**punti** (una metrica ha un valore), non come **oggetti temporali**
(un'evidenza cambia nel tempo, si deteriora, si rigenera).

Domande di ricerca che il paper porrà esplicitamente:
- **Deterioramento**: quando un'evidenza smette di essere
  rappresentativa? (es. una topology conformance calcolata su un
  batch di 6 mesi fa vale ancora se il codice degli agenti è
  cambiato?)
- **Rigenerazione**: quando va rieseguita la raccolta? (per-commit?
  per-deploy? on-demand?)
- **Composizione temporale**: come si combinano evidenze raccolte in
  finestre temporali diverse per produrre un verdetto attuale?

Nessuna di queste domande ha risposta pulita in letteratura; il paper
può proporre un framework di primo livello.

---

## 8 · Processo di collezione delle evidenze

Il § 8 del paper discuterà **come** ogni evidenza viene raccolta, con
particolare attenzione ai **blind spots**: cosa il framework NON riesce
a osservare.

Bozza dei blind spots noti del prototipo:
- **Prompt fingerprint post-templating**: osserviamo il fingerprint
  del prompt inviato al provider, non il prompt effettivamente
  processato dal modello (che può differire per template interni).
- **Batch composition lato provider**: sappiamo che varia (§ 6.1
  RESEARCH_DECISIONS.md), non possiamo osservarla direttamente.
- **Aggiornamenti silenziosi del modello**: rilevabili solo
  indirettamente via divergenza dei fingerprint.
- **Quasi-identifier PII**: la detection su V è per-categoria, non
  cattura combinazioni di attributi non-sensibili che identificano
  un individuo.
- **Emergenza cross-run**: comportamenti emergenti visibili solo a N
  grande non catturati con N piccolo (limite del regime statistico).

Discutere i blind spots è **contributo scientifico onesto** e apre
alla roadmap del paper 2 (composizione).

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
