"""The three specialized agents for configuration 2.

Same model, different system prompts. They communicate ONLY through the shared
MultiAgentState — never directly with each other. Each node snapshots the state
before/after so every mutation is logged as a state_transition event.
"""

from __future__ import annotations

import json

from .. import prompts
from ..llm_client import LLMClient
from ..logging_utils import TraceLogger
from ..parsing import extract_json_object, parse_react_action
from ..state import MultiAgentState
from ..tools import execute_tool

# How many tool calls the retriever may make before being forced to stop.
RETRIEVER_MAX_STEPS = 4


def build_specialist_nodes(llm: LLMClient, logger: TraceLogger) -> dict:

    def intent_classifier_node(state: MultiAgentState) -> dict:
        before = state.model_dump()
        resp = llm.complete(prompts.INTENT_CLASSIFIER_SYSTEM, state.user_input)
        obj = extract_json_object(resp.text) or {}
        intent = str(obj.get("intent") or "other")
        thought = str(obj.get("thought") or "")
        ticket_id = obj.get("ticket_id") or state.task_ticket_id

        logger.agent_step("intent_classifier", state.iteration, thought,
                          {"tool": "classify_intent",
                           "args": {"intent": intent, "ticket_id": ticket_id}},
                          resp.raw_text)

        updates = {
            "current_intent": intent,
            "intent_rationale": thought,
            "task_ticket_id": ticket_id,
            "agent_history": state.agent_history + ["intent_classifier"],
            "total_tokens": state.total_tokens + resp.total_tokens,
        }
        logger.state_transition("intent_classifier", state.iteration,
                                before, {**before, **updates})
        logger.handoff("intent_classifier", "orchestrator", state.iteration,
                       "controllo restituito")
        return updates

    def retriever_node(state: MultiAgentState) -> dict:
        before = state.model_dump()
        ticket_data = state.ticket_data
        retrieved: list[dict] = list(state.retrieved_context)
        tokens = 0

        for sub in range(1, RETRIEVER_MAX_STEPS + 1):
            collected = {
                "intent": state.current_intent,
                "ticket_id_noto": state.task_ticket_id,
                "ticket_gia_letto": ticket_data is not None,
                "articoli_kb_trovati": len(retrieved),
            }
            user_prompt = (
                f"Richiesta utente: {state.user_input}\n"
                f"Stato raccolta finora: {json.dumps(collected, ensure_ascii=False)}\n"
                f"Produci il prossimo passo (JSON)."
            )
            resp = llm.complete(prompts.RETRIEVER_SYSTEM, user_prompt)
            tokens += resp.total_tokens
            thought, action, _ = parse_react_action(resp.text)
            tool, args = action["tool"], action["args"]
            logger.agent_step("retriever", state.iteration, thought, action,
                              resp.raw_text)

            if tool == "done":
                break
            logger.tool_call("retriever", state.iteration, tool, args)
            result, success = execute_tool(tool, args)
            logger.tool_result("retriever", state.iteration, tool, result, success)

            if tool == "read_ticket" and success:
                ticket_data = result
            elif tool == "search_knowledge_base" and isinstance(result, list):
                seen = {a.get("id") for a in retrieved}
                retrieved.extend(a for a in result if a.get("id") not in seen)

        updates = {
            "ticket_data": ticket_data,
            "retrieved_context": retrieved,
            "retrieval_done": True,
            "agent_history": state.agent_history + ["retriever"],
            "total_tokens": state.total_tokens + tokens,
        }
        logger.state_transition("retriever", state.iteration,
                                before, {**before, **updates})
        logger.handoff("retriever", "orchestrator", state.iteration,
                       "controllo restituito")
        return updates

    def responder_node(state: MultiAgentState) -> dict:
        before = state.model_dump()
        context = {
            "intent": state.current_intent,
            "ticket": state.ticket_data,
            "articoli_kb": state.retrieved_context,
        }
        user_prompt = (
            f"Richiesta utente: {state.user_input}\n\n"
            f"Contesto accumulato (usa solo questo):\n"
            f"{json.dumps(context, ensure_ascii=False, default=str)}\n\n"
            f"Produci la risposta finale (JSON)."
        )
        resp = llm.complete(prompts.RESPONDER_SYSTEM, user_prompt)
        obj = extract_json_object(resp.text) or {}
        thought = str(obj.get("thought") or "")
        answer = str(obj.get("answer") or resp.text).strip()

        logger.agent_step("responder", state.iteration, thought,
                          {"tool": "final_answer", "args": {"answer": answer}},
                          resp.raw_text)

        updates = {
            "final_answer": answer,
            "agent_history": state.agent_history + ["responder"],
            "total_tokens": state.total_tokens + resp.total_tokens,
        }
        logger.state_transition("responder", state.iteration,
                                before, {**before, **updates})
        logger.final_answer("responder", state.iteration, answer,
                            state.iteration, before["total_tokens"] + resp.total_tokens)
        logger.handoff("responder", "orchestrator", state.iteration,
                       "controllo restituito")
        return updates

    return {
        "intent_classifier": intent_classifier_node,
        "retriever": retriever_node,
        "responder": responder_node,
    }
