"""The two tools available to the agents.

Certification angle: tool boundaries are CONTROL POINTS. Every call goes
through `execute_tool`, which is where a future implementation could enforce
input validation, authorization, rate limits, or PII redaction. The keyword
matching is intentionally naive — the prototype is about observability, not
retrieval quality.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from . import config


@lru_cache(maxsize=1)
def _load_knowledge_base() -> list[dict[str, Any]]:
    return json.loads(config.KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_tickets() -> dict[str, dict[str, Any]]:
    tickets = json.loads(config.TICKETS_PATH.read_text(encoding="utf-8"))
    return {t["id"]: t for t in tickets}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def search_knowledge_base(query: str) -> list[dict[str, Any]]:
    """Naive keyword search over the in-memory KB.

    Scores each article by overlap between the query tokens and the article's
    tags + title + content. Returns up to 3 articles with score > 0, each
    annotated with the match score (useful as an observability signal).
    """
    q_tokens = _tokenize(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for article in _load_knowledge_base():
        haystack = " ".join(
            [article["titolo"], " ".join(article["tag"]), article["contenuto"]]
        )
        score = len(q_tokens & _tokenize(haystack))
        # Tags are high-signal: weight an exact tag hit extra.
        score += sum(2 for tag in article["tag"] if tag.lower() in q_tokens)
        if score > 0:
            scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**article, "_match_score": score} for score, article in scored[:3]]


def read_ticket(ticket_id: str) -> dict[str, Any]:
    """Fetch a simulated ticket by id. Returns an error dict if not found."""
    ticket = _load_tickets().get(ticket_id.strip())
    if ticket is None:
        return {
            "error": "ticket_not_found",
            "ticket_id": ticket_id,
            "available_ids": sorted(_load_tickets().keys()),
        }
    return ticket


# Registry: the single source of truth for what tools exist. Both
# configurations dispatch through `execute_tool`, so this is the one place
# to instrument tool usage for certification.
TOOL_REGISTRY = {
    "search_knowledge_base": search_knowledge_base,
    "read_ticket": read_ticket,
}

TOOL_DESCRIPTIONS = {
    "search_knowledge_base": "search_knowledge_base(query: str) -> list[article] "
    "— cerca articoli nella knowledge base tecnica.",
    "read_ticket": "read_ticket(ticket_id: str) -> ticket "
    "— recupera i dettagli di un ticket (es. 'T-001').",
}


def execute_tool(tool_name: str, args: dict[str, Any]) -> tuple[Any, bool]:
    """Single dispatch point. Returns (result, success)."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return ({"error": "unknown_tool", "tool_name": tool_name}, False)
    try:
        result = fn(**args)
        # A not-found ticket is a "successful call, negative result".
        success = not (isinstance(result, dict) and result.get("error"))
        return result, success
    except TypeError as exc:
        return ({"error": "bad_arguments", "detail": str(exc)}, False)
    except Exception as exc:  # noqa: BLE001 - base-level interception is enough here
        return ({"error": "tool_exception", "detail": str(exc)}, False)
