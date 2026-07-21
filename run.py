"""Entry point for the prototype.

    python run.py --config single_agent --task "L'utente ha aperto il ticket T-001, capisci il problema e proponi una soluzione."
    python run.py --config multi_agent  --task "..."

Each run writes one JSONL trace to ./traces/ and mirrors it live to the console.
"""

from __future__ import annotations

import argparse
import re
from importlib.metadata import version

from rich.console import Console

from src import config
from src.legacy import prompts
from src.llm_client import LLMClient
from src.legacy.logging_utils import TraceLogger, code_hash, make_run_id
from src.legacy.multi_agent.graph import build_multi_agent_graph
from src.legacy.multi_agent.orchestrator import ROUTING_RULES
from src.legacy.single_agent.agent import build_single_agent_graph
from src.legacy.state import MultiAgentState, SingleAgentState

TICKET_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)


def _extract_ticket_id(task: str) -> str | None:
    m = TICKET_RE.search(task)
    return m.group(0).upper() if m else None


def _base_metadata(configuration: str, task: str) -> dict:
    return {
        "configuration": configuration,
        "task": task,
        "code_hash": code_hash(),
        "langgraph_version": version("langgraph"),
        "groq_sdk_version": version("groq"),
        "pydantic_version": version("pydantic"),
        "model": config.MODEL,
        "temperature": config.TEMPERATURE,
        "max_iterations": config.MAX_ITERATIONS,
        "groq_base_url": config.GROQ_BASE_URL,
    }


def run_single_agent(task: str, logger: TraceLogger) -> None:
    metadata = _base_metadata("single_agent", task)
    metadata["system_prompts"] = {"agent": prompts.SINGLE_AGENT_SYSTEM}
    metadata["state_schema"] = SingleAgentState.model_json_schema()
    logger.write_metadata(metadata)

    llm = LLMClient()
    app = build_single_agent_graph(llm, logger)
    initial = SingleAgentState(task=task)
    app.invoke(initial, config={"recursion_limit": config.MAX_ITERATIONS * 2 + 5})


def run_multi_agent(task: str, logger: TraceLogger) -> None:
    metadata = _base_metadata("multi_agent", task)
    metadata["system_prompts"] = {
        "intent_classifier": prompts.INTENT_CLASSIFIER_SYSTEM,
        "retriever": prompts.RETRIEVER_SYSTEM,
        "responder": prompts.RESPONDER_SYSTEM,
    }
    metadata["state_schema"] = MultiAgentState.model_json_schema()
    metadata["routing_rules"] = [
        {"next_node": str(nxt), "reason": reason} for _, nxt, reason in ROUTING_RULES
    ]
    logger.write_metadata(metadata)

    llm = LLMClient()
    app = build_multi_agent_graph(llm, logger)
    initial = MultiAgentState(user_input=task, task_ticket_id=_extract_ticket_id(task))
    app.invoke(initial, config={"recursion_limit": 25})


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic certification prototype")
    parser.add_argument("--config", required=True,
                        choices=["single_agent", "multi_agent"])
    parser.add_argument("--task", required=True, help="Task in linguaggio naturale")
    args = parser.parse_args()

    console = Console()
    run_id = make_run_id(args.config, args.task)
    logger = TraceLogger(run_id, args.config, console)
    try:
        if args.config == "single_agent":
            run_single_agent(args.task, logger)
        else:
            run_multi_agent(args.task, logger)
    finally:
        logger.close()
        console.print(f"\n[bold]Traccia salvata in:[/bold] {logger.path}")


if __name__ == "__main__":
    main()
