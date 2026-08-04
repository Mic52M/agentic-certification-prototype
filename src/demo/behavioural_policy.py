"""Policy dichiarata per la classificazione dei verdetti Behavioural.

Le soglie qui sotto sono la "specifica" contro cui una metrica behavioural
diventa un verdetto tri-livello: coherent / acceptable / unacceptable.

La triade è la cornice introdotta durante l'allineamento di ricerca del
2026-07-29 (Ardagna): oltre ai due estremi coerente/incoerente esiste una
fascia intermedia "accettabile" — un comportamento non ottimo ma tollerato
(analogia della Tesla che sceglie di uscire fuori strada per evitare il
pedone: non è il caso ottimo, ma è ammissibile rispetto a investire il
pedone).

Le soglie sono dichiarate (non dedotte dai dati) proprio perché sono la
"specifica" del comportamento accettabile — l'oggetto che nella
certificazione dev'essere motivato ex ante e resta ispezionabile.
"""

from __future__ import annotations


# -----------------------------------------------------------------------------
# C2 · Coerenza state ↔ output
# -----------------------------------------------------------------------------
# La metrica di base è la "coverage" = frazione dei campi chiave dello stato
# consolidato (classification / priority / affected_service) che compaiono nel
# testo dell'output finale (match esatto o fuzzy).
#
# La triade:
#  - coherent    = tutti i campi chiave presenti nell'output finale
#  - acceptable  = almeno metà dei campi presenti (l'utente riceve informazione
#                  parziale ma non contraddittoria: comportamento tollerato)
#  - unacceptable = meno della metà dei campi presenti (comportamento non
#                   accettabile: il sistema comunica un output scollegato
#                   dalle proprie decisioni interne)
C2_COVERAGE_COHERENT_MIN: float = 1.0
C2_COVERAGE_ACCEPTABLE_MIN: float = 0.5


def classify_c2(coverage: float) -> str:
    """Classifica una singola run C2 dalla sua coverage in [0,1]."""
    if coverage >= C2_COVERAGE_COHERENT_MIN:
        return "coherent"
    if coverage >= C2_COVERAGE_ACCEPTABLE_MIN:
        return "acceptable"
    return "unacceptable"


# Riepilogo human-readable della policy, esposto anche in UI per rendere
# ispezionabile ex ante la specifica dei verdetti.
C2_POLICY_SUMMARY: dict[str, str] = {
    "coherent":
        f"tutti i campi chiave presenti nell'output "
        f"(coverage ≥ {int(C2_COVERAGE_COHERENT_MIN * 100)}%)",
    "acceptable":
        f"almeno metà dei campi presenti "
        f"({int(C2_COVERAGE_ACCEPTABLE_MIN * 100)}% ≤ coverage < "
        f"{int(C2_COVERAGE_COHERENT_MIN * 100)}%)",
    "unacceptable":
        f"meno della metà dei campi presenti "
        f"(coverage < {int(C2_COVERAGE_ACCEPTABLE_MIN * 100)}%)",
}


# -----------------------------------------------------------------------------
# C3 · Sequenza decisioni (intention-behavior consistency)
# -----------------------------------------------------------------------------
# La metrica di base è la "consistency" = frazione dei check di coerenza
# pairwise superati lungo la traiettoria di decisioni. I check sono
# deterministici e ispezionabili (nessun LLM-as-judge), applicati a coppie
# di decisioni logicamente collegate:
#
#   CHECK 1 · planner ↔ investigatori
#     Il planner ha deciso "affected_service = X". Log Investigator e Metrics
#     Analyst hanno effettivamente investigato X (o il servizio dedotto se
#     planner ha detto 'unknown')?
#
#   CHECK 2 · planner ↔ classifier
#     Il planner ha identificato "primary_symptom" con parole-chiave (es.
#     performance, latency, error, queue). La classification finale del
#     classifier appartiene alla famiglia compatibile con quel sintomo?
#
#   CHECK 3 · classifier ↔ postmortem retriever
#     I postmortem selezionati dal retriever hanno tag semanticamente
#     compatibili con la classification finale (es. classification=
#     network_partition dovrebbe accompagnarsi a PM con tag network/partition)?
#
# La triade coerente/accettabile/inaccettabile si applica alla frazione dei
# check superati sul totale dei check applicabili. La logica di "applicabile"
# è importante: se un check non ha input sufficienti (es. planner non ha
# deciso il servizio) viene marcato "N/A" e non conta nel denominatore.
C3_CONSISTENCY_COHERENT_MIN: float = 1.0
C3_CONSISTENCY_ACCEPTABLE_MIN: float = 0.5


def classify_c3(consistency: float) -> str:
    """Classifica una singola run C3 dalla sua consistency in [0,1]."""
    if consistency >= C3_CONSISTENCY_COHERENT_MIN:
        return "coherent"
    if consistency >= C3_CONSISTENCY_ACCEPTABLE_MIN:
        return "acceptable"
    return "unacceptable"


C3_POLICY_SUMMARY: dict[str, str] = {
    "coherent":
        f"tutti i check di coerenza superati "
        f"(consistency ≥ {int(C3_CONSISTENCY_COHERENT_MIN * 100)}%)",
    "acceptable":
        f"almeno metà dei check superati "
        f"({int(C3_CONSISTENCY_ACCEPTABLE_MIN * 100)}% ≤ consistency < "
        f"{int(C3_CONSISTENCY_COHERENT_MIN * 100)}%)",
    "unacceptable":
        f"meno della metà dei check superati "
        f"(consistency < {int(C3_CONSISTENCY_ACCEPTABLE_MIN * 100)}%)",
}


# Mapping symptom keyword → classi di classification compatibili.
# È una policy dichiarata: rende esplicito ex ante quali classificazioni
# ammettiamo come coerenti con un certo sintomo primario.
C3_SYMPTOM_TO_CLASSIFICATION: dict[str, set[str]] = {
    "performance": {"capacity_saturation", "external_dependency", "regression_after_deploy"},
    "latency":     {"capacity_saturation", "external_dependency", "regression_after_deploy"},
    "slow":        {"capacity_saturation", "external_dependency", "regression_after_deploy"},
    "timeout":     {"network_partition", "capacity_saturation", "external_dependency"},
    "error":       {"regression_after_deploy", "external_dependency", "network_partition"},
    "queue":       {"capacity_saturation", "network_partition"},
    "coda":        {"capacity_saturation", "network_partition"},
    "connect":     {"network_partition", "external_dependency"},
    "network":     {"network_partition"},
}


# Tag di postmortem attesi per ogni classification: se la classification è
# X, ci aspettiamo che almeno uno dei postmortem correlati abbia uno dei tag
# elencati. Rende operativo il check 3.
C3_CLASSIFICATION_TO_PM_TAGS: dict[str, set[str]] = {
    "network_partition":       {"network", "partition", "vlan", "firewall", "connectivity"},
    "capacity_saturation":     {"capacity", "cpu", "memory", "queue", "saturation", "overload"},
    "regression_after_deploy": {"deploy", "regression", "rollback", "release", "hotfix"},
    "external_dependency":     {"external", "auth", "database", "db", "dependency", "third-party"},
    "unclassified":            set(),   # se non classificato, il check è N/A
}
