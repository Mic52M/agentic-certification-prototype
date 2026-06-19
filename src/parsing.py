"""Robust extraction of the JSON action object from raw LLM text.

The ReAct contract is: the model returns a single JSON object. Models being
models, they sometimes wrap it in prose or code fences. We extract the first
balanced {...} block. Parsing failures are themselves observable: we return a
sentinel action so the loop can log the malformed output instead of crashing.
"""

from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Return the first balanced JSON object in `text`, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_react_action(raw_text: str) -> tuple[str, dict[str, Any], str]:
    """Parse a ReAct turn.

    Returns (thought, action_dict, parse_status) where action_dict is
    {"tool": str, "args": dict}. On failure, tool == "_parse_error".
    """
    obj = extract_json_object(raw_text)
    if obj is None:
        return ("", {"tool": "_parse_error", "args": {"raw": raw_text[:500]}},
                "no_json_found")

    thought = str(obj.get("thought", ""))
    action = obj.get("action", {})
    if not isinstance(action, dict):
        return (thought, {"tool": "_parse_error", "args": {"raw": str(action)}},
                "action_not_object")

    tool = action.get("tool")
    args = action.get("args", {})
    if not isinstance(args, dict):
        args = {}
    if not tool:
        return (thought, {"tool": "_parse_error", "args": {"raw": raw_text[:500]}},
                "missing_tool")
    return (thought, {"tool": str(tool), "args": args}, "ok")
