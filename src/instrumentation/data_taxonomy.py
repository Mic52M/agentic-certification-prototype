"""Tassonomia dei dati grezzi elementari raccolti dal framework.

Fonte unica di verità per la matrice tassonomica del primo paper
(spina dorsale in PAPER_TAXONOMY.md § 6). Ogni entry è un DATO GREZZO
(campo elementare del payload di un evento), NON una metrica aggregata.

Gli undici attributi seguono lo schema di PAPER_TAXONOMY.md § 5:
  name · type · hook · moment · cardinality · lifecycle · reproducibility
  · cadence · persistence · pii · unit

Domini chiusi degli attributi (documentati per ispezione dashboard):
"""

from __future__ import annotations

from typing import Any

# =========================================================================
# Domini chiusi degli attributi (esposti alla dashboard per filtri).
# =========================================================================
DOMAINS: dict[str, list[str]] = {
    "macro": ["common", "control_flow", "data_flow", "behavioral"],
    "type": [
        "string", "int", "float", "timestamp_ms", "boolean",
        "list", "dict", "categorical", "text_free", "sha256",
    ],
    "hook": [
        "recorder-builtin", "orchestrator", "agent", "tool_adapter",
        "event_store", "aggregator", "source_code",
    ],
    "moment": ["pre-event", "during-event", "post-event", "end-of-run", "end-of-batch"],
    "cardinality": ["1", "N=events", "N=decisions", "N=handoffs", "variable-bounded", "N per batch"],
    "lifecycle": ["snapshot", "stable-in-run", "derived-deterministic", "one-shot", "volatile", "decaying"],
    "reproducibility": ["re-collectable-identical", "re-collectable-analogous", "one-shot"],
    "cadence": ["event-triggered", "on-demand", "polling-able", "sliding-window"],
    "persistence": [
        "jsonl.event.field", "jsonl.event.metadata", "jsonl.event.payload_redacted",
        "experiment.json", "aggregate/metrics.json", "in-memory-only",
    ],
    "pii": ["none", "email", "phone", "reporter", "ip", "userid", "may-contain-V", "audit-only", "schema"],
}


def _row(**kw: Any) -> dict[str, Any]:
    """Costruttore con defaults sensati (evita ripetizione delle chiavi).

    Attributi:
      - id, macro, evidence: coordinate della tassonomia
      - name: nome tecnico del campo nel JSONL
      - human_label: nome discorsivo human-readable in italiano
                     (visibile in dashboard come titolo della card)
      - 11 attributi tassonomici: type, hook, moment, cardinality,
        lifecycle, reproducibility, cadence, persistence, pii, unit, notes
      - usage: paragrafetto italiano che spiega COME questo dato viene
               sfruttato per costruire l'evidenza (visibile in dashboard
               come sezione dedicata). Rende esplicito il legame
               dato→evidenza — evita il "container fallacy" (DEMM 2026:
               la presenza del dato non basta, serve dichiarare il suo
               ruolo nel ragionamento di certificazione).
    """
    return {
        "id": kw["id"],
        "macro": kw["macro"],
        "evidence": kw["evidence"],
        "name": kw["name"],
        "human_label": kw.get("human_label", kw["name"]),
        "type": kw["type"],
        "hook": kw["hook"],
        "moment": kw["moment"],
        "cardinality": kw["cardinality"],
        "lifecycle": kw["lifecycle"],
        "reproducibility": kw["reproducibility"],
        "cadence": kw["cadence"],
        "persistence": kw["persistence"],
        "pii": kw.get("pii", "none"),
        "unit": kw.get("unit"),
        "notes": kw.get("notes"),
        "usage": kw.get("usage"),
    }


# =========================================================================
# Campi comuni recorder-builtin (presenti in OGNI evento).
# =========================================================================
COMMON: list[dict[str, Any]] = [
    _row(id="E0.1", macro="common", evidence="recorder-builtin",
         name="event_id", human_label="Identificatore univoco dell'evento",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field",
         notes="UUID a 16 caratteri assegnato ad ogni evento.",
         usage="Chiave primaria per riferirsi puntualmente a un evento nella "
               "trace. Consente join fra eventi (parent/child, richiesta/"
               "risposta di un tool) e permette all'aggregator di deduplicare "
               "eventi ricevuti da percorsi diversi. Non alimenta metriche "
               "direttamente ma è precondizione di ogni analisi provenance."),
    _row(id="E0.2", macro="common", evidence="recorder-builtin",
         name="run_id", human_label="Identificatore della run",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Chiave di raggruppamento fondamentale: tutte le metriche "
               "per-run (A4.1 step count, A4.6 durata, C2 coverage state↔output) "
               "sono calcolate raggruppando gli eventi per run_id. È anche il "
               "join key con l'indice experiment.json."),
    _row(id="E0.3", macro="common", evidence="recorder-builtin",
         name="experiment_id", human_label="Identificatore dell'esperimento",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Chiave di raggruppamento per le metriche cross-run (tutta la "
               "macro C4, IC Wilson su completion A4.2, coherent/acceptable "
               "rate C2/C3). Consente il regime statistico su N ripetizioni."),
    _row(id="E0.4", macro="common", evidence="recorder-builtin",
         name="event_type", human_label="Tipo semantico dell'evento",
         type="categorical", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         notes="Dominio: enum EventKind (orchestrator_decision, handoff, tool_call, …).",
         usage="Discriminante primario per l'aggregator: seleziona gli eventi "
               "orchestrator_decision per A1, planning_span per A2, handoff "
               "per A3, tool_call/tool_result per A4.3, decision_point per C3. "
               "Senza questa tipizzazione il framework non saprebbe cosa "
               "conta cosa."),
    _row(id="E0.5", macro="common", evidence="recorder-builtin",
         name="channel_id", human_label="Canale AgentLeak",
         type="categorical", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         notes="Canale AgentLeak (C1..C7) o null se evento senza canale.",
         usage="Chiave di ripartizione per tutta la macro Data Flow. B1 conta "
               "eventi/byte per canale; B2 CLR raggruppa violazioni per canale "
               "vs ALLOWED_SET_A[channel]; il PIIRedactor applica REDACTION_"
               "POLICY[channel] prima della persistenza. Il channel_id è il "
               "primo cittadino della governance data-flow."),
    _row(id="E0.6", macro="common", evidence="recorder-builtin",
         name="macro_categories", human_label="Macro-categorie di ricerca",
         type="list", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         notes="Derivato da KIND_TO_MACROS; ogni evento contribuisce a 1..3 macro.",
         usage="Consente all'aggregator di reindirizzare uno stesso evento "
               "a più macro (es. un handoff contribuisce sia a Control Flow "
               "sia a Data Flow). Cattura formalmente il fatto che le tre "
               "macro non sono partizioni disgiunte degli eventi."),
    _row(id="E0.7", macro="common", evidence="recorder-builtin",
         name="timestamp_start", human_label="Istante di inizio dell'evento",
         type="timestamp_ms", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field", unit="ms",
         usage="Base per l'ordinamento cronologico degli eventi nella run "
               "(fondamentale per C1 timeline, C3 sequenza decisioni pairwise, "
               "A3 sequenza handoff). Insieme a timestamp_end alimenta A4.6 "
               "durata e C4.9 CV della durata."),
    _row(id="E0.8", macro="common", evidence="recorder-builtin",
         name="timestamp_end", human_label="Istante di fine dell'evento",
         type="timestamp_ms", hook="recorder-builtin",
         moment="post-event", cardinality="N=events",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field", unit="ms",
         usage="Con timestamp_start delimita lo span dell'evento. Serve al "
               "calcolo della durata effettiva (A2.4 planning latency, A4.6 "
               "durata run) e all'analisi di overlap/concorrenza fra eventi."),
    _row(id="E0.9", macro="common", evidence="recorder-builtin",
         name="duration_ms", human_label="Durata dell'evento",
         type="int", hook="recorder-builtin",
         moment="post-event", cardinality="N=events",
         lifecycle="derived-deterministic", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field", unit="ms",
         usage="Alimenta direttamente A2.4 (latenza pianificazione) quando "
               "l'evento è planning_span, e A4.6 (durata run) come aggregato. "
               "È derivato da timestamp_end - timestamp_start: nella tassonomia "
               "esemplifica la categoria derived-deterministic."),
    _row(id="E0.10", macro="common", evidence="recorder-builtin",
         name="agent_id", human_label="Agente che ha prodotto l'evento",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Chiave di ripartizione per-agente. Alimenta A3.5 fan-out per "
               "componente, A1.2 distribuzione decisioni per target, e "
               "l'aggregato per-agente in C1 (trajectory grouped by agent)."),
    _row(id="E0.11", macro="common", evidence="recorder-builtin",
         name="source_component", human_label="Componente sorgente",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Uno dei due estremi dell'arco negli handoff (A3): con "
               "target_component costituisce l'edge (source, target). Base "
               "per A3.1 conformance, A3.2 edge coverage, A3.4 bounces "
               "strutturali vs anti-pattern (via DECLARED_HUB_NODES)."),
    _row(id="E0.12", macro="common", evidence="recorder-builtin",
         name="target_component", human_label="Componente destinatario",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Con source_component costituisce l'arco del control flow. "
               "Per orchestrator_decision è l'agente scelto dal routing → "
               "alimenta A1.1 rule coverage, A1.2 target distribution e "
               "l'edge sequence usata da C4.2 edge signatures."),
    _row(id="E0.13", macro="common", evidence="recorder-builtin",
         name="tool_name", human_label="Nome del tool invocato",
         type="string", hook="recorder-builtin",
         moment="during-event", cardinality="N=events",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.field",
         usage="Presente in tool_call e tool_result. Alimenta A4.3 tool error "
               "rate (raggruppando per tool_name), la tool_signatures di "
               "C4.3 (sequenze tool per run) e la cattura dei postmortem "
               "correlati per il check3 di C3."),
]


# =========================================================================
# CONTROL FLOW · A1..A4
# =========================================================================
CF: list[dict[str, Any]] = [
    # ---------- A1: orchestrator_decision ----------
    _row(id="A1.d1", macro="control_flow", evidence="A1 · Decisioni orchestratore",
         name="metadata.reason", human_label="Motivo della decisione di routing",
         type="string", hook="orchestrator",
         moment="pre-event", cardinality="N=decisions",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Dalla ROUTING_RULES matched al momento della scelta.",
         usage="È il ponte fra osservato e dichiarato per A1.1 rule activation "
               "coverage: confrontato con la lista dei reason in ROUTING_RULES "
               "per contare quali regole sono state esercitate (attivate) e "
               "quali restano dead branches. Alimenta anche A1.2 distribuzione "
               "decisioni + entropia."),
    _row(id="A1.d2", macro="control_flow", evidence="A1 · Decisioni orchestratore",
         name="metadata.alternatives", human_label="Alternative disponibili al momento",
         type="list", hook="orchestrator",
         moment="pre-event", cardinality="N=decisions",
         lifecycle="snapshot", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Elenco regole vere al momento t (snapshot delle alternative).",
         usage="Alimenta A1.4 branching factor: il numero di alternative - 1 "
               "è il branching factor della decisione. Le 'forced decision' "
               "(alternative=1) sono conteggiate come decisioni strutturalmente "
               "vincolate (più facilmente certificabili)."),
    _row(id="A1.d3", macro="control_flow", evidence="A1 · Decisioni orchestratore",
         name="metadata.step", human_label="Numero d'ordine della decisione nella run",
         type="int", hook="orchestrator",
         moment="during-event", cardinality="N=decisions",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="count",
         usage="Con timestamp_start ordina cronologicamente le decisioni. "
               "Serve a A1.5 decisioni per run come conteggio finale (max step) "
               "e per ricostruire la sequenza corretta anche in caso di eventi "
               "concorrenti con timestamp uguali."),
    _row(id="A1.d4", macro="control_flow", evidence="A1 · Decisioni orchestratore",
         name="metadata.context_snapshot_keys",
         human_label="Chiavi di stato viste al momento della decisione",
         type="list", hook="orchestrator",
         moment="pre-event", cardinality="N=decisions",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Chiavi di stato valorizzate al momento della decisione.",
         usage="Costituisce la 'firma di contesto' per A1.3 routing determinism: "
               "l'orchestratore è considerato deterministico se, a parità di "
               "firma di contesto, decide sempre lo stesso target. È un proxy "
               "conservativo (dichiarato): usa le chiavi, non i valori."),

    # ---------- A2: planning_span + replanning ----------
    _row(id="A2.d1", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.plan", human_label="Piano di triage prodotto dal planner",
         type="list", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Piano generato dal LLM planner. Un-ripetibile bit-a-bit.",
         usage="Alimenta A2.3 plan-execution fitness/precision: i token del "
               "piano vengono matchati con le aree semantiche degli agenti "
               "effettivamente eseguiti (fitness = piano seguito, precision = "
               "no step extra). Alimenta anche A2.5 plan variability (distinct "
               "first steps) come proxy della varianza LLM a temp=0."),
    _row(id="A2.d2", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.n_steps", human_label="Numero di step del piano",
         type="int", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="count",
         notes="Derivato da len(plan); ricalcolabile dal plan salvato.",
         usage="Alimenta A2.1 plan length (min/max/mean/σ della lunghezza del "
               "piano) e A2.5 length_entropy_norm (varianza cross-run della "
               "lunghezza)."),
    _row(id="A2.d3", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.updated", human_label="Flag di piano rivisto",
         type="boolean", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Distingue il piano iniziale da un piano prodotto in seguito "
               "a replanning. Insieme al conteggio di eventi replanning "
               "alimenta A2.2 replanning rate."),
    _row(id="A2.d4", macro="control_flow", evidence="A2 · Pianificazione",
         name="duration_ms", human_label="Durata dello span di pianificazione",
         type="int", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.field", unit="ms",
         notes="Latenza dello span di pianificazione (dominata dal LLM).",
         usage="Alimenta A2.4 planning latency (min/max/mean/σ, p95) come "
               "misura di quanto tempo il planner impiega a produrre il piano. "
               "La sua alta varianza a temp=0 è un indicatore della "
               "stocasticità residua lato provider LLM."),
    _row(id="A2.d5", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_provider", human_label="Provider LLM effettivamente usato",
         type="categorical", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Dominio: groq | cerebras (per fallback multi-provider).",
         usage="Audit del multi-provider: consente di dichiarare, per ogni "
               "chiamata, se è avvenuta sul provider primario o sul fallback. "
               "Essenziale per la riproducibilità dell'esperimento "
               "(re-certifiability window)."),
    _row(id="A2.d6", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_model", human_label="Modello LLM canonico",
         type="string", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Nome canonico del modello effettivamente usato.",
         usage="Identità del modello per la re-certifiability window: se il "
               "provider aggiorna silenziosamente il modello, il valore "
               "cambia e le vecchie certificazioni vanno rieseguite."),
    _row(id="A2.d7", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_fingerprint",
         human_label="Impronta hash del prompt inviato",
         type="sha256", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="sha256(model, system, user, temperature). Audit di deduplica prompt.",
         usage="Chiave stabile per raggruppare chiamate LLM identiche: consente "
               "di verificare che, nelle N run dello stesso ticket, il prompt "
               "sia effettivamente lo stesso (controllo di stabilità del "
               "pipeline). Base per un eventuale drift detection lato provider."),
    _row(id="A2.d8", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_latency_ms", human_label="Latenza della chiamata LLM",
         type="int", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="ms",
         usage="Componente principale di A2.4 latency e A4.6 durata totale. "
               "La sua CV cross-run è un indicatore diretto del rumore lato "
               "provider (batch composition variabile)."),
    _row(id="A2.d9", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_prompt_tokens", human_label="Token di prompt consumati",
         type="int", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="tokens",
         usage="Accounting economico e vincolo rate-limit provider. Somma "
               "cross-run alimenta A4.d5 total_tokens per run; il monitoring "
               "in-run è la base per l'adaptive sleep del multi-provider client."),
    _row(id="A2.d10", macro="control_flow", evidence="A2 · Pianificazione",
         name="metadata.llm_completion_tokens", human_label="Token di risposta generati",
         type="int", hook="agent",
         moment="post-event", cardinality="1",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="tokens",
         usage="Alimenta lo stesso pipeline di prompt_tokens (accounting + "
               "rate-limit); un'alta varianza cross-run a temp=0 su questa "
               "grandezza è indicatore di risposte LLM di lunghezza diversa "
               "sullo stesso prompt (stocasticità residua)."),
    _row(id="A2.r1", macro="control_flow", evidence="A2 · Pianificazione · Replanning",
         name="metadata.old_plan", human_label="Piano precedente (prima del replan)",
         type="list", hook="agent",
         moment="post-event", cardinality="variable-bounded",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Piano precedente prima del replan. 0..k occorrenze per run.",
         usage="Consente il confronto old_plan → new_plan per capire cosa è "
               "cambiato: base per l'analisi di stabilità della pianificazione "
               "e per un eventuale detection di cicli di replan patologici."),
    _row(id="A2.r2", macro="control_flow", evidence="A2 · Pianificazione · Replanning",
         name="metadata.new_plan", human_label="Piano riformulato",
         type="list", hook="agent",
         moment="post-event", cardinality="variable-bounded",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Simmetrico a old_plan. La coppia (old_plan, new_plan) è "
               "l'evidenza puntuale del replan; il conteggio degli eventi "
               "replanning alimenta A2.2 replanning rate."),
    _row(id="A2.r3", macro="control_flow", evidence="A2 · Pianificazione · Replanning",
         name="metadata.reason", human_label="Motivo del replanning",
         type="text_free", hook="agent",
         moment="post-event", cardinality="variable-bounded",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Testo libero prodotto dall'agente: utile in analisi qualitativa "
               "per capire la tipologia di replan (nuova evidence, tool "
               "failure, ambiguità del piano iniziale). Non alimenta metriche "
               "quantitative, ma è materiale per case study nel paper."),

    # ---------- A3: handoff (E ricostruito da orchestrator_decision) ----------
    _row(id="A3.d1", macro="control_flow", evidence="A3 · Handoff",
         name="metadata.reason", human_label="Motivo dell'handoff",
         type="string", hook="orchestrator",
         moment="during-event", cardinality="N=handoffs",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Stesso ruolo del reason in A1 (viene dalla ROUTING_RULES). "
               "Contribuisce alla ricostruzione degli edge per A3.1 topology "
               "conformance e A3.4 bounces strutturali (via hub_nodes)."),
    _row(id="A3.d2", macro="control_flow", evidence="A3 · Handoff",
         name="metadata.context_summary", human_label="Riassunto contesto trasferito",
         type="text_free", hook="agent",
         moment="during-event", cardinality="N=handoffs",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Presente solo negli handoff espliciti (runtime attuale non li emette).",
         usage="Testo libero descrittivo del contesto passato tra agenti. "
               "Utile per audit qualitativo di cosa un agente vede quando "
               "riceve controllo. Non è emesso dal runtime attuale (hub-and-"
               "spoke con handoff derivati): campo predisposto per topologie "
               "peer-to-peer future."),
    _row(id="A3.d3", macro="control_flow", evidence="A3 · Handoff",
         name="metadata.payload_size", human_label="Dimensione payload trasferito",
         type="int", hook="agent",
         moment="during-event", cardinality="N=handoffs",
         lifecycle="snapshot", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="bytes",
         usage="Misura del volume di dati che attraversa il confine agente-"
               "agente. Utile per A3.3 densità del grafo pesata e per il "
               "monitoraggio del budget di contesto trasferito (rischio di "
               "context bloat in pipeline lunghe)."),

    # ---------- A4: path metrics (aggregati) + run_end ----------
    _row(id="A4.d1", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.outcome (run_end)", human_label="Esito finale della run",
         type="categorical",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="stable-in-run", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Dominio: completed | error | no_final_report.",
         usage="Alimenta A4.2 completion rate + IC Wilson 95%: probabilità "
               "che il sistema porti a termine il task. È la metrica gating "
               "del regime statistico su N run (Legay et al. 2010: statistical "
               "model checking)."),
    _row(id="A4.d2", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.classification (run_end)",
         human_label="Classificazione finale dell'incidente",
         type="categorical",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Materia prima per C4.4 (distribuzione classification cross-run + "
               "entropia), per C2 coverage state↔output, e per C3 check "
               "planner↔classifier. Il fatto che sia one-shot rende N grande "
               "essenziale per stimarne la distribuzione con IC."),
    _row(id="A4.d3", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.priority (run_end)", human_label="Priorità finale (P1..P4)",
         type="categorical",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Alimenta C4.5 (distribuzione priority cross-run) e C2 coverage. "
               "La stabilità di questo campo su N ripetizioni è indicatore "
               "di quanto il modello concorda con se stesso sulla severità."),
    _row(id="A4.d4", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.affected_service (run_end)",
         human_label="Servizio impattato deciso dal planner",
         type="categorical",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Alimenta C4.6 (distribuzione affected_service cross-run) e C3 "
               "check1 planner↔investigatori (il servizio deciso è stato "
               "effettivamente investigato?)."),
    _row(id="A4.d5", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.total_tokens (run_end)", human_label="Token totali usati nella run",
         type="int",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata", unit="tokens",
         usage="Somma dei token di tutte le chiamate LLM della run. Base per "
               "accounting economico e per proiettare il consumo di batch "
               "grandi (N=200-600 in prospettiva)."),
    _row(id="A4.d6", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="metadata.agent_history (run_end)",
         human_label="Sequenza agenti attivati (dedup)",
         type="list",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Materia prima per A4.4 trace variants: sequenze distinte + "
               "entropia normalizzata. Alimenta anche C4.1 signature nodi. Il "
               "numero di varianti distinte è un indicatore diretto della "
               "stabilità del routing."),
    _row(id="A4.d7", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="run_duration", human_label="Durata end-to-end della run",
         type="int", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-analogous",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="ms",
         notes="Derivato: max(ts_end) - min(ts_start) sulla run.",
         usage="Alimenta A4.6 durata (stats + p95) e C4.9 CV della durata "
               "cross-run: la sua CV alta a temp=0 è la manifestazione più "
               "diretta della stocasticità residua LLM."),
    _row(id="A4.d8", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="tool_call_count", human_label="Numero di chiamate a tool",
         type="int", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="count",
         usage="Denominatore di A4.3 tool error rate (errors/tool_calls). "
               "Utile anche come indicatore di efficienza: run che ne fanno "
               "molte di più della media suggeriscono un ReAct loop poco "
               "focalizzato."),
    _row(id="A4.d9", macro="control_flow", evidence="A4 · Metriche di percorso",
         name="error_count", human_label="Numero di errori nella run",
         type="int", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="count",
         usage="Numeratore di A4.3 tool error rate. In prospettiva alimenta "
               "una tassonomia degli errori (allineamento con Microsoft "
               "Failure Modes 2026: tool abuse, excessive agency, ...)."),
]


# =========================================================================
# DATA FLOW · B1..B4 (7 canali AgentLeak)
# =========================================================================
DF: list[dict[str, Any]] = [
    # ---------- B1-B3: campi che veicolano PII sui canali ----------
    _row(id="B.d1", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="payload_summary", human_label="Riassunto testuale dell'evento",
         type="text_free", hook="agent",
         moment="during-event", cardinality="N=events",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.field", pii="may-contain-V", unit="chars",
         notes="Riassunto human-readable dell'evento; scanned per PII detection.",
         usage="Fonte primaria della PII detection (B2 CLR): il PIIRedactor "
               "scansiona questo campo con VAULT_PATTERNS per rilevare "
               "categorie di V; se DATAFLOW_REDACTION_ENABLED, sostituisce in-"
               "place le categorie non ammesse dal canale prima della "
               "persistenza."),
    _row(id="B.d2", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="payload_redacted (ricorsivo)", human_label="Payload strutturato dell'evento",
         type="dict", hook="agent",
         moment="during-event", cardinality="N=events",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.payload_redacted",
         pii="may-contain-V",
         notes="Payload strutturato (dict/list annidati); redazione ricorsiva.",
         usage="Stesso ruolo di payload_summary ma su struttura ricorsiva: il "
               "PIIRedactor discende dict e list annidati per raggiungere ogni "
               "stringa foglia. Fondamentale perché la PII reale (reporter_email "
               "in tool_result) vive dentro dict annidati, non top-level."),
    _row(id="B.d3", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="metadata.pii_redaction_hits", human_label="Audit delle mascherature applicate",
         type="dict", hook="event_store",
         moment="during-event", cardinality="variable-bounded",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata", pii="audit-only", unit="count",
         notes="Conteggio delle categorie mascherate (audit trail della mitigation).",
         usage="Sorgente autoritativa post-mitigazione di B2 CLR: l'aggregator "
               "legge questo campo (invece di ri-scannare il testo, che è già "
               "mascherato) per contare le violazioni originarie e alimentare "
               "il blocco mitigation di B4. Chiude il ciclo detect→mitigate→"
               "re-verify in modo auditabile."),
    _row(id="B.d4", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="metadata.namespace (shared_memory)",
         human_label="Namespace della memoria condivisa (es. workspace)",
         type="string",
         hook="agent", moment="during-event", cardinality="variable-bounded",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Discrimina le regioni di shared memory (workspace, staging, "
               "cache). Il canale C5 aggrega tutti i namespace; se in futuro "
               "servisse una CLR per-namespace, questo campo è la chiave."),
    _row(id="B.d5", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="metadata.key (shared_memory)",
         human_label="Chiave scritta/letta nella memoria condivisa",
         type="string",
         hook="agent", moment="during-event", cardinality="variable-bounded",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Consente l'analisi del ciclo di vita dei dati nel workspace "
               "(scritture e letture per chiave). Base per audit di data-flow "
               "internal (chi ha scritto X, chi lo ha letto)."),
    _row(id="B.d6", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="metadata.success (tool_result)", human_label="Esito della chiamata a tool",
         type="boolean",
         hook="tool_adapter", moment="post-event", cardinality="variable-bounded",
         lifecycle="stable-in-run", reproducibility="re-collectable-analogous",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Alimenta A4.3 tool error rate: numeratore = success=false, "
               "denominatore = totale tool_result. Indicatore di robustezza "
               "degli adapter e dell'infrastruttura sottostante."),
    _row(id="B.d7", macro="data_flow", evidence="B1-B3 · Emissione canali + CLR/SLR",
         name="metadata.subject (inter_agent_msg)",
         human_label="Soggetto del messaggio inter-agente",
         type="string",
         hook="agent", moment="during-event", cardinality="variable-bounded",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Etichetta semantica del messaggio (es. 'classification_ready', "
               "'incident_snapshot'). Utile per analisi qualitativa del "
               "protocollo di comunicazione fra agenti; base per una futura "
               "conformance del protocollo di messaging."),

    # ---------- B4: Policy dichiarata + mitigation aggregata ----------
    _row(id="B4.d1", macro="data_flow", evidence="B4 · Policy (V, A, REDACTION)",
         name="VAULT_PATTERNS (V)", human_label="Vault privacy V (categorie di PII)",
         type="dict", hook="source_code",
         moment="end-of-batch", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", pii="schema",
         notes="Vocabolario privacy dichiarato ex-ante (regex per categoria).",
         usage="Vocabolario delle categorie di dato sensibile (email, phone, "
               "ip, ...). È lo scan target del PIIRedactor: ogni evento con "
               "channel viene scansionato per ogni regex del vault. La "
               "presenza del vault come artefatto ispezionabile è "
               "precondizione di ogni claim di data governance."),
    _row(id="B4.d2", macro="data_flow", evidence="B4 · Policy (V, A, REDACTION)",
         name="ALLOWED_SET_A[channel]",
         human_label="Insieme categorie ammesse per canale (A)",
         type="dict", hook="source_code",
         moment="end-of-batch", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", pii="schema",
         notes="Categorie ammesse per canale (base della metrica di leakage).",
         usage="Specifica dichiarata ex-ante di quali categorie di V sono "
               "ammesse su ciascun canale AgentLeak. Definisce operativamente "
               "cos'è un leak: una categoria di V rilevata su un canale che "
               "NON la ammette. Alimenta B2 CLR e B3 SLR."),
    _row(id="B4.d3", macro="data_flow", evidence="B4 · Policy (V, A, REDACTION)",
         name="REDACTION_POLICY (V - A)",
         human_label="Policy di mitigazione (categorie da mascherare per canale)",
         type="dict", hook="source_code",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", pii="schema",
         notes="Derivata deterministicamente: unica sorgente di verità detect+mitigate.",
         usage="Guida operativa del PIIRedactor. È derivata deterministicamente "
               "da V e A: cambia in un solo posto, detection e mitigation "
               "restano coerenti per costruzione (evita il rischio di "
               "divergenza silenziosa tra le due policy)."),
    _row(id="B4.d4", macro="data_flow", evidence="B4 · Policy (V, A, REDACTION)",
         name="mitigation.per_channel.redactions_by_category",
         human_label="Contatore mascherature applicate per canale/categoria",
         type="dict",
         hook="aggregator", moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="count",
         notes="Contatore delle mascherature effettivamente applicate per canale.",
         usage="Prova empirica del lavoro della mitigation. Un batch con "
               "CLR=0 ma redactions_by_category > 0 dice: il framework HA "
               "trovato violazioni e le HA mascherate. Un batch con CLR=0 e "
               "redactions vuote dice: non c'era nulla da mascherare."),
    _row(id="B4.d5", macro="data_flow", evidence="B4 · Policy (V, A, REDACTION)",
         name="mitigation.events_with_redaction",
         human_label="Eventi toccati dalla redazione",
         type="int",
         hook="aggregator", moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="count",
         usage="Cardinality dell'intervento di mitigazione. Insieme al totale "
               "degli eventi del canale, dà la 'redaction rate' del canale: "
               "quanto spesso, in questo esperimento, il canale ha portato "
               "PII fuori policy."),
]


# =========================================================================
# BEHAVIORAL · C2, C3, C4
# =========================================================================
BH: list[dict[str, Any]] = [
    # ---------- C2: state_snapshot + final_output ----------
    _row(id="C2.d1", macro="behavioral", evidence="C2 · Coerenza state ↔ output",
         name="metadata.state (state_snapshot)",
         human_label="Stato consolidato di fine run",
         type="dict",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="stable-in-run", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata", pii="may-contain-V",
         notes="Stato consolidato del sistema (classification, priority, service, ecc.).",
         usage="Termine sinistro del confronto C2 state↔output: contiene i "
               "campi chiave (classification, priority, affected_service) da "
               "cercare nell'output finale. Alimenta il verdetto tri-livello "
               "C2 (coherent/acceptable/unacceptable) via classify_c2."),
    _row(id="C2.d2", macro="behavioral", evidence="C2 · Coerenza state ↔ output",
         name="metadata.label (state_snapshot)", human_label="Etichetta dello snapshot",
         type="string",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="stable-in-run", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         usage="Discrimina snapshot multipli in una singola run (es. "
               "'consolidated', 'draft'). Attualmente c'è un solo snapshot "
               "per run; il campo è predisposto per pipeline multi-fase."),
    _row(id="C2.d3", macro="behavioral", evidence="C2 · Coerenza state ↔ output",
         name="payload_summary (final_output)",
         human_label="Testo dell'output finale utente",
         type="text_free",
         hook="agent", moment="end-of-run", cardinality="1",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.field",
         pii="may-contain-V", unit="chars",
         notes="Testo prosaico prodotto dal summarizer LLM; base per coverage.",
         usage="Termine destro del confronto C2 state↔output: si verifica che "
               "i campi chiave dello stato appaiano lessicalmente nel testo "
               "(proxy dichiarato di groundedness RAGAS-like). Alimenta anche "
               "C4.8 CV output length (misura di stabilità della verbosità)."),

    # ---------- C3: decision_point + tool_result postmortem ----------
    _row(id="C3.d1", macro="behavioral", evidence="C3 · Sequenza decisioni (intention↔behavior)",
         name="metadata.label", human_label="Etichetta semantica del decision_point",
         type="categorical", hook="agent",
         moment="during-event", cardinality="variable-bounded",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Dominio: affected_service | log_depth | critical_component | classification | …",
         usage="Discriminante che consente al check di C3 di sapere cosa è "
               "stato deciso (es. il label 'affected_service' identifica la "
               "decisione del planner sul servizio impattato, da matchare con "
               "quello effettivamente investigato)."),
    _row(id="C3.d2", macro="behavioral", evidence="C3 · Sequenza decisioni (intention↔behavior)",
         name="metadata.choice", human_label="Scelta effettuata dall'agente",
         type="string", hook="agent",
         moment="during-event", cardinality="variable-bounded",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.metadata",
         notes="Lifecycle misto: one-shot se LLM (planner/classifier), derived se deterministico.",
         usage="Contenuto della decisione. Nei check pairwise C3.d2 è "
               "confrontato: (check1) con il servizio investigato, (check2) "
               "con il primary_symptom via C3_SYMPTOM_TO_CLASSIFICATION, "
               "(check3) con i tag dei postmortem via "
               "C3_CLASSIFICATION_TO_PM_TAGS. È il dato più "
               "certificazione-critical dell'intera macro Behavioral."),
    _row(id="C3.d3", macro="behavioral", evidence="C3 · Sequenza decisioni (intention↔behavior)",
         name="payload_redacted.inputs",
         human_label="Input al momento della decisione",
         type="dict", hook="agent",
         moment="during-event", cardinality="variable-bounded",
         lifecycle="one-shot", reproducibility="one-shot",
         cadence="event-triggered", persistence="jsonl.event.payload_redacted",
         pii="may-contain-V",
         usage="Contesto su cui l'agente ha basato la decisione. Nel check2 "
               "(planner↔classifier) contiene il primary_symptom estratto dal "
               "planner, che viene tokenizzato e mappato via "
               "C3_SYMPTOM_TO_CLASSIFICATION."),
    _row(id="C3.d4", macro="behavioral", evidence="C3 · Sequenza decisioni (intention↔behavior)",
         name="payload_redacted.result[i].id (query_postmortems)",
         human_label="ID postmortem selezionato dal retriever",
         type="string",
         hook="tool_adapter", moment="post-event", cardinality="variable-bounded",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.payload_redacted",
         usage="Cardinality dei postmortem selezionati. Alimenta C4.10 "
               "postmortem_sets (Jaccard medio pairwise cross-run) come "
               "misura di stabilità del retriever."),
    _row(id="C3.d5", macro="behavioral", evidence="C3 · Sequenza decisioni (intention↔behavior)",
         name="payload_redacted.result[i].tags (query_postmortems)",
         human_label="Tag semantici del postmortem",
         type="list",
         hook="tool_adapter", moment="post-event", cardinality="variable-bounded",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="event-triggered", persistence="jsonl.event.payload_redacted",
         usage="Ingresso principale del check3 (classifier↔postmortem): i tag "
               "sono matchati (substring bidirezionale) con expected_tags della "
               "classification scelta. Determinano se la decisione del "
               "classifier è coerente con l'evidenza recuperata."),

    # ---------- C4: aggregati cross-run multi-asse ----------
    _row(id="C4.d1", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="node_signatures", human_label="Firme nodi (sequenza dedup di agenti)",
         type="dict", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.1: distribuzione + entropia normalizzata delle "
               "firme nodi. H=0 significa routing perfettamente stabile; H>0 "
               "significa che le run visitano set di agenti diversi. In "
               "topologia hub-and-spoke a temp=0 attesa H≈0."),
    _row(id="C4.d2", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="edge_signatures",
         human_label="Firme edge (sequenza ordinata degli handoff)",
         type="dict", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.2: granularità più fine di C4.1 (l'ordine conta, "
               "non solo l'insieme). Detecta swap di ordine invisibili alla "
               "firma nodi."),
    _row(id="C4.d3", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="tool_signatures",
         human_label="Firme tool (sequenza ordinata delle chiamate a tool)",
         type="dict", hook="aggregator",
         moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.3: granularità ancora più fine, indipendente dal "
               "routing (due run possono avere la stessa sequenza di agenti "
               "ma tool call diverse, es. min_level='WARN' vs 'ERROR')."),
    _row(id="C4.d4", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="final_classification (Counter)",
         human_label="Distribuzione classification cross-run",
         type="dict",
         hook="aggregator", moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.4: distribuzione + entropia della classification "
               "finale su N run. È il segnale principale di 'varianza "
               "semantica' del sistema anche a temp=0 (es. 19× "
               "capacity_saturation + 1× regression_after_deploy)."),
    _row(id="C4.d5", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="final_priority (Counter)",
         human_label="Distribuzione priority cross-run",
         type="dict",
         hook="aggregator", moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.5: analogo di C4.4 sul campo priority. Stabilità "
               "di P1..P4 indica accordo del modello con se stesso sulla "
               "severità del caso."),
    _row(id="C4.d6", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="final_affected_service (Counter)",
         human_label="Distribuzione servizio impattato cross-run",
         type="dict",
         hook="aggregator", moment="end-of-batch", cardinality="1",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.6: stabilità della decisione del planner sul "
               "servizio impattato. È il pendant, cross-run, di ciò che C3 "
               "check1 verifica in-run (coerenza planner↔investigatori)."),
    _row(id="C4.d7", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="step_counts (list)", human_label="Numero di step per run",
         type="list",
         hook="aggregator", moment="end-of-batch", cardinality="N per batch",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="count",
         usage="Alimenta C4.7: CV del numero di step per run. In pipeline "
               "hub-and-spoke deterministica atteso CV=0. Un CV>0 indica "
               "biforcazioni reali (replan, retry)."),
    _row(id="C4.d8", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="output_lengths (list)", human_label="Lunghezze del final_output per run",
         type="list",
         hook="aggregator", moment="end-of-batch", cardinality="N per batch",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="chars",
         usage="Alimenta C4.8: CV della lunghezza dell'output finale. Sul "
               "batch da 20 osservato CV=0.256 (min 679, max 1904 chars): "
               "manifestazione empirica diretta della stocasticità LLM "
               "residua a temp=0."),
    _row(id="C4.d9", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="durations_ms (list)", human_label="Durate totali per run",
         type="list",
         hook="aggregator", moment="end-of-batch", cardinality="N per batch",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json", unit="ms",
         usage="Alimenta C4.9: CV della durata end-to-end. Osservato CV=0.90 "
               "(min 4.6s, max 59.1s): la varianza è dominata dalla latenza "
               "LLM lato provider (batch composition)."),
    _row(id="C4.d10", macro="behavioral", evidence="C4 · Stabilità cross-run (multi-asse)",
         name="postmortem_sets (list)",
         human_label="Insieme di postmortem selezionati per run",
         type="list",
         hook="aggregator", moment="end-of-batch", cardinality="N per batch",
         lifecycle="derived-deterministic", reproducibility="re-collectable-identical",
         cadence="on-demand", persistence="aggregate/metrics.json",
         usage="Alimenta C4.10: Jaccard medio pairwise sull'insieme di ID "
               "postmortem selezionati. J=1.0 significa che il retriever "
               "sceglie sempre lo stesso set (stabile); J<1.0 mostra varianza "
               "nel retrieval."),
]


# =========================================================================
# Tassonomia completa + summary + blind spot.
# =========================================================================
DATA_TAXONOMY: list[dict[str, Any]] = COMMON + CF + DF + BH


def _summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter
    macros = Counter(e["macro"] for e in entries)
    life = Counter(e["lifecycle"] for e in entries)
    reproducibility = Counter(e["reproducibility"] for e in entries)
    cadence = Counter(e["cadence"] for e in entries)
    hooks = Counter(e["hook"] for e in entries)
    # Buchi: dimensioni del dominio NON osservate.
    unused_lifecycle = [v for v in DOMAINS["lifecycle"] if life.get(v, 0) == 0]
    unused_cadence = [v for v in DOMAINS["cadence"] if cadence.get(v, 0) == 0]
    return {
        "total": len(entries),
        "by_macro": dict(macros),
        "by_lifecycle": dict(life),
        "by_reproducibility": dict(reproducibility),
        "by_cadence": dict(cadence),
        "by_hook": dict(hooks),
        "gaps": {
            "unused_lifecycle": unused_lifecycle,
            "unused_cadence": unused_cadence,
        },
    }


TAXONOMY_SUMMARY: dict[str, Any] = _summarize(DATA_TAXONOMY)


# Blind spot dichiarati (mappati sulla matrice — vedi PAPER_TAXONOMY.md § 8).
BLIND_SPOTS: list[dict[str, str]] = [
    {"name": "Prompt post-templating",
     "detail": "Osserviamo il fingerprint del prompt inviato al provider, non "
               "quello effettivamente processato dopo il template interno."},
    {"name": "Batch composition provider",
     "detail": "Causa nota della varianza residua a temp=0. Non osservabile "
               "direttamente lato client."},
    {"name": "Aggiornamenti silenziosi del modello",
     "detail": "Rilevabili solo indirettamente via divergenza di fingerprint "
               "in cache-hit verificati (funzionalità rimossa)."},
    {"name": "Token remaining volatile",
     "detail": "Leggibile dagli header HTTP, usato per adaptive sleep, ma NON "
               "persistito negli eventi. Candidato per una sonda nuova."},
    {"name": "Quasi-identifier PII",
     "detail": "Detection su V per-categoria; non cattura combinazioni di "
               "attributi non-sensibili che identificano un individuo."},
    {"name": "Emergenza cross-run",
     "detail": "Comportamenti visibili solo a N grande; limite del regime "
               "statistico, non del cosa raccogliamo."},
    {"name": "Freshness contesto (decaying data)",
     "detail": "Nessun dato del prototipo modella lifecycle 'decaying'. "
               "Rilevante in sistemi RAG-based."},
    {"name": "Sliding-window aggregates",
     "detail": "Nessuna metrica del prototipo ha cadenza 'sliding-window'. "
               "Buco principale della raccolta attuale."},
]
