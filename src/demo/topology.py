"""Topologia e regole DICHIARATE del sistema.

Questo modulo rende esplicito il "modello atteso" del control flow, cioè ciò
che l'architettura *dichiara* di poter fare. Serve come riferimento per le
metriche di conformance: il comportamento osservato a runtime va confrontato
con questa dichiarazione.

È l'analogo, nel nostro sistema, del "process model" contro cui si fa
conformance checking nel process mining: il grafo di esecuzione osservato
deve essere un sottografo di quello dichiarato (role adherence).
"""

from __future__ import annotations

from .graph import NODE_NAMES
from .orchestrator import ROUTING_RULES

# Nodi ammessi (esclusi orchestrator e terminatore).
DECLARED_AGENTS: tuple[str, ...] = NODE_NAMES

# Topologia hub-and-spoke dichiarata: l'orchestratore può instradare verso
# ciascun agente e verso END; ogni agente torna all'orchestratore.
DECLARED_EDGES: list[tuple[str, str]] = (
    [("orchestrator", n) for n in DECLARED_AGENTS]
    + [("orchestrator", "__end__")]
    + [(n, "orchestrator") for n in DECLARED_AGENTS]
)

# Regole di routing dichiarate, nella forma (indice, target, motivo).
# L'indice è la posizione nella lista ordinata: identifica la regola in modo
# stabile anche se due regole condividono lo stesso target.
DECLARED_RULES: list[dict[str, str | int]] = [
    {"index": i, "target": str(target), "reason": reason}
    for i, (_pred, target, reason) in enumerate(ROUTING_RULES)
]


def declared_spec() -> dict:
    """Spec dichiarata, passata all'Aggregator per le metriche di conformance."""
    return {
        "agents": list(DECLARED_AGENTS),
        "edges": [list(e) for e in DECLARED_EDGES],
        "rules": DECLARED_RULES,
        # numero di nodi del grafo dichiarato (agenti + orchestrator + end)
        "n_nodes": len(DECLARED_AGENTS) + 2,
    }
