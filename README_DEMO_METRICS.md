# Demo osservativa — Control Flow · Data Flow · Comportamentale

Questa demo mostra, in modo operativo e trasparente, come il sistema raccoglie
e aggrega evidenze per le tre macro-dimensioni della ricerca. **Non emette
alcun giudizio di verificabilità o certificazione**: la UI e i dati sono
pensati per far vedere, ai supervisori, dove sono le sonde e cosa producono.

Il caso d'uso è un incident triage multi-agente: partendo da un ticket di
incidente con sintomi multipli, il sistema pianifica, investiga (log +
metriche + postmortem), classifica e riepiloga — producendo per costruzione
tutti gli eventi di interesse.

---

## Come lanciarla

```bash
# 1. Ambiente
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # aggiungi GROQ_API_KEY

# 2. Web UI
python -m webapp.server   # http://127.0.0.1:8000
```

Nella pagina:

1. **Seleziona la macro** in alto: `Control Flow`, `Data Flow`, `Comportamentale`.
2. Scegli il **ticket incident** (INC-2026-014 o INC-2026-015).
3. Imposta il **numero di run** (default 10, come da documento delle evidenze).
4. Premi **Lancia esperimento**.
5. Vedrai:
   - eventi in **live stream** filtrati per la macro selezionata;
   - **Evidence card** per ciascuna evidenza della macro (A1..A4 / B1..B4 /
     C1..C4), con nome, dove/come è catturata, totale sulle N run e
     distribuzione per run;
   - **Aggregazione multi-run** in tabelle e mini indicatori;
   - **Architettura osservata**: i nodi del sistema evidenziati sono quelli
     che contribuiscono alla macro corrente.

## Configurazione

Tutti i parametri stanno in `.env` (o env vars):

| Variabile           | Default                     | Cosa fa |
|---------------------|-----------------------------|---------|
| `GROQ_API_KEY`      | —                           | Chiave API Groq (obbligatoria) |
| `MODEL`             | `openai/gpt-oss-120b`       | Modello LLM Groq |
| `TEMPERATURE`       | `0.0`                       | Temperatura sampling |
| `EXPERIMENT_RUNS`   | `10`                        | Numero di run per esperimento |
| `EXPERIMENT_DELAY_S`| `1.0`                       | Pausa tra run consecutive (rate limit) |

Il modello **è mostrato nella UI** in alto (`modello: ...`) durante la demo.

Alternative valide per `MODEL`:
- `openai/gpt-oss-120b` — 131K contesto, raccomandato per orchestrazione (default);
- `qwen/qwen3.6-27b` — sostituto naturale del precedente Qwen3-32b deprecato;
- `llama-3.3-70b-versatile`.

---

## Evidenze raccolte, per macro

### Control Flow (§2 documento delle evidenze)

| ID | Nome | Dove | Come | Frequenza |
|----|------|------|------|-----------|
| A1 | Decisioni dell'orchestratore | nodo `orchestrator` | hook nel routing rule-based; ogni decisione emette `orchestrator_decision` con motivo e alternative | ~7-8 per run |
| A2 | Piani + replanning | agente `planner` | span aperto ad ogni pianificazione, marcato `updated=True` in caso di replan | 1-2 per run |
| A3 | Handoff tra agenti | confini agent-orchestrator | evento `handoff` con `source`, `target`, `reason` | ~7-8 per run |
| A4 | Metriche di percorso | derivata dalla trace | step count, tool call, durata, esito | 1 riga per run |

### Data Flow (§3 documento delle evidenze, canali AgentLeak)

| ID | Nome | Dove | Come | Frequenza |
|----|------|------|------|-----------|
| B1 | Tracce per canale C1..C7 | adapter layer che intercepta le sette classi di canale | ogni evento è marcato con `channel_id`; JSONL append-only | tutti gli eventi con canale associato |
| B2 | Channel Leakage Rate (proxy) | detection PII sul contenuto dei canali | regex su categorie di V (vault), confronto con Allowed Set A per canale | 1 valore per canale, per esperimento |
| B3 | System Leakage Rate (proxy) | aggregazione OR sui canali | conteggio di run con ≥1 canale fuori policy in S = {C1,C2,C5} | 1 valore per esperimento |
| B4 | Vault V + Allowed Set A | policy dichiarata in codice | categorie di dati sensibili + permessi per canale | statico, versionato con l'app |

I sette canali del framework AgentLeak (Rongxin Liu et al., 2025) sono:

- **C1** Final output → user
- **C2** Inter-agent messages
- **C3** Tool input
- **C4** Tool output
- **C5** Shared memory / workspace
- **C6** Reasoning traces / logs
- **C7** Persistent artifacts

### Comportamentale (§4 documento delle evidenze)

| ID | Nome | Dove | Come | Frequenza |
|----|------|------|------|-----------|
| C1 | Trace end-to-end (span-per-tick) | unione di tutti gli eventi della run | timeline + vista gerarchica per agente | 1 traiettoria per run |
| C2 | Coerenza state ↔ output | proiezione dello stato consolidato + testo dell'output finale | verifica di presenza lessicale dei campi chiave (classification/priority/service) nell'output | 1 riga per run |
| C3 | Sequenza decisioni successive | ordine cronologico dei `decision_point` | estrazione e linearizzazione per ispezione | 1 riga per run |
| C4 | Varianza comportamentale su N run | sulle N ripetizioni dello stesso ticket | distribuzioni + entropia normalizzata su firme di traiettoria e campi finali | 1 report per esperimento |

---

## Come leggere la UI

- **Overview** in alto: macro corrente, run eseguite/pianificate, modello.
- **Evidence catalog**: una card per ogni evidenza. La *heatmap* per-run
  mostra il numero di occorrenze in ciascuna delle N run.
- **Estratti**: cliccando `Estratti` in fondo alla card, vedi il payload
  reale catturato (non un mockup: JSONL letto dal disco).
- **Aggregazione multi-run**: mini tabelle con le metriche derivate.
- **Live event stream** (in fondo): eventi filtrati sulla macro selezionata,
  in tempo reale durante l'esecuzione.
- **Architettura osservata**: nodi evidenziati = nodi che contribuiscono
  alla macro corrente.

## Dove finiscono i dati

Tutto quello che vedi in UI arriva da file su disco, ispezionabili a mano:

```
experiments/<experiment_id>/
├── experiment.json           # metadati esperimento + indice run
├── runs/<run_id>.jsonl       # JSONL append-only degli eventi di una run
└── aggregate/metrics.json    # metriche aggregate per macro (Aggregator output)
```

Le tracce sono **riproducibili e ispezionabili**: puoi rilanciare
l'Aggregator su una vecchia cartella per ricostruire tutte le metriche.

## Note

- La demo non fa distinzioni tra "leakage" reale e "occorrenza di V su canale":
  segnala le *occorrenze di categorie di V fuori Allowed Set A per canale*. È
  una sonda, non un giudizio di sicurezza.
- Le categorie V e A per canale sono definite in
  `src/instrumentation/aggregator.py` (`VAULT_PATTERNS`, `ALLOWED_SET_A`).
  Sono didattiche: rendono non ambigua la nozione di leakage per la demo.
- Il non-determinismo degli LLM produce distribuzioni diverse su run ripetute
  (macro *Comportamentale* → C4): questo è deliberato ed è ciò che la demo
  mostra come varianza sull'N-run.
