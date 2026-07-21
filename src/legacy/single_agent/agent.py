r"""Configuration 1 — single agent with an explicit ReAct loop.

Graph shape (a cycle, which is what makes it a loop):

    START -> agent -> (final?) -> finalize -> END
                   \-> tool -> agent

One model, one system prompt, plays every role. Every Thought/Action/Observation
is logged. The cycle is bounded by MAX_ITERATIONS as a safety control point.
"""

from __future__ import annotations

import json

from langgraph.graph import END, START, StateGraph

from ... import config
from .. import prompts
from ...llm_client import LLMClient
from ..logging_utils import TraceLogger
from ...parsing import parse_react_action
from ..state import ReActStep, SingleAgentState
from ..tools import execute_tool


def _render_history(state: SingleAgentState) -> str:
    """Serialize prior steps so the model sees its own trajectory."""
    if not state.history:
        return "(nessun passo precedente — questa e' la prima iterazione, Observation vuota)"
    lines = []
    for step in state.history:
        lines.append(f"[iter {step.iteration}]")
        lines.append(f"Thought: {step.thought}")
        lines.append(f"Action: {json.dumps({'tool': step.action_tool, 'args': step.action_args}, ensure_ascii=False)}")
        obs = step.observation
        obs_str = json.dumps(obs, ensure_ascii=False, default=str) if obs is not None else "(in attesa)"
        if len(obs_str) > 1200:
            obs_str = obs_str[:1200] + " …"
        lines.append(f"Observation: {obs_str}")
    return "\n".join(lines)


def build_single_agent_graph(llm: LLMClient, logger: TraceLogger):
    def agent_node(state: SingleAgentState) -> dict:
        iteration = state.iteration + 1
        user_prompt = (
            f"Task: {state.task}\n\n"
            f"Storico ReAct finora:\n{_render_history(state)}\n\n"
            f"Produci il prossimo passo (Thought + Action) come JSON."
        )
        resp = llm.complete(prompts.SINGLE_AGENT_SYSTEM, user_prompt)
        thought, action, _status = parse_react_action(resp.text)
        tool = action["tool"]
        args = action["args"]
        logger.agent_step("agent", iteration, thought, action, resp.raw_text)

        step = ReActStep(iteration=iteration, thought=thought,
                         action_tool=tool, action_args=args)
        history = state.history + [step]

        updates: dict = {
            "iteration": iteration,
            "pending_tool": tool,
            "pending_args": args,
            "history": history,
            "total_tokens": state.total_tokens + resp.total_tokens,
        }
        if tool == "final_answer":
            updates["final_answer"] = str(args.get("answer", "")).strip()
        elif iteration >= config.MAX_ITERATIONS:
            updates["final_answer"] = (
                "[LIMITE ITERAZIONI RAGGIUNTO] Non e' stata prodotta una risposta "
                "finale entro il limite di sicurezza. Ultimo ragionamento: " + thought
            )
        return updates

    def tool_node(state: SingleAgentState) -> dict:
        tool, args = state.pending_tool, state.pending_args
        logger.tool_call("agent", state.iteration, tool, args)
        result, success = execute_tool(tool, args)
        logger.tool_result("agent", state.iteration, tool, result, success)
        # Attach the observation to the step we just took.
        history = [s.model_copy() for s in state.history]
        if history:
            history[-1].observation = result
        return {"last_observation": result, "history": history}

    def finalize_node(state: SingleAgentState) -> dict:
        logger.final_answer("agent", state.iteration, state.final_answer or "",
                            state.iteration, state.total_tokens)
        return {}

    def route_after_agent(state: SingleAgentState) -> str:
        return "finalize" if state.final_answer is not None else "tool"

    graph = StateGraph(SingleAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tool", tool_node)
    graph.add_node("finalize", finalize_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent,
                                {"tool": "tool", "finalize": "finalize"})
    graph.add_edge("tool", "agent")
    graph.add_edge("finalize", END)
    # recursion_limit covers all super-steps; generous vs MAX_ITERATIONS.
    return graph.compile()
