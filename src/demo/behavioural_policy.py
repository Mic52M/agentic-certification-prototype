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
