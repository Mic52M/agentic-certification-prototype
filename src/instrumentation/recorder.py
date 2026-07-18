"""Recorder: façade con cui il codice di dominio emette eventi.

L'obiettivo è tenere la business logic PULITA: gli agenti e l'orchestratore
non conoscono JSONL, canali AgentLeak, né UI live. Chiamano metodi ad alto
livello del Recorder (record_decision, record_handoff, ecc.) e il Recorder
costruisce il TraceEvent giusto e lo scrive nello store.
"""

from __future__ import annotations

import time
from typing import Any

from .events import ChannelId, EventKind, build_event
from .store import EventStore


class Recorder:
    """Wrapper di comodo attorno all'EventStore per il codice di dominio."""

    def __init__(self, store: EventStore) -> None:
        self.store = store
        self._run_start_ms = int(time.time() * 1000)

    # ---------- Metadati / meta -----------------------------------------
    def run_metadata(self, source: str, meta: dict[str, Any]) -> None:
        self.store.append(build_event(
            EventKind.RUN_METADATA,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            payload_summary=meta.get("summary", "run avviata"),
            metadata=meta,
        ))

    def run_end(self, source: str, outcome: str, meta: dict | None = None) -> None:
        self.store.append(build_event(
            EventKind.RUN_END,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            payload_summary=f"run terminata: {outcome}",
            metadata={"outcome": outcome, **(meta or {})},
        ))

    def error(self, source: str, detail: str) -> None:
        self.store.append(build_event(
            EventKind.ERROR,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            payload_summary=detail,
        ))

    # ---------- Control Flow (A1..A4) -----------------------------------
    def orchestrator_decision(self, target: str, reason: str,
                              alternatives: list[str] | None = None,
                              step: int = 0,
                              context_snapshot_keys: list[str] | None = None) -> None:
        self.store.append(build_event(
            EventKind.ORCHESTRATOR_DECISION,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component="orchestrator",
            target_component=target,
            payload_summary=f"→ {target} · {reason}",
            metadata={
                "reason": reason,
                "alternatives": alternatives or [],
                "step": step,
                "context_snapshot_keys": context_snapshot_keys or [],
            },
        ))

    def planning_span(self, agent: str, plan: list[str], updated: bool = False,
                      duration_ms: int = 0) -> None:
        self.store.append(build_event(
            EventKind.PLANNING_SPAN,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            payload_summary=f"piano [{len(plan)} step]: " + " → ".join(plan)[:200],
            metadata={"plan": plan, "n_steps": len(plan), "updated": updated},
            duration_ms=duration_ms,
        ))

    def replanning(self, agent: str, old_plan: list[str], new_plan: list[str],
                   reason: str) -> None:
        self.store.append(build_event(
            EventKind.REPLANNING,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            payload_summary=f"replanning: {reason}",
            metadata={"old_plan": old_plan, "new_plan": new_plan, "reason": reason},
        ))

    def handoff(self, source: str, target: str, reason: str,
                context_summary: str = "", payload_size: int = 0) -> None:
        self.store.append(build_event(
            EventKind.HANDOFF,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            target_component=target,
            payload_summary=f"{source} → {target} · {reason}",
            metadata={"reason": reason, "context_summary": context_summary,
                      "payload_size": payload_size},
        ))

    # ---------- Data Flow (B1: canali C1..C7) ---------------------------
    def tool_call(self, agent: str, tool_name: str, args: dict[str, Any]) -> None:
        # C3: input tool
        self.store.append(build_event(
            EventKind.TOOL_CALL,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            target_component=f"tool:{tool_name}",
            tool_name=tool_name,
            payload_summary=f"{tool_name}({_short(args)})",
            payload_redacted={"args": _redact(args)},
        ))

    def tool_result(self, agent: str, tool_name: str, result: Any,
                    success: bool, duration_ms: int = 0) -> None:
        # C4: output tool
        self.store.append(build_event(
            EventKind.TOOL_RESULT,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=f"tool:{tool_name}",
            target_component=agent,
            tool_name=tool_name,
            payload_summary=_short(result),
            payload_redacted={"result": _redact(result)},
            metadata={"success": success},
            duration_ms=duration_ms,
        ))

    def inter_agent_msg(self, source: str, target: str, subject: str,
                        content: str) -> None:
        # C2: messaggio inter-agente
        self.store.append(build_event(
            EventKind.INTER_AGENT_MSG,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            target_component=target,
            payload_summary=f"{source}→{target}: {subject}: {content[:180]}",
            payload_redacted={"subject": subject, "content": _redact_str(content)},
        ))

    def shared_memory_write(self, agent: str, key: str, value: Any,
                            namespace: str = "workspace") -> None:
        # C5: scrittura shared memory
        self.store.append(build_event(
            EventKind.SHARED_MEMORY_WRITE,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            target_component=f"memory:{namespace}",
            payload_summary=f"WRITE {namespace}/{key} = {_short(value, 120)}",
            payload_redacted={"key": key, "value": _redact(value)},
            metadata={"namespace": namespace, "key": key},
        ))

    def shared_memory_read(self, agent: str, key: str,
                           namespace: str = "workspace") -> None:
        self.store.append(build_event(
            EventKind.SHARED_MEMORY_READ,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=f"memory:{namespace}",
            target_component=agent,
            payload_summary=f"READ {namespace}/{key}",
            metadata={"namespace": namespace, "key": key},
        ))

    def final_output(self, agent: str, text: str) -> None:
        # C1: canale finale utente
        self.store.append(build_event(
            EventKind.FINAL_OUTPUT,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            target_component="user",
            payload_summary=text,
            payload_redacted={"text": _redact_str(text)},
        ))

    def artifact(self, agent: str, name: str, kind: str, content: str) -> None:
        # C7: artefatto persistente (es. report, riepilogo)
        self.store.append(build_event(
            EventKind.ARTIFACT_PRODUCED,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            payload_summary=f"artefatto '{name}' ({kind})",
            payload_redacted={"name": name, "kind": kind,
                              "content_excerpt": content[:600]},
        ))

    def reasoning_step(self, agent: str, thought: str) -> None:
        # C6: reasoning trace (utile per debugging e trajectory eval)
        self.store.append(build_event(
            EventKind.REASONING_STEP,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            payload_summary=thought[:280],
            payload_redacted={"thought": _redact_str(thought)},
        ))

    # ---------- Behavioral (C1..C4) -------------------------------------
    def decision_point(self, agent: str, label: str, choice: str,
                       inputs: dict[str, Any] | None = None,
                       meta: dict | None = None) -> None:
        self.store.append(build_event(
            EventKind.DECISION_POINT,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            agent_id=agent,
            source_component=agent,
            payload_summary=f"{label}: {choice}",
            payload_redacted={"inputs": _redact(inputs or {})},
            metadata={"label": label, "choice": choice, **(meta or {})},
        ))

    def state_snapshot(self, source: str, state: dict[str, Any],
                       label: str = "final_state") -> None:
        self.store.append(build_event(
            EventKind.STATE_SNAPSHOT,
            run_id=self.store.run.run_id,
            experiment_id=self.store.run.experiment_id,
            source_component=source,
            payload_summary=f"snapshot {label}: " + _short(state, 200),
            metadata={"state": state, "label": label},
        ))


# ---------------------- utils di serializzazione -------------------------
def _short(x: Any, n: int = 180) -> str:
    if isinstance(x, str):
        s = x
    else:
        import json
        try:
            s = json.dumps(x, ensure_ascii=False, default=str)
        except Exception:
            s = str(x)
    return s if len(s) <= n else s[:n] + " …"


def _redact_str(s: str) -> str:
    # Placeholder deliberato: qui NON redattiamo (la demo mostra le PII per
    # farle rilevare dall'aggregator). In produzione qui applicheresti maschere.
    return s


def _redact(x: Any) -> Any:
    if isinstance(x, str):
        return _redact_str(x)
    if isinstance(x, dict):
        return {k: _redact(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_redact(v) for v in x]
    return x
