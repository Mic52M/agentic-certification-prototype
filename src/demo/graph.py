"""Grafo LangGraph per l'incident triage multi-agente.

Topologia hub-and-spoke: l'orchestratore è l'unico router, tutti gli agenti
tornano a lui. La routing è deterministica e rule-based (orchestrator.py).
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..instrumentation import Recorder
from ..llm_client import LLMClient
from .agents import (
    build_classifier_node,
    build_log_investigator_node,
    build_metrics_analyst_node,
    build_planner_node,
    build_postmortem_retriever_node,
    build_reader_node,
    build_summarizer_node,
)
from .orchestrator import build_orchestrator_node
from .state import IncidentState


NODE_NAMES = (
    "reader",
    "planner",
    "log_investigator",
    "metrics_analyst",
    "postmortem_retriever",
    "classifier",
    "summarizer",
)


def build_incident_graph(llm: LLMClient, recorder: Recorder):
    orchestrator = build_orchestrator_node(recorder)
    nodes = {
        "reader":               build_reader_node(llm, recorder),
        "planner":              build_planner_node(llm, recorder),
        "log_investigator":     build_log_investigator_node(llm, recorder),
        "metrics_analyst":      build_metrics_analyst_node(llm, recorder),
        "postmortem_retriever": build_postmortem_retriever_node(llm, recorder),
        "classifier":           build_classifier_node(llm, recorder),
        "summarizer":           build_summarizer_node(llm, recorder),
    }

    graph = StateGraph(IncidentState)
    graph.add_node("orchestrator", orchestrator)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        lambda s: s.next_node,
        {**{name: name for name in nodes}, END: END},
    )
    for name in nodes:
        graph.add_edge(name, "orchestrator")

    return graph.compile()
