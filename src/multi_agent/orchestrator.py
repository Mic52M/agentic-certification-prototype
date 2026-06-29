"""Orchestratore deterministico, basato su regole, per la configurazione multi-agente.

L'instradamento non è guidato da un LLM: è una lista ordinata e dichiarativa di
regole nella forma (condizione, nodo_successivo, motivo). Il flusso di controllo
tra gli agenti è quindi ispezionabile e riproducibile, e può essere analizzato
indipendentemente dal comportamento (non-deterministico) dei singoli agenti.
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import END

from ..logging_utils import TraceLogger
from ..state import MultiAgentState

# Regole di instradamento: lista ordinata di (predicato, nodo_successivo, motivo).
# Vengono valutate dall'alto verso il basso e vince la prima con predicato vero
# ("first match wins"). L'intera politica di routing è contenuta qui:
#   1) intent non ancora classificato        -> intent_classifier
#   2) contesto (ticket + KB) non recuperato  -> retriever
#   3) risposta finale mancante               -> responder
#   4) caso di default (tutto completato)     -> END
ROUTING_RULES: list[tuple[Callable[[MultiAgentState], bool], str, str]] = [
    (lambda s: s.current_intent is None,
     "intent_classifier",
     "intent non ancora classificato"),
    (lambda s: not s.retrieval_done,
     "retriever",
     "contesto (ticket + KB) non ancora recuperato"),
    (lambda s: s.final_answer is None,
     "responder",
     "contesto pronto, manca la risposta finale"),
    # Predicato sempre vero: ramo di default, raggiunto quando tutte le fasi
    # precedenti sono concluse.
    (lambda s: True,
     END,
     "risposta finale prodotta: terminazione"),
]


def decide_next(state: MultiAgentState) -> tuple[str, str]:
    """Valuta le regole nell'ordine e restituisce (nodo_successivo, motivo).

    Funzione pura e deterministica: dipende solo dallo stato, senza effetti
    collaterali, e per lo stesso stato restituisce sempre lo stesso risultato.
    """
    for predicate, next_node, reason in ROUTING_RULES:
        if predicate(state):
            return next_node, reason
    # Rete di sicurezza: l'ultima regola ha predicato sempre vero, quindi questo
    # ramo non dovrebbe essere raggiunto; garantisce comunque la terminazione.
    return END, "fallback"


def build_orchestrator_node(logger: TraceLogger):
    # Factory: inietta il logger nel nodo senza ricorrere a variabili globali.
    def orchestrator_node(state: MultiAgentState) -> dict:
        # Contatore dei passi dell'orchestratore (solo per la tracciabilità).
        iteration = state.iteration + 1

        # Applica le regole allo stato corrente.
        next_node, reason = decide_next(state)

        # Campi dello stato valorizzati al momento della decisione: documenta
        # su quali informazioni si è basato l'instradamento.
        snapshot_keys = [k for k, v in state.model_dump().items()
                         if v not in (None, [], "", False)]

        # Traccia la decisione (nodo scelto + motivo + snapshot) e il
        # conseguente passaggio di controllo verso il nodo scelto.
        logger.orchestrator_decision(iteration, next_node, reason, snapshot_keys)
        logger.handoff("orchestrator", str(next_node), iteration, "instradamento")

        # Scrive nello stato il prossimo nodo: è l'arco condizionale del grafo a
        # leggerlo e instradare. L'orchestratore decide, il grafo esegue.
        return {"next_node": next_node, "iteration": iteration}

    return orchestrator_node
