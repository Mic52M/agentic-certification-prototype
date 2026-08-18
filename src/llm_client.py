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

Cache integrazione (fase 1: rate limit → esperimenti su N grande):
- Se il client riceve una `LLMCache`, ogni `.complete()` consulta la cache
  prima di chiamare il provider. La cache si attiva solo a `temperature==0.0`
  (regola dura, cfr. `llm_cache.py`).
- Ogni risposta porta un `cache_status` che verrà propagato negli eventi
  trace: chi legge un esperimento vede sempre quante chiamate sono state
  reali, quante servite da cache, quante verificate.
- Verify sampling: una frazione delle cache-hit viene ri-eseguita contro il
  provider per detectare drift lato modello; se il testo diverge, il codice
  fallisce forte (nessuna verità silenziosa).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from groq import Groq

from . import config
from .instrumentation.llm_cache import (
    CACHE_STATUS_DISABLED,
    CACHE_STATUS_HIT,
    CACHE_STATUS_MISS,
    CACHE_STATUS_VERIFIED_HIT,
    LLMCache,
    fingerprint,
)


@dataclass
class LLMResponse:
    text: str          # model output with <think> blocks stripped
    raw_text: str      # exactly what the model returned
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    # Provenance della risposta rispetto alla cache LLM. Uno tra:
    # "miss" | "hit" | "verified_hit" | "disabled".
    cache_status: str = CACHE_STATUS_DISABLED
    # Fingerprint della richiesta (audit trail: comparire nei metadata degli
    # eventi trace, così l'esperimento è pienamente ricostruibile ex-post).
    request_fingerprint: str = ""
    # Metriche di tempo utili per la certificazione (latenza percepita).
    latency_ms: int = 0
    # Extra metadata (es. dettagli di drift se una verifica ha trovato
    # differenze — vuoto nella maggioranza dei casi).
    extra: dict = field(default_factory=dict)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class CacheDriftError(RuntimeError):
    """Sollevato quando una cache-hit viene verificata e diverge dal provider.

    Fallire forte è deliberato: una divergenza significa che il provider ha
    modificato silenziosamente il modello, o che la cache è stata corrotta,
    o che qualcosa nel prompt engineering è cambiato senza aggiornare gli
    esperimenti. Nessuno di questi casi va nascosto in un log.
    """


class LLMClient:
    """Stateless single-shot completion client, con cache opzionale."""

    def __init__(
        self,
        model: str = config.MODEL,
        temperature: float = config.TEMPERATURE,
        base_url: str = config.GROQ_BASE_URL,
        cache: LLMCache | None = None,
        verify_sample: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        # base_url is recorded for the trace metadata. The Groq SDK already
        # targets the OpenAI-compatible endpoint and appends "/openai/v1"
        # itself, so we do NOT pass it through (doing so double-prefixes the
        # path -> 404). We only override the client's base if a *custom*
        # host (not the documented default) is configured.
        self.base_url = base_url
        self.cache = cache
        # Frazione [0,1] di cache-hit che vengono ri-eseguite contro il
        # provider per verificare l'assenza di drift lato modello.
        self.verify_sample = max(0.0, min(1.0, verify_sample))
        # RNG deliberatamente NON seedato: la scelta di quali entry
        # verificare deve variare tra esperimenti diversi, così su un
        # orizzonte lungo copriamo hash diversi.
        self._rng = rng or random.Random()
        # Groq() reads GROQ_API_KEY from env by default; we pass it explicitly
        # so the failure mode is a clear message instead of a vague auth error.
        self._client = Groq(api_key=config.require_api_key())

    # ---------------------------------------------------------------
    # API pubblica
    # ---------------------------------------------------------------
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """One system + one user message in, one parsed response out.

        Se il client ha una cache e `temperature==0.0`, prima consulta la
        cache; se HIT, decide con probabilità `verify_sample` se ri-eseguire
        la chiamata reale per confrontare bit-a-bit.
        """
        fp = fingerprint(self.model, system_prompt, user_prompt, self.temperature)

        # 1) Nessuna cache o temperature != 0 → chiamata reale, status "disabled".
        if self.cache is None:
            return self._call_provider(system_prompt, user_prompt, fp,
                                       cache_status=CACHE_STATUS_DISABLED)

        # 2) Cache presente: tenta il lookup (la cache stessa applica la
        #    regola sulla temperatura; a temp>0 ritorna sempre None).
        cached = self.cache.get(self.model, system_prompt, user_prompt,
                                self.temperature)

        if cached is None:
            # MISS: chiama il provider e memoizza.
            resp = self._call_provider(system_prompt, user_prompt, fp,
                                       cache_status=CACHE_STATUS_MISS)
            self.cache.put(
                self.model, system_prompt, user_prompt, self.temperature,
                text=resp.text, raw_text=resp.raw_text,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                total_tokens=resp.total_tokens,
            )
            return resp

        # 3) HIT: eventuale verifica campionaria.
        if self.verify_sample > 0.0 and self._rng.random() < self.verify_sample:
            live = self._call_provider(system_prompt, user_prompt, fp,
                                       cache_status=CACHE_STATUS_VERIFIED_HIT)
            if live.text != cached.text or live.raw_text != cached.raw_text:
                raise CacheDriftError(
                    f"cache drift su fingerprint {fp}: "
                    f"cached len={len(cached.text)} vs live len={len(live.text)}. "
                    "Il provider ha probabilmente modificato il modello: "
                    "svuota la cache dell'esperimento e rigenera."
                )
            # Verifica passata: torniamo la versione appena calcolata dal
            # provider (equivalente a quella cached, per costruzione) e la
            # etichettiamo come verified_hit.
            return live

        # 3b) HIT semplice, nessuna chiamata reale.
        return LLMResponse(
            text=cached.text,
            raw_text=cached.raw_text,
            prompt_tokens=cached.prompt_tokens,
            completion_tokens=cached.completion_tokens,
            total_tokens=cached.total_tokens,
            cache_status=CACHE_STATUS_HIT,
            request_fingerprint=fp,
            latency_ms=0,
        )

    # ---------------------------------------------------------------
    # Chiamata reale al provider (usata anche per verify)
    # ---------------------------------------------------------------
    def _call_provider(self, system_prompt: str, user_prompt: str,
                       fp: str, *, cache_status: str) -> LLMResponse:
        import time as _time
        t0 = _time.time()
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        dt = int((_time.time() - t0) * 1000)
        raw = resp.choices[0].message.content or ""
        cleaned = _THINK_RE.sub("", raw).strip()
        usage = resp.usage
        return LLMResponse(
            text=cleaned,
            raw_text=raw,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            cache_status=cache_status,
            request_fingerprint=fp,
            latency_ms=dt,
        )
