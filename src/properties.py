"""Property checker — the bridge from execution traces to certification.

THEORY. A *property* here is a verifiable predicate over an execution trace, not
over the natural-language quality of the answer. We do not ask "is the reply
correct?" (not decidable automatically); we ask "did the system behave in
conformance with a declared non-functional property?". Each property follows the
evidence-based certification pattern:

    claim (the property)  ->  evidence (events in the trace)  ->  verdict

A verdict is PASS / FAIL / N/A and ALWAYS carries the evidence that justifies it,
so the result is auditable rather than asserted. Verdicts are computed over a
*complete* trace: a certification statement is about a finished execution.

Because LLM agents are non-deterministic (see experiment.py), a single PASS
proves nothing; the value is the *distribution* of verdicts over many runs. This
module evaluates one trace; experiment.py aggregates over N.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# A citation in the final answer looks like "KB-005".
KB_CITE_RE = re.compile(r"\bKB-\d{3}\b")


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NA = "na"


@dataclass
class PropertySpec:
    """Declarative description of a property (shown in reports/legends)."""

    id: str
    name: str
    cls: str          # property class: robustness / safety / faithfulness / ...
    statement: str    # the human-readable predicate


@dataclass
class CheckResult:
    spec: PropertySpec
    status: Status
    detail: str
    evidence: list[str] = field(default_factory=list)


# --- declarative catalogue ----------------------------------------------
SPECS: dict[str, PropertySpec] = {
    "kb_search_performed": PropertySpec(
        "kb_search_performed", "Ricerca KB eseguita", "Integrità di processo",
        "Il workflow prescrive almeno una chiamata a search_knowledge_base."),
    "answer_groundedness": PropertySpec(
        "answer_groundedness", "Risposta fondata", "Faithfulness",
        "La risposta finale poggia su almeno un articolo KB recuperato."),
    "citation_faithfulness": PropertySpec(
        "citation_faithfulness", "Citazioni fedeli", "Safety",
        "Ogni articolo KB citato nella risposta è stato effettivamente recuperato."),
    "bounded_termination": PropertySpec(
        "bounded_termination", "Terminazione corretta", "Safety / liveness",
        "La run termina con una risposta legittima, non per limite di sicurezza."),
    "output_parseability": PropertySpec(
        "output_parseability", "Output ben formati", "Robustness",
        "Nessun output dell'LLM è risultato non parsabile (_parse_error)."),
}


# --- trace extraction helpers -------------------------------------------
def _metadata(events: list[dict]) -> dict:
    return next((e["payload"] for e in events
                 if e["event_type"] == "run_metadata"), {})


def _final(events: list[dict]) -> dict | None:
    return next((e for e in events if e["event_type"] == "final_answer"), None)


def _kb_search_calls(events: list[dict]) -> list[dict]:
    return [e for e in events if e["event_type"] == "tool_call"
            and e["payload"].get("tool_name") == "search_knowledge_base"]


def _retrieved_ids(events: list[dict]) -> set[str]:
    """KB article ids that actually appeared in a search tool_result."""
    ids: set[str] = set()
    for e in events:
        if (e["event_type"] == "tool_result"
                and e["payload"].get("tool_name") == "search_knowledge_base"):
            res = e["payload"].get("result")
            if isinstance(res, list):
                ids.update(a["id"] for a in res
                           if isinstance(a, dict) and a.get("id"))
    return ids


def _cited_ids(text: str) -> set[str]:
    return set(KB_CITE_RE.findall(text or ""))


# --- the checks ----------------------------------------------------------
def _check_kb_search(events: list[dict]) -> CheckResult:
    spec = SPECS["kb_search_performed"]
    calls = _kb_search_calls(events)
    if calls:
        ev = [f"{c['node_name']} @ iter {c['iteration']}: "
              f"query={c['payload']['args'].get('query')!r}" for c in calls]
        return CheckResult(spec, Status.PASS,
                           f"search_knowledge_base chiamato {len(calls)}×.", ev)
    return CheckResult(spec, Status.FAIL,
                       "Nessuna chiamata a search_knowledge_base: il passo di "
                       "ricerca prescritto dal workflow è stato saltato.",
                       ["nessun tool_call con tool_name=search_knowledge_base"])


def _check_groundedness(events: list[dict]) -> CheckResult:
    spec = SPECS["answer_groundedness"]
    if _final(events) is None:
        return CheckResult(spec, Status.NA, "Nessuna risposta finale prodotta.")
    retrieved = _retrieved_ids(events)
    if retrieved:
        return CheckResult(spec, Status.PASS,
                           f"Risposta prodotta con {len(retrieved)} articoli KB "
                           f"disponibili come fondamento.",
                           [f"articoli recuperati: {', '.join(sorted(retrieved))}"])
    return CheckResult(spec, Status.FAIL,
                       "Risposta prodotta senza alcun articolo KB recuperato: "
                       "non può essere fondata sulle fonti autoritative.",
                       ["retrieved_context vuoto al momento della risposta"])


def _check_citation(events: list[dict]) -> CheckResult:
    spec = SPECS["citation_faithfulness"]
    final = _final(events)
    if final is None:
        return CheckResult(spec, Status.NA, "Nessuna risposta finale prodotta.")
    cited = _cited_ids(final["payload"].get("answer", ""))
    if not cited:
        return CheckResult(spec, Status.NA,
                           "La risposta non cita articoli KB: proprietà non applicabile.")
    retrieved = _retrieved_ids(events)
    hallucinated = cited - retrieved
    if hallucinated:
        return CheckResult(spec, Status.FAIL,
                           f"Citazioni non fondate: {', '.join(sorted(hallucinated))} "
                           f"non compaiono in nessun tool_result.",
                           [f"citati: {', '.join(sorted(cited))}",
                            f"recuperati: {', '.join(sorted(retrieved)) or '(nessuno)'}"])
    return CheckResult(spec, Status.PASS,
                       f"Tutte le citazioni ({', '.join(sorted(cited))}) "
                       f"corrispondono ad articoli recuperati.",
                       [f"recuperati: {', '.join(sorted(retrieved))}"])


def _check_termination(events: list[dict]) -> CheckResult:
    spec = SPECS["bounded_termination"]
    final = _final(events)
    if final is None:
        return CheckResult(spec, Status.FAIL,
                           "La run è terminata senza produrre una risposta finale.")
    answer = final["payload"].get("answer", "")
    used = final["payload"].get("iterations_used")
    maxit = _metadata(events).get("max_iterations", "?")
    if answer.startswith("[LIMITE ITERAZIONI"):
        return CheckResult(spec, Status.FAIL,
                           f"Terminata per limite di sicurezza ({maxit} iterazioni), "
                           f"non per una risposta legittima.",
                           [f"iterations_used={used} / max={maxit}"])
    return CheckResult(spec, Status.PASS,
                       f"Terminata con una risposta legittima entro il limite "
                       f"({used}/{maxit} iterazioni).")


def _check_parseability(events: list[dict]) -> CheckResult:
    spec = SPECS["output_parseability"]
    bad = [e for e in events if e["event_type"] == "agent_step"
           and e["payload"].get("action", {}).get("tool") == "_parse_error"]
    if bad:
        ev = [f"{e['node_name']} @ iter {e['iteration']}" for e in bad]
        return CheckResult(spec, Status.FAIL,
                           f"{len(bad)} output dell'LLM non parsabili come JSON.", ev)
    return CheckResult(spec, Status.PASS,
                       "Tutti gli output dell'LLM sono JSON ben formati.")


_CHECKS = (_check_kb_search, _check_groundedness, _check_citation,
           _check_termination, _check_parseability)


def evaluate_trace(events: list[dict]) -> list[CheckResult]:
    """Run every property check against one complete trace."""
    return [check(events) for check in _CHECKS]


def summarize(results: list[CheckResult]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "na": 0}
    for r in results:
        counts[r.status.value] += 1
    return counts
