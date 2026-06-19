"""Offline smoke tests — no Groq API key required.

We inject a scripted fake LLM so the graphs run end-to-end deterministically.
Run with:  python tests/smoke_test.py    (or: pytest tests/smoke_test.py)

These check plumbing (data, tools, parsing, both graphs, trace file), NOT model
quality — which by design requires the live model.
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402

from src import tools  # noqa: E402
from src.llm_client import LLMResponse  # noqa: E402
from src.logging_utils import TraceLogger, make_run_id  # noqa: E402
from src.multi_agent.graph import build_multi_agent_graph  # noqa: E402
from src.parsing import parse_react_action  # noqa: E402
from src.single_agent.agent import build_single_agent_graph  # noqa: E402
from src.state import MultiAgentState, SingleAgentState  # noqa: E402


class FakeLLM:
    """Returns scripted responses in order, ignoring the prompt."""

    def __init__(self, scripted: list[str]) -> None:
        self._scripted = list(scripted)
        self.model = "fake"

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        text = self._scripted.pop(0) if self._scripted else '{"thought":"done","action":{"tool":"done","args":{}}}'
        return LLMResponse(text=text, raw_text=text,
                           prompt_tokens=1, completion_tokens=1, total_tokens=2)


def _logger(config_name: str) -> TraceLogger:
    console = Console(file=StringIO(), force_terminal=False)
    run_id = make_run_id(config_name, "smoke")
    return TraceLogger(run_id, config_name, console)


def test_tools_and_data():
    ticket = tools.read_ticket("T-001")
    assert ticket["utente"] == "Giulia Ferrari", ticket
    assert tools.read_ticket("T-999").get("error") == "ticket_not_found"
    results = tools.search_knowledge_base("password account bloccato login")
    assert results and results[0]["id"] in {"KB-001", "KB-002"}, results
    _, success = tools.execute_tool("read_ticket", {"ticket_id": "T-001"})
    assert success is True
    print("ok  test_tools_and_data")


def test_parsing():
    thought, action, status = parse_react_action(
        'blah {"thought":"t","action":{"tool":"read_ticket","args":{"ticket_id":"T-001"}}} tail')
    assert status == "ok" and action["tool"] == "read_ticket", (action, status)
    _, bad, status = parse_react_action("no json here")
    assert bad["tool"] == "_parse_error" and status == "no_json_found"
    print("ok  test_parsing")


def test_single_agent_graph():
    llm = FakeLLM([
        '{"thought":"leggo il ticket","action":{"tool":"read_ticket","args":{"ticket_id":"T-001"}}}',
        '{"thought":"cerco in KB","action":{"tool":"search_knowledge_base","args":{"query":"account bloccato password"}}}',
        '{"thought":"rispondo","action":{"tool":"final_answer","args":{"answer":"Il tuo account e\' bloccato: attendi 15 minuti."}}}',
    ])
    logger = _logger("single_agent")
    app = build_single_agent_graph(llm, logger)
    final = app.invoke(SingleAgentState(task="ticket T-001"), config={"recursion_limit": 30})
    logger.close()
    assert final["final_answer"].startswith("Il tuo account"), final
    lines = logger.path.read_text(encoding="utf-8").strip().splitlines()
    types = [json.loads(l)["event_type"] for l in lines]
    assert "agent_step" in types and "tool_call" in types and "final_answer" in types, types
    print(f"ok  test_single_agent_graph ({len(lines)} events)")


def test_multi_agent_graph():
    llm = FakeLLM([
        # intent_classifier
        '{"thought":"accesso","intent":"password_access","ticket_id":"T-001"}',
        # retriever step 1: read ticket
        '{"thought":"leggo il ticket","action":{"tool":"read_ticket","args":{"ticket_id":"T-001"}}}',
        # retriever step 2: search
        '{"thought":"cerco","action":{"tool":"search_knowledge_base","args":{"query":"account bloccato"}}}',
        # retriever step 3: done
        '{"thought":"ho abbastanza","action":{"tool":"done","args":{}}}',
        # responder
        '{"thought":"compongo","answer":"Account temporaneamente bloccato; riprova tra 15 minuti."}',
    ])
    logger = _logger("multi_agent")
    app = build_multi_agent_graph(llm, logger)
    final = app.invoke(MultiAgentState(user_input="ticket T-001", task_ticket_id="T-001"),
                       config={"recursion_limit": 30})
    logger.close()
    assert final["final_answer"].startswith("Account"), final
    assert final["agent_history"] == ["intent_classifier", "retriever", "responder"], final["agent_history"]
    types = {json.loads(l)["event_type"]
             for l in logger.path.read_text(encoding="utf-8").strip().splitlines()}
    assert {"orchestrator_decision", "state_transition", "agent_step", "final_answer"} <= types, types
    print(f"ok  test_multi_agent_graph (history={final['agent_history']})")


if __name__ == "__main__":
    test_tools_and_data()
    test_parsing()
    test_single_agent_graph()
    test_multi_agent_graph()
    print("\nALL SMOKE TESTS PASSED")
