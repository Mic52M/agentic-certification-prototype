"""Stato condiviso del sistema di incident triage.

Include un `SharedWorkspace` (dizionario tipizzato) che gli agenti usano come
memoria condivisa: ogni scrittura/lettura è un evento su canale C5 emesso dal
Recorder chi effettua l'operazione. Questo espone concretamente il canale
'shared memory' del framework AgentLeak.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SharedWorkspace(BaseModel):
    """Memoria condivisa strutturata del ticket (evidenze accumulate)."""
    incident_snapshot: dict[str, Any] | None = None
    triage_plan: list[str] = Field(default_factory=list)
    findings_logs: list[str] = Field(default_factory=list)
    findings_metrics: dict[str, Any] = Field(default_factory=dict)
    related_postmortems: list[dict] = Field(default_factory=list)
    triage_notes: list[str] = Field(default_factory=list)
    hypothesis_ranked: list[dict] = Field(default_factory=list)


class IncidentState(BaseModel):
    """Stato del grafo LangGraph del use case incident triage."""
    # input utente
    user_message: str
    incident_id: str

    # shared workspace (C5)
    workspace: SharedWorkspace = Field(default_factory=SharedWorkspace)

    # bookkeeping di orchestrazione
    next_node: str | None = None
    iteration: int = 0
    agent_history: list[str] = Field(default_factory=list)

    # fase corrente (per l'orchestratore rule-based)
    planning_done: bool = False
    investigation_done: bool = False
    triage_done: bool = False
    classification_done: bool = False

    # stato consolidato
    classification: str | None = None      # es. "network_partition" / "capacity_saturation" / "regression_after_deploy" / "unclassified"
    priority: str | None = None            # "P1" | "P2" | "P3" | "P4"
    affected_service: str | None = None
    confidence: str | None = None          # "low" | "medium" | "high"
    recommended_actions: list[str] = Field(default_factory=list)

    # output finale
    final_report: str | None = None

    # metriche
    total_tokens: int = 0
