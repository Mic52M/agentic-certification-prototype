"""Thin wrapper over the Groq OpenAI-compatible chat API.

Design notes (certification angle):
- This is the ONLY place the system talks to the model. It is therefore the
  natural choke point for future control hooks (input/output guardrails,
  prompt logging, sampling-parameter enforcement).
- We use plain chat completions, NOT tool/function calling, because the ReAct
  loop must be EXPLICIT: the model emits Thought+Action as text we parse, so
  every decision is visible in the trace rather than hidden in an opaque
  tool-call object.
- Qwen3 on Groq can emit <think>...</think> reasoning blocks. We strip them
  before parsing the JSON action, but we keep the raw output in the trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from groq import Groq

from . import config


@dataclass
class LLMResponse:
    text: str          # model output with <think> blocks stripped
    raw_text: str      # exactly what the model returned
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMClient:
    """Stateless single-shot completion client."""

    def __init__(
        self,
        model: str = config.MODEL,
        temperature: float = config.TEMPERATURE,
        base_url: str = config.GROQ_BASE_URL,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.base_url = base_url
        # Groq() reads GROQ_API_KEY from env by default; we pass it explicitly
        # so the failure mode is a clear message instead of a vague auth error.
        self._client = Groq(api_key=config.require_api_key(), base_url=base_url)

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """One system + one user message in, one parsed response out."""
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = resp.choices[0].message.content or ""
        cleaned = _THINK_RE.sub("", raw).strip()
        usage = resp.usage
        return LLMResponse(
            text=cleaned,
            raw_text=raw,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )
