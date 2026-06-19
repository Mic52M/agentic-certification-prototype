"""Configuration 2 — multi-agent with a centralized orchestrator.

Graph shape (a hub-and-spoke; the orchestrator is the only router):

    START -> orchestrator -> intent_classifier -> orchestrator
                          -> retriever          -> orchestrator
                          -> responder          -> orchestrator
                          -> END

Specialists never call each other. They return to the orchestrator, which
re-evaluates the deterministic routing rules against the shared state.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..llm_client import LLMClient
from ..logging_utils import TraceLogger
from ..state import MultiAgentState
from .agents import build_specialist_nodes
from .orchestrator import build_orchestrator_node


def build_multi_agent_graph(llm: LLMClient, logger: TraceLogger):
    orchestrator_node = build_orchestrator_node(logger)
    specialists = build_specialist_nodes(llm, logger)

    graph = StateGraph(MultiAgentState)
    graph.add_node("orchestrator", orchestrator_node)
    for name, node in specialists.items():
        graph.add_node(name, node)

    graph.add_edge(START, "orchestrator")
    # The orchestrator already wrote next_node into the state; route on it.
    graph.add_conditional_edges(
        "orchestrator",
        lambda s: s.next_node,
        {
            "intent_classifier": "intent_classifier",
            "retriever": "retriever",
            "responder": "responder",
            END: END,
        },
    )
    # Every specialist hands control back to the orchestrator.
    for name in specialists:
        graph.add_edge(name, "orchestrator")

    return graph.compile()
