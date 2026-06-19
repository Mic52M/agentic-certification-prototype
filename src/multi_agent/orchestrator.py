"""Deterministic, rule-based orchestrator for configuration 2.

The routing is NOT LLM-driven. The rules below are a declarative, ordered list
of (condition, next_node, reason). This is a deliberate certification choice:
the control flow between agents is fully inspectable and reproducible, so it can
be reasoned about independently of model behavior.
"""

from __future__ import annotations

from collections.abc import Callable

from langgraph.graph import END

from ..logging_utils import TraceLogger
from ..state import MultiAgentState

# Ordered rules. First matching predicate wins. Each is plain data + a lambda,
# so the whole routing policy can be read top-to-bottom.
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
    (lambda s: True,
     END,
     "risposta finale prodotta: terminazione"),
]


def decide_next(state: MultiAgentState) -> tuple[str, str]:
    """Evaluate the rules in order; return (next_node, reason)."""
    for predicate, next_node, reason in ROUTING_RULES:
        if predicate(state):
            return next_node, reason
    return END, "fallback"


def build_orchestrator_node(logger: TraceLogger):
    def orchestrator_node(state: MultiAgentState) -> dict:
        iteration = state.iteration + 1
        next_node, reason = decide_next(state)
        snapshot_keys = [k for k, v in state.model_dump().items()
                         if v not in (None, [], "", False)]
        logger.orchestrator_decision(iteration, next_node, reason, snapshot_keys)
        return {"next_node": next_node, "iteration": iteration}

    return orchestrator_node
