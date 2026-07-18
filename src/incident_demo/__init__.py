"""Incident triage — use case ricco per la demo osservativa.

Ticket di partenza: analisi di un incident applicativo con sintomi multipli;
il sistema deve raccogliere dati da più fonti (log, metriche, postmortem),
fare triage, classificare, produrre un riepilogo e delle azioni consigliate.

Fornisce a tutte e tre le macro-dimensioni un substrato ricco di eventi:
- control flow: pianificazione, branching orchestratore, handoff multipli;
- data flow: input/output tool, messaggi inter-agente, memoria condivisa,
  artefatto finale;
- comportamentale: traiettoria multi-step, sequenza di decision point,
  stato consolidato confrontabile con l'output.
"""
