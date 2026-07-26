# Metriche di dettaglio — macro Control Flow

Ogni evidenza del control flow (A1..A4) è scomposta in metriche puntuali.
Questo documento spiega, per ciascuna: **cosa misura**, **come si calcola**,
**su quale radice in letteratura poggia** e **come leggerla**.

Implementazione: [`src/instrumentation/cf_metrics.py`](src/instrumentation/cf_metrics.py).
Topologia e regole dichiarate (riferimento per la conformance):
[`src/demo/topology.py`](src/demo/topology.py).

> Nota di scope: nessuna di queste metriche emette un giudizio di conformità.
> Sono **descrittori**. La soglia e il verdetto sono decisioni successive, che
> appartengono al processo di certificazione e non allo strato di misura.

---

## Inquadramento: da dove vengono queste metriche

Le metriche attingono a tre filoni consolidati, adattati al setting agentico.

| Filone | Cosa fornisce | Metriche che ne derivano |
|---|---|---|
| **Process mining / conformance checking** (van der Aalst; Entropia, Polyvyanyy et al.) | fitness, precision, trace variants, misure entropiche | A2.3, A2.5, A4.4, A1.2 |
| **Software testing / analisi statica** | branch coverage, complessità ciclomatica (McCabe 1976) | A1.1, A3.2, A4.5 |
| **Agent evaluation / observability** | completion rate, tool error rate, step efficiency, decision surface | A1.4, A1.5, A3.6, A4.1, A4.3 |
| **Statistical model checking** | stima di proporzioni con intervallo di confidenza (Wilson) | A4.2 |

L'idea di fondo, mutuata dal conformance checking: esiste un **modello
dichiarato** (la topologia degli agenti e le regole di routing) e un
**comportamento osservato** (le tracce). Le metriche quantificano la relazione
fra i due — quanto del modello è stato esercitato, quanto dell'osservato è
ammesso dal modello, e quanto il comportamento è stabile.

---

## A1 — Decisioni dell'orchestratore

### A1.1 · Rule activation coverage
- **Cosa**: frazione delle regole di routing dichiarate che sono state
  effettivamente attivate almeno una volta.
- **Come**: si confronta il campo `reason` di ogni `orchestrator_decision`
  con l'elenco delle regole in `ROUTING_RULES`. Le regole con zero
  attivazioni sono **dead branches**.
- **Radice**: *branch coverage* del software testing.
- **Lettura**: coverage < 100% non è un difetto in sé — significa che lo
  scenario testato non esercita tutti i rami. È però un'informazione
  necessaria: una regola mai attivata è una regola **non verificata**.

### A1.2 · Distribuzione decisioni + entropia
- **Cosa**: come si distribuiscono le decisioni fra i target possibili, e
  quanto è concentrata la distribuzione.
- **Come**: conteggio per target e per motivo; entropia di Shannon
  normalizzata in [0,1].
- **Radice**: misure entropiche del conformance checking (Entropia).
- **Lettura**: entropia bassa = routing prevedibile e concentrato; alta =
  il sistema esplora molti rami diversi.

### A1.3 · Routing determinism
- **Cosa**: a parità di contesto di stato, l'orchestratore prende sempre la
  stessa decisione?
- **Come**: si costruisce una *firma di contesto* (insieme ordinato delle
  chiavi di stato valorizzate al momento della decisione) e si verifica se a
  ogni firma corrisponde un solo target.
- **Radice**: determinismo della funzione di routing; conformance a livello
  di decisione.
- **Lettura e limite dichiarato**: la firma usa **le chiavi, non i valori**
  dello stato. Due momenti diversi con le stesse chiavi valorizzate ma valori
  differenti risultano indistinguibili, quindi la metrica può segnalare
  ambiguità apparenti. È un **proxy conservativo**: sottostima il determinismo,
  non lo sovrastima. L'orchestratore è deterministico per costruzione
  (`decide_next` è una funzione pura); la metrica misura quanto ciò è
  *osservabile dalla traccia*, che è cosa diversa e più interessante per la
  certificazione.

### A1.4 · Branching factor
- **Cosa**: quante alternative erano disponibili quando l'orchestratore ha
  deciso.
- **Come**: dal campo `alternatives` dell'evento (regole successive risultate
  vere al momento della valutazione).
- **Radice**: *decision surface* nella letteratura di agent observability.
- **Lettura**: branching factor 0 = decisione forzata (una sola regola vera).
  Un'alta quota di decisioni forzate indica un routing fortemente vincolato,
  quindi più facilmente certificabile in modo strutturale.

### A1.5 · Decisioni per run
- **Cosa**: quante decisioni servono per concludere una run (min/media/max/σ).
- **Radice**: step-level agent evaluation.

---

## A2 — Spans di pianificazione

### A2.1 · Lunghezza del piano
- **Cosa**: numero di step nel piano prodotto dal planner, con distribuzione.
- **Radice**: planning span / decision surface.

### A2.2 · Replanning rate
- **Cosa**: frazione di run in cui il piano è stato rivisto almeno una volta.
- **Lettura**: un replanning rate alto indica instabilità della pianificazione;
  è una delle evidenze corroboranti per la robustezza del workflow (assenza di
  cicli di pianificazione infinita).

### A2.3 · Plan-execution fitness / precision
- **Cosa**: quanto il piano dichiarato corrisponde a ciò che è stato realmente
  eseguito.
  - **fitness** = frazione degli step pianificati riconducibili a un agente
    effettivamente eseguito (*il piano è stato seguito?*);
  - **precision** = frazione degli agenti eseguiti che erano previsti dal piano
    (*ci sono stati passi non pianificati?*).
- **Radice**: le due dimensioni classiche del conformance checking — fitness
  (il log si replica sul modello) e precision (il modello non ammette
  comportamento extra).
- **Limite dichiarato**: il piano è testo libero, quindi il matching è un
  **proxy lessicale** tra i token dello step e l'area semantica dell'agente
  (log, metriche, postmortem, classificazione, report). Non è entailment.

### A2.4 · Latenza di pianificazione
- **Cosa**: durata dello span di pianificazione (media, σ, p95).
- **Radice**: span duration nel tracing distribuito.

### A2.5 · Variabilità del piano fra run
- **Cosa**: su ripetizioni dello stesso ticket, quanto varia il piano.
- **Come**: entropia normalizzata sulla distribuzione delle lunghezze,
  numero di formulazioni distinte del primo step.
- **Radice**: trace variant analysis.

---

## A3 — Handoff

### A3.1 · Topology conformance (role adherence)
- **Cosa**: gli handoff osservati sono tutti ammessi dalla topologia
  dichiarata?
- **Come**: il grafo osservato deve essere un **sottografo** di quello
  dichiarato in `DECLARED_EDGES`. Gli archi osservati e non dichiarati sono
  elencati come `unexpected_edges`.
- **Radice**: conformance checking (relazione sottografo modello/osservato);
  è la metrica che sostanzia la proprietà di **role adherence**.
- **Lettura**: è la metrica **gating** del control flow. Conformance < 100%
  significa che il sistema ha eseguito un passaggio di controllo non previsto
  dall'architettura dichiarata — un fatto che invalida qualunque
  ragionamento successivo sul flusso.

### A3.2 · Edge coverage
- **Cosa**: quanta parte della topologia dichiarata è stata esercitata.
- **Come**: archi osservati ∩ dichiarati, diviso dichiarati. Elenca gli archi
  mai percorsi.
- **Radice**: coverage testing applicato al grafo.
- **Lettura**: duale di A3.1. Conformance risponde a *"ha fatto solo cose
  ammesse?"*; coverage risponde a *"quanto di ciò che può fare l'abbiamo
  visto fare?"*.

### A3.3 · Densità del grafo osservato
- **Cosa**: |E| / (|N| · (|N|−1)) sul grafo diretto osservato.
- **Radice**: densità di un grafo diretto.
- **Lettura**: topologie a stella (hub-and-spoke) hanno densità bassa;
  densità crescente indica interazione più diffusa fra agenti — quindi più
  canali e più superficie da certificare.

### A3.4 · Bounce e ritorni
- **Cosa**: rimbalzi A→B→A consecutivi e agenti riattivati più volte nella
  stessa run.
- **Radice**: anti-pattern di orchestrazione multi-agente (handoff troppo
  frequenti, responsabilità non chiare).

### A3.5 · Fan-out per componente
- **Cosa**: verso quanti destinatari distinti instrada ciascun componente.
- **Lettura**: in una topologia hub-and-spoke ci si attende fan-out alto solo
  per l'orchestratore. Fan-out inatteso su un agente segnala una deviazione
  dal design.

### A3.6 · Handoff per run
- **Cosa**: quanti passaggi di controllo servono a concludere una run.

---

## A4 — Metriche di percorso

### A4.1 · Step count
- **Cosa**: numero di eventi per run (min/media/max/σ, p95).

### A4.2 · Completion rate + intervallo di confidenza
- **Cosa**: probabilità che il sistema porti a termine il task, con
  **intervallo di Wilson al 95%**.
- **Radice**: statistical model checking; Wilson score interval (preferito
  all'intervallo normale con N piccolo — non degenera quando la proporzione
  è 0 o 1).
- **Lettura**: è la metrica che collega direttamente il control flow al
  **regime statistico** della certificazione. Con N=4 e 4 successi il punto
  è 100% ma l'intervallo è ampio (≈51–100%): è esattamente l'informazione che
  serve per non sovra-dichiarare su poche run.

### A4.3 · Tool error rate
- **Cosa**: frazione di chiamate a tool che falliscono.
- **Radice**: KPI standard di agent evaluation.

### A4.4 · Trace variants
- **Cosa**: quante sequenze di esecuzione distinte produce lo stesso ticket,
  con entropia normalizzata.
- **Radice**: trace variant analysis del process mining.
- **Lettura**: 1 variante su N run = percorso perfettamente stabile.
  Più varianti = biforcazioni reali nel control flow, da caratterizzare.

### A4.5 · Complessità ciclomatica
- **Cosa**: M = E − N + 2 sul grafo di control flow osservato.
- **Radice**: McCabe (1976).
- **Lettura**: numero di cammini linearmente indipendenti. Dà una misura
  sintetica di quanto è articolato il flusso, e quindi di quanti casi
  servirebbe coprire per esercitarlo interamente.

### A4.6 · Durata della run
- **Cosa**: durata complessiva (min/media/max/σ, p95).
- **Radice**: latenza di pipeline nei playbook di orchestrazione.

---

## Come leggerle insieme

Le metriche si compongono in tre domande di livello superiore:

1. **Il sistema fa solo ciò che è ammesso?** → A3.1 (conformance), A1.1
   (nessuna attivazione di regole non dichiarate).
2. **Quanto del sistema abbiamo osservato?** → A1.1 (coverage regole),
   A3.2 (coverage archi), A4.4 (varianti esercitate).
3. **Quanto è stabile e prevedibile?** → A1.3 (determinismo del routing),
   A2.2/A2.5 (stabilità della pianificazione), A4.2 (completion con IC),
   A4.4 (entropia delle varianti).

La prima è verificabile in modo **strutturale** (è una proprietà del grafo).
Le altre due richiedono un **regime statistico**: valgono su una distribuzione
di run, non su una singola esecuzione.

---

## Riferimenti

- van der Aalst W. — *Process Mining: Data Science in Action*, Springer.
  (fitness, precision, generalization, simplicity; trace variants)
- Polyvyanyy A. et al. — *Entropia: A Family of Entropy-Based Conformance
  Checking Measures for Process Mining*. [arXiv:2008.09558](https://arxiv.org/pdf/2008.09558)
- McCabe T. J. (1976) — *A Complexity Measure*, IEEE TSE. (complessità ciclomatica)
- Brown L. D., Cai T. T., DasGupta A. (2001) — *Interval Estimation for a
  Binomial Proportion*, Statistical Science. (Wilson score interval)
- Legay A., Delahaye B., Bensalem S. (2010) — *Statistical Model Checking:
  An Overview*, RV'10.
- Confident AI — *LLM Agent Evaluation: Tool Calling, Task Completion,
  Reasoning, Trace-Based Evals*. [link](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide)
  (step efficiency, tool call accuracy, completion rate)
