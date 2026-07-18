"""Agenti specializzati dell'incident triage.

Ognuno è un nodo del grafo LangGraph. Ogni azione:
- viene emessa come reasoning_step (C6);
- ogni tool call/result viene emesso su C3/C4;
- ogni scrittura sul workspace è un evento C5;
- ogni output verso un altro agente è un inter_agent_msg (C2);
- ogni decision_point è annotato per la macro comportamentale.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..instrumentation import Recorder
from ..llm_client import LLMClient
from ..parsing import extract_json_object
from . import prompts as P
from .state import IncidentState
from .tools import execute_tool, TOOL_DESCRIPTIONS


# =========================================================================
# Utility
# =========================================================================
def _clean_json(raw: str) -> dict[str, Any]:
    obj = extract_json_object(raw)
    return obj if isinstance(obj, dict) else {}


def _bytes_of(x: Any) -> int:
    try:
        return len(json.dumps(x, ensure_ascii=False, default=str).encode("utf-8"))
    except Exception:
        return len(str(x).encode("utf-8"))


# =========================================================================
# READER: legge il ticket incident (tool read_incident)
# =========================================================================
def build_reader_node(llm: LLMClient, recorder: Recorder):
    def reader(state: IncidentState) -> dict:
        agent = "reader"
        recorder.reasoning_step(agent, f"leggo l'incident {state.incident_id}")
        # tool call diretto (nessun LLM: è determinismo puro)
        args = {"incident_id": state.incident_id}
        recorder.tool_call(agent, "read_incident", args)
        t0 = time.time()
        result, ok = execute_tool("read_incident", args)
        recorder.tool_result(agent, "read_incident", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))
        if not ok:
            recorder.error(agent, f"read_incident failed: {result}")
            return {"agent_history": state.agent_history + [agent]}

        # C5: shared memory write
        recorder.shared_memory_write(agent, "incident_snapshot", result)
        ws = state.workspace.model_copy()
        ws.incident_snapshot = result
        # C2: comunico al planner cosa ho letto
        recorder.inter_agent_msg(agent, "planner", "incident_snapshot",
                                 f"Incident {result.get('id')} letto: "
                                 f"reporter={result.get('reporter_name')}, "
                                 f"servizio~{result.get('service_hint')}")
        return {"workspace": ws, "agent_history": state.agent_history + [agent]}

    return reader


# =========================================================================
# PLANNER: costruisce il piano di triage
# =========================================================================
def build_planner_node(llm: LLMClient, recorder: Recorder):
    def planner(state: IncidentState) -> dict:
        agent = "planner"
        inc = state.workspace.incident_snapshot or {}
        recorder.shared_memory_read(agent, "incident_snapshot")
        user_prompt = (
            f"Messaggio utente: {state.user_message}\n\n"
            f"Ticket incident (letto dalla memoria condivisa):\n"
            f"{json.dumps(inc, ensure_ascii=False, indent=2)}\n\n"
            f"Produci il piano di triage in JSON."
        )
        t0 = time.time()
        resp = llm.complete(P.TRIAGE_PLANNER_SYSTEM, user_prompt)
        dt = int((time.time() - t0) * 1000)
        obj = _clean_json(resp.text)

        thought = str(obj.get("thought", ""))
        plan = obj.get("plan") or []
        service = str(obj.get("affected_service") or "unknown")
        primary_symptom = str(obj.get("primary_symptom", ""))

        recorder.reasoning_step(agent, thought)
        # A2: planning span
        recorder.planning_span(agent, plan=list(plan), duration_ms=dt)
        # decision point: quale servizio investigare
        recorder.decision_point(agent, "affected_service", service,
                                inputs={"primary_symptom": primary_symptom},
                                meta={"n_steps": len(plan)})
        # C5: scrivo piano e servizio nel workspace
        recorder.shared_memory_write(agent, "triage_plan", plan)
        recorder.shared_memory_write(agent, "affected_service", service)
        # C2: notifica agli agenti investigatori
        recorder.inter_agent_msg(agent, "orchestrator",
                                 "triage_plan_ready",
                                 f"Piano pronto: {len(plan)} step, servizio={service}")

        ws = state.workspace.model_copy()
        ws.triage_plan = list(plan)
        return {
            "workspace": ws,
            "affected_service": service if service != "unknown" else None,
            "planning_done": True,
            "total_tokens": state.total_tokens + resp.total_tokens,
            "agent_history": state.agent_history + [agent],
        }

    return planner


# =========================================================================
# LOG INVESTIGATOR: due-step (call + done)
# =========================================================================
def _pick_service(state: IncidentState) -> str:
    if state.affected_service:
        return state.affected_service
    inc = state.workspace.incident_snapshot or {}
    hint = inc.get("service_hint")
    return hint or "mail-gateway"


def build_log_investigator_node(llm: LLMClient, recorder: Recorder):
    def investigator(state: IncidentState) -> dict:
        agent = "log_investigator"
        service = _pick_service(state)
        recorder.shared_memory_read(agent, "affected_service")
        recorder.reasoning_step(agent,
                                f"investigo i log di '{service}' (livello WARN+)")
        args = {"service": service, "min_level": "WARN"}
        recorder.tool_call(agent, "fetch_logs", args)
        t0 = time.time()
        result, ok = execute_tool("fetch_logs", args)
        recorder.tool_result(agent, "fetch_logs", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))

        findings = []
        if ok and isinstance(result, list):
            for row in result:
                findings.append(f"[{row['level']}] {row['component']}: {row['msg']}")

        # decision point sulla profondità dell'analisi
        recorder.decision_point(agent, "log_depth",
                                choice=f"{len(findings)} righe rilevanti",
                                meta={"service": service, "n_lines": len(findings)})
        # C5: shared memory
        recorder.shared_memory_write(agent, "findings_logs", findings)
        # C2: inter-agent
        recorder.inter_agent_msg(agent, "classifier", "findings_logs_ready",
                                 f"{len(findings)} findings dal servizio {service}")

        ws = state.workspace.model_copy()
        ws.findings_logs = findings
        return {
            "workspace": ws,
            "agent_history": state.agent_history + [agent],
        }

    return investigator


# =========================================================================
# METRICS ANALYST
# =========================================================================
def build_metrics_analyst_node(llm: LLMClient, recorder: Recorder):
    def analyst(state: IncidentState) -> dict:
        agent = "metrics_analyst"
        service = _pick_service(state)
        recorder.shared_memory_read(agent, "affected_service")
        recorder.reasoning_step(agent, f"analizzo le metriche di '{service}'")
        args = {"service": service}
        recorder.tool_call(agent, "fetch_metrics", args)
        t0 = time.time()
        result, ok = execute_tool("fetch_metrics", args)
        recorder.tool_result(agent, "fetch_metrics", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))

        findings: dict[str, Any] = {}
        if ok and isinstance(result, dict):
            # identifica il componente più critico su una combinazione di indicatori
            components = set()
            for k, v in result.items():
                if isinstance(v, dict):
                    components.update(v.keys())
            worst_component = None
            worst_score = -1
            for c in components:
                score = 0
                score += result.get("cpu_pct", {}).get(c, 0)
                score += result.get("mem_pct", {}).get(c, 0)
                score += (result.get("p95_latency_ms", {}).get(c, 0) / 20)
                score += (result.get("error_rate_pct", {}).get(c, 0) * 10)
                if score > worst_score:
                    worst_score = score
                    worst_component = c
            findings = {
                "critical_component": worst_component,
                "highlights": [
                    f"{worst_component}: CPU={result.get('cpu_pct', {}).get(worst_component)}%, "
                    f"latency_p95={result.get('p95_latency_ms', {}).get(worst_component)}ms, "
                    f"err={result.get('error_rate_pct', {}).get(worst_component)}%"
                ],
                "raw_snapshot": result,
            }

        recorder.decision_point(agent, "critical_component",
                                choice=str(findings.get("critical_component")),
                                meta={"service": service})
        recorder.shared_memory_write(agent, "findings_metrics", findings)
        recorder.inter_agent_msg(agent, "classifier", "findings_metrics_ready",
                                 f"critico={findings.get('critical_component')}")

        ws = state.workspace.model_copy()
        ws.findings_metrics = findings
        # se ora abbiamo entrambe le fonti, segna investigation_done
        investigation_done = bool(ws.findings_logs) and bool(ws.findings_metrics)
        return {
            "workspace": ws,
            "investigation_done": investigation_done,
            "affected_service": state.affected_service or service,
            "agent_history": state.agent_history + [agent],
        }

    return analyst


# =========================================================================
# POSTMORTEM RETRIEVER
# =========================================================================
def build_postmortem_retriever_node(llm: LLMClient, recorder: Recorder):
    def retriever(state: IncidentState) -> dict:
        agent = "postmortem_retriever"
        recorder.shared_memory_read(agent, "findings_logs")
        recorder.shared_memory_read(agent, "findings_metrics")
        # keywords derivate da findings + servizio
        service = state.affected_service or _pick_service(state)
        seed = [service]
        for row in (state.workspace.findings_logs or [])[:6]:
            for w in re.findall(r"\w+", row.lower()):
                if len(w) >= 4 and w not in seed:
                    seed.append(w)
        keywords = seed[:8]

        recorder.reasoning_step(agent,
                                f"cerco postmortem con parole chiave: {keywords[:6]}")
        args = {"keywords": keywords, "limit": 3}
        recorder.tool_call(agent, "query_postmortems", args)
        t0 = time.time()
        result, ok = execute_tool("query_postmortems", args)
        recorder.tool_result(agent, "query_postmortems", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))

        pms = result if isinstance(result, list) else []
        recorder.decision_point(agent, "postmortems_selected",
                                choice=", ".join(p.get("id", "?") for p in pms))
        recorder.shared_memory_write(agent, "related_postmortems", pms)
        recorder.inter_agent_msg(agent, "classifier", "postmortems_ready",
                                 f"{len(pms)} postmortem correlati")

        ws = state.workspace.model_copy()
        ws.related_postmortems = pms
        # dopo il retriever, l'investigation è comunque conclusa
        investigation_done = bool(ws.findings_logs or ws.findings_metrics)
        return {
            "workspace": ws,
            "investigation_done": investigation_done,
            "agent_history": state.agent_history + [agent],
        }

    return retriever


# =========================================================================
# CLASSIFIER
# =========================================================================
def build_classifier_node(llm: LLMClient, recorder: Recorder):
    def classifier(state: IncidentState) -> dict:
        agent = "classifier"
        recorder.shared_memory_read(agent, "findings_logs")
        recorder.shared_memory_read(agent, "findings_metrics")
        recorder.shared_memory_read(agent, "related_postmortems")

        context = {
            "primary_symptoms": (state.workspace.incident_snapshot or {}).get("symptoms", []),
            "findings_logs": state.workspace.findings_logs,
            "findings_metrics": state.workspace.findings_metrics,
            "related_postmortems": [
                {"id": p.get("id"), "title": p.get("title"), "tags": p.get("tags")}
                for p in state.workspace.related_postmortems
            ],
        }
        user_prompt = (
            f"Contesto raccolto (usa solo questo):\n"
            f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"Produci classificazione in JSON."
        )
        t0 = time.time()
        resp = llm.complete(P.CLASSIFIER_SYSTEM, user_prompt)
        dt = int((time.time() - t0) * 1000)
        obj = _clean_json(resp.text)

        thought = str(obj.get("thought", ""))
        classification = str(obj.get("classification", "unclassified"))
        priority = str(obj.get("priority", "P3"))
        confidence = str(obj.get("confidence", "low"))
        hypothesis = obj.get("hypothesis_ranked") or []

        recorder.reasoning_step(agent, thought)
        # tre decision_point espliciti (materia prima per intention-behavior)
        recorder.decision_point(agent, "classification", classification,
                                meta={"confidence": confidence})
        recorder.decision_point(agent, "priority", priority,
                                meta={"classification": classification})
        recorder.decision_point(agent, "hypothesis_ranking",
                                choice=str(len(hypothesis)) + " hp",
                                meta={"top": hypothesis[:1]})

        # C5: aggiorno il workspace
        recorder.shared_memory_write(agent, "hypothesis_ranked", hypothesis)
        # C2: notifica al summarizer
        recorder.inter_agent_msg(agent, "summarizer", "classification_ready",
                                 f"class={classification} prio={priority} conf={confidence}")

        ws = state.workspace.model_copy()
        ws.hypothesis_ranked = hypothesis
        return {
            "workspace": ws,
            "classification": classification,
            "priority": priority,
            "confidence": confidence,
            "classification_done": True,
            "total_tokens": state.total_tokens + resp.total_tokens,
            "agent_history": state.agent_history + [agent],
        }

    return classifier


# =========================================================================
# SUMMARIZER
# =========================================================================
def build_summarizer_node(llm: LLMClient, recorder: Recorder):
    def summarizer(state: IncidentState) -> dict:
        agent = "summarizer"
        recorder.shared_memory_read(agent, "hypothesis_ranked")
        recorder.shared_memory_read(agent, "related_postmortems")

        payload = {
            "incident_id": state.incident_id,
            "reporter": (state.workspace.incident_snapshot or {}).get("reporter_name"),
            "reporter_email": (state.workspace.incident_snapshot or {}).get("reporter_email"),
            "affected_service": state.affected_service,
            "classification": state.classification,
            "priority": state.priority,
            "confidence": state.confidence,
            "hypothesis_ranked": state.workspace.hypothesis_ranked,
            "postmortems": state.workspace.related_postmortems,
            "findings_logs": state.workspace.findings_logs,
            "findings_metrics": state.workspace.findings_metrics,
        }
        user_prompt = (
            f"Stato consolidato:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Produci JSON con recommended_actions e final_report."
        )
        t0 = time.time()
        resp = llm.complete(P.SUMMARIZER_SYSTEM, user_prompt)
        dt = int((time.time() - t0) * 1000)
        obj = _clean_json(resp.text)

        thought = str(obj.get("thought", ""))
        actions = obj.get("recommended_actions") or []
        final_text = str(obj.get("final_report") or "").strip() or resp.text.strip()

        recorder.reasoning_step(agent, thought)

        # Artefatto persistente (C7) + final output (C1)
        recorder.artifact(agent, name="triage_report", kind="markdown/plain",
                          content=final_text)
        recorder.final_output(agent, final_text)

        # State snapshot per BH-2 (state <-> output)
        recorder.state_snapshot("summarizer", state={
            "classification": state.classification,
            "priority": state.priority,
            "affected_service": state.affected_service,
            "confidence": state.confidence,
            "recommended_actions_count": len(actions),
        }, label="consolidated")

        return {
            "final_report": final_text,
            "recommended_actions": list(actions),
            "total_tokens": state.total_tokens + resp.total_tokens,
            "agent_history": state.agent_history + [agent],
        }

    return summarizer
