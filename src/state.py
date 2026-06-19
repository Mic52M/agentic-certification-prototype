"""Pydantic state schemas for both configurations.

The shared state is the certification surface: every field here is something a
future certification scheme can read or constrain. We use Pydantic models (not
bare dicts) precisely so that each mutation is typed and inspectable.
LangGraph accepts a Pydantic BaseModel as a graph state schema; nodes return a
dict of the fields they changed.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReActStep(BaseModel):
    """One Thought / Action / Observation triple in the ReAct loop."""

    iteration: int
    thought: str
    action_tool: str
    action_args: dict[str, Any] = Field(default_factory=dict)
    observation: Any = None


class SingleAgentState(BaseModel):
    """State for configuration 1 (single agent, internal ReAct loop)."""

    task: str
    iteration: int = 0
    # The pending action the agent decided on this turn (consumed by tool node).
    pending_tool: str | None = None
    pending_args: dict[str, Any] = Field(default_factory=dict)
    # Observation produced by the last tool call, fed back next turn.
    last_observation: Any = None
    history: list[ReActStep] = Field(default_factory=list)
    final_answer: str | None = None
    total_tokens: int = 0


class MultiAgentState(BaseModel):
    """Shared state for configuration 2. The ONLY channel between agents.

    No agent talks to another directly; they read and write these fields and
    the deterministic orchestrator routes based on their values.
    """

    user_input: str
    task_ticket_id: str | None = None

    # Filled by IntentClassifier.
    current_intent: str | None = None
    intent_rationale: str | None = None

    # Filled by Retriever.
    ticket_data: dict[str, Any] | None = None
    retrieved_context: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_done: bool = False

    # Filled by Responder.
    final_answer: str | None = None

    # Orchestration bookkeeping (observability).
    next_node: str | None = None
    agent_history: list[str] = Field(default_factory=list)
    iteration: int = 0
    total_tokens: int = 0
