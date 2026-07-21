"""Agenti specializzati dell'incident triage — versione snellita.

Ognuno è un nodo del grafo LangGraph. La strumentazione emette solo gli eventi
significativi per le tre macro-dimensioni:
- reasoning_step (C6) quando c'è ragionamento non ridondante;
- tool call/result (C3/C4);
- shared_memory_write (C5) per ogni scrittura nel workspace;
- shared_memory_read (C5) solo quando è informativo (non appena c'è già lo state);
- inter_agent_msg (C2) solo per gli scambi realmente inter-agente;
- decision_point (BH) sui punti di scelta significativi;
- final_output (C1), artifact_produced (C7), state_snapshot alla chiusura.
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
from .tools import execute_tool


def _clean_json(raw: str) -> dict[str, Any]:
    obj = extract_json_object(raw)
    return obj if isinstance(obj, dict) else {}


# =========================================================================
# READER: legge il ticket incident
# =========================================================================
def build_reader_node(llm: LLMClient, recorder: Recorder):
    def reader(state: IncidentState) -> dict:
        agent = "reader"
        args = {"incident_id": state.incident_id}
        recorder.tool_call(agent, "read_incident", args)
        t0 = time.time()
        result, ok = execute_tool("read_incident", args)
        recorder.tool_result(agent, "read_incident", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))
        if not ok:
            recorder.error(agent, f"read_incident failed: {result}")
            return {"agent_history": state.agent_history + [agent]}

        recorder.shared_memory_write(agent, "incident_snapshot", result)
        # Un solo messaggio inter-agente al planner: è la sola comunicazione
        # sensata (il planner è il prossimo attore che deve conoscere l'incident).
        recorder.inter_agent_msg(agent, "planner", "incident_snapshot",
                                 f"Incident {result.get('id')}: "
                                 f"reporter={result.get('reporter_name')}, "
                                 f"servizio~{result.get('service_hint')}")
        ws = state.workspace.model_copy()
        ws.incident_snapshot = result
        return {"workspace": ws, "agent_history": state.agent_history + [agent]}

    return reader


# =========================================================================
# PLANNER: costruisce il piano di triage (LLM)
# =========================================================================
def build_planner_node(llm: LLMClient, recorder: Recorder):
    def planner(state: IncidentState) -> dict:
        agent = "planner"
        inc = state.workspace.incident_snapshot or {}
        # Una sola read esplicita per mostrare la lettura del workspace.
        recorder.shared_memory_read(agent, "incident_snapshot")
        user_prompt = (
            f"Messaggio utente: {state.user_message}\n\n"
            f"Ticket incident:\n{json.dumps(inc, ensure_ascii=False, indent=2)}\n\n"
            f"Produci il piano di triage in JSON."
        )
        t0 = time.time()
        resp = llm.complete(P.TRIAGE_PLANNER_SYSTEM, user_prompt)
        dt = int((time.time() - t0) * 1000)
        obj = _clean_json(resp.text)

        thought = str(obj.get("thought", ""))
        plan = list(obj.get("plan") or [])
        service = str(obj.get("affected_service") or "unknown")
        primary_symptom = str(obj.get("primary_symptom", ""))

        recorder.reasoning_step(agent, thought)
        recorder.planning_span(agent, plan=plan, duration_ms=dt)
        recorder.decision_point(agent, "affected_service", service,
                                inputs={"primary_symptom": primary_symptom},
                                meta={"n_steps": len(plan)})
        recorder.shared_memory_write(agent, "triage_plan", plan)
        recorder.shared_memory_write(agent, "affected_service", service)

        ws = state.workspace.model_copy()
        ws.triage_plan = plan
        return {
            "workspace": ws,
            "affected_service": service if service != "unknown" else None,
            "planning_done": True,
            "total_tokens": state.total_tokens + resp.total_tokens,
            "agent_history": state.agent_history + [agent],
        }

    return planner


# =========================================================================
# LOG INVESTIGATOR (deterministico)
# =========================================================================
def _pick_service(state: IncidentState) -> str:
    if state.affected_service:
        return state.affected_service
    inc = state.workspace.incident_snapshot or {}
    return inc.get("service_hint") or "mail-gateway"


def build_log_investigator_node(llm: LLMClient, recorder: Recorder):
    def investigator(state: IncidentState) -> dict:
        agent = "log_investigator"
        service = _pick_service(state)
        args = {"service": service, "min_level": "WARN"}
        recorder.tool_call(agent, "fetch_logs", args)
        t0 = time.time()
        result, ok = execute_tool("fetch_logs", args)
        recorder.tool_result(agent, "fetch_logs", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))

        findings: list[str] = []
        if ok and isinstance(result, list):
            for row in result:
                findings.append(f"[{row['level']}] {row['component']}: {row['msg']}")

        recorder.decision_point(agent, "log_depth",
                                choice=f"{len(findings)} righe rilevanti",
                                meta={"service": service, "n_lines": len(findings)})
        recorder.shared_memory_write(agent, "findings_logs", findings)

        ws = state.workspace.model_copy()
        ws.findings_logs = findings
        return {"workspace": ws,
                "agent_history": state.agent_history + [agent]}

    return investigator


# =========================================================================
# METRICS ANALYST (deterministico)
# =========================================================================
def build_metrics_analyst_node(llm: LLMClient, recorder: Recorder):
    def analyst(state: IncidentState) -> dict:
        agent = "metrics_analyst"
        service = _pick_service(state)
        args = {"service": service}
        recorder.tool_call(agent, "fetch_metrics", args)
        t0 = time.time()
        result, ok = execute_tool("fetch_metrics", args)
        recorder.tool_result(agent, "fetch_metrics", result, ok,
                             duration_ms=int((time.time() - t0) * 1000))

        findings: dict[str, Any] = {}
        if ok and isinstance(result, dict):
            components = set()
            for k, v in result.items():
                if isinstance(v, dict):
                    components.update(v.keys())
            worst_component = None
            worst_score = -1.0
            for c in components:
                score = 0.0
                score += result.get("cpu_pct", {}).get(c, 0)
                score += result.get("mem_pct", {}).get(c, 0)
                score += (result.get("p95_latency_ms", {}).get(c, 0) / 20)
                score += (result.get("error_rate_pct", {}).get(c, 0) * 10)
                if score > worst_score:
                    worst_score, worst_component = score, c
            findings = {
                "critical_component": worst_component,
                "highlights": [
                    f"{worst_component}: CPU={result.get('cpu_pct', {}).get(worst_component)}%, "
                    f"lat_p95={result.get('p95_latency_ms', {}).get(worst_component)}ms, "
                    f"err={result.get('error_rate_pct', {}).get(worst_component)}%"
                ],
                "raw_snapshot": result,
            }

        recorder.decision_point(agent, "critical_component",
                                choice=str(findings.get("critical_component")),
                                meta={"service": service})
        recorder.shared_memory_write(agent, "findings_metrics", findings)

        ws = state.workspace.model_copy()
        ws.findings_metrics = findings
        investigation_done = bool(ws.findings_logs) and bool(ws.findings_metrics)
        return {
            "workspace": ws,
            "investigation_done": investigation_done,
            "affected_service": state.affected_service or service,
            "agent_history": state.agent_history + [agent],
        }

    return analyst


# =========================================================================
# POSTMORTEM RETRIEVER (deterministico)
# =========================================================================
def build_postmortem_retriever_node(llm: LLMClient, recorder: Recorder):
    def retriever(state: IncidentState) -> dict:
        agent = "postmortem_retriever"
        service = state.affected_service or _pick_service(state)
        # keywords derivate da findings + servizio
        seed = [service]
        for row in (state.workspace.findings_logs or [])[:6]:
            for w in re.findall(r"\w+", row.lower()):
                if len(w) >= 4 and w not in seed:
                    seed.append(w)
        keywords = seed[:8]

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

        ws = state.workspace.model_copy()
        ws.related_postmortems = pms
        investigation_done = bool(ws.findings_logs or ws.findings_metrics)
        return {"workspace": ws,
                "investigation_done": investigation_done,
                "agent_history": state.agent_history + [agent]}

    return retriever


# =========================================================================
# CLASSIFIER (LLM)
# =========================================================================
def build_classifier_node(llm: LLMClient, recorder: Recorder):
    def classifier(state: IncidentState) -> dict:
        agent = "classifier"
        # una sola read esplicita, sulle findings principali, per mostrare
        # che il classifier attinge al workspace.
        recorder.shared_memory_read(agent, "findings_logs")

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
        obj = _clean_json(resp.text)

        thought = str(obj.get("thought", ""))
        classification = str(obj.get("classification", "unclassified"))
        priority = str(obj.get("priority", "P3"))
        confidence = str(obj.get("confidence", "low"))
        hypothesis = obj.get("hypothesis_ranked") or []

        recorder.reasoning_step(agent, thought)
        # Un unico decision_point che porta tutte le decisioni del classifier
        # nei suoi metadati (classification è la "scelta principale", priority
        # / confidence / hypothesis in meta).
        recorder.decision_point(agent, "classification", classification,
                                meta={"priority": priority,
                                      "confidence": confidence,
                                      "n_hypothesis": len(hypothesis),
                                      "top_hypothesis": hypothesis[:1]})
        recorder.shared_memory_write(agent, "hypothesis_ranked", hypothesis)

        # Un solo messaggio inter-agente al summarizer.
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
# SUMMARIZER (LLM)
# =========================================================================
def build_summarizer_node(llm: LLMClient, recorder: Recorder):
    def summarizer(state: IncidentState) -> dict:
        agent = "summarizer"
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
        obj = _clean_json(resp.text)

        actions = list(obj.get("recommended_actions") or [])
        final_text = str(obj.get("final_report") or "").strip() or resp.text.strip()

        # Nessun reasoning_step separato: il final_output è già l'output
        # sostantivo del summarizer, il thought sarebbe solo meta-narrativa.
        recorder.artifact(agent, name="triage_report", kind="markdown/plain",
                          content=final_text)
        recorder.final_output(agent, final_text)
        recorder.state_snapshot("summarizer", state={
            "classification": state.classification,
            "priority": state.priority,
            "affected_service": state.affected_service,
            "confidence": state.confidence,
            "recommended_actions_count": len(actions),
        }, label="consolidated")

        return {
            "final_report": final_text,
            "recommended_actions": actions,
            "total_tokens": state.total_tokens + resp.total_tokens,
            "agent_history": state.agent_history + [agent],
        }

    return summarizer
