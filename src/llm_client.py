"""Client LLM multi-provider con fallback e rate-limit adattivo.

Design (angolo certificazione)
------------------------------
Questa è l'UNICA superficie di contatto con i provider LLM: ogni chiamata,
ogni fallback, ogni ritardo indotto dal rate limit è osservabile qui.
Ogni `LLMResponse` porta con sé `provider`, `model`, `latency_ms`,
`request_fingerprint` e conteggio token → gli eventi trace registrano
sempre chi ha risposto a cosa, così un esperimento su N grande è
completamente auditabile ex-post (essenziale per il paper).

Architettura
------------
- `BaseBackend`: interfaccia astratta (`.complete()`, `.is_available()`,
  `.canonical_to_native(model)` per il naming per-provider).
- `GroqBackend`, `CerebrasBackend`: implementazioni concrete. Ognuno:
  * mappa il nome canonico del modello al naming del provider;
  * espone `remaining_tokens` / `reset_seconds` dai response header per il
    rate-limit adattivo;
  * alza un `_RateLimited` interno su 429/quota exceeded → il client passa
    al backend successivo.
- `LLMClient`: orchestra i backend in ordine di priorità. Su rate-limit del
  primo, prova il secondo. Se tutti falliscono, ripropaga l'ultimo errore.
  Prima di ogni chiamata applica una policy di attesa se il backend
  preferito è sotto-soglia (adaptive sleep).

Nessuna cache: la varianza residua a `temperature=0` (batch-composition e
non-associatività floating-point lato provider) è parte del segnale
scientifico che vogliamo osservare, non un difetto da sopprimere.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config


# =========================================================================
# Response type
# =========================================================================
@dataclass
class LLMResponse:
    text: str          # model output con <think>...</think> strippato
    raw_text: str      # exactly what the model returned
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str = ""             # "groq" | "cerebras"
    model: str = ""                # nome canonico usato nella richiesta
    native_model: str = ""         # nome per-provider (dopo il mapping)
    request_fingerprint: str = ""  # hash sha256 stabile della richiesta
    latency_ms: int = 0
    # Informazione di rate limit residua sul provider che ha risposto,
    # letta dai response header quando disponibile.
    remaining_tokens: int | None = None
    reset_seconds: float | None = None
    # Se la chiamata è finita su un backend non-primario, il primario ha
    # fallito: registriamo l'errore per l'audit.
    fallback_from: list[str] = field(default_factory=list)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def request_fingerprint(model: str, system_prompt: str, user_prompt: str,
                        temperature: float) -> str:
    payload = json.dumps(
        {"model": model, "system": system_prompt,
         "user": user_prompt, "temperature": temperature},
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# =========================================================================
# Errori interni per il flusso di fallback
# =========================================================================
class _RateLimited(Exception):
    """Sollevato da un backend quando il provider dice 429/quota-exceeded."""

    def __init__(self, backend: str, reset_seconds: float | None = None,
                 detail: str = "") -> None:
        super().__init__(f"{backend} rate-limited: {detail}")
        self.backend = backend
        self.reset_seconds = reset_seconds
        self.detail = detail


class NoBackendAvailable(RuntimeError):
    """Sollevato quando nessun provider configurato è utilizzabile."""


# =========================================================================
# Backend base
# =========================================================================
class BaseBackend:
    name: str = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def canonical_to_native(self, model: str) -> str:
        raise NotImplementedError

    def complete(self, *, model: str, system_prompt: str, user_prompt: str,
                 temperature: float) -> LLMResponse:
        raise NotImplementedError


def _parse_reset_string(v: Any) -> float | None:
    """Groq: 'x-ratelimit-reset-tokens' può essere '5.234s', '1m30s', ecc.

    Ritorna secondi come float. Se non riesce a parsare, None.
    """
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s:
        return None
    # forma numerica pura (secondi)
    try:
        return float(s)
    except ValueError:
        pass
    # formato composito: '1m30s', '250ms', '5.2s'
    total = 0.0
    m = re.match(r"^(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?$", s)
    if m:
        mins, secs, ms = m.groups()
        if mins:
            total += float(mins) * 60.0
        if secs:
            total += float(secs)
        if ms:
            total += float(ms) / 1000.0
        return total if total > 0 else None
    return None


# =========================================================================
# Groq backend
# =========================================================================
class GroqBackend(BaseBackend):
    name = "groq"

    # Mapping canonical → native. Il nome canonico è deliberatamente il più
    # neutro dei due (senza il prefisso 'openai/').
    _MODEL_MAP = {
        "gpt-oss-120b": "openai/gpt-oss-120b",
        "gpt-oss-20b": "openai/gpt-oss-20b",
        "llama-3.3-70b": "llama-3.3-70b-versatile",
        "llama-3.1-8b": "llama-3.1-8b-instant",
        "qwen3-32b": "qwen/qwen3-32b",
    }

    def __init__(self) -> None:
        self._client = None
        self._api_key = os.getenv("GROQ_API_KEY")

    def is_available(self) -> bool:
        return bool(self._api_key)

    def canonical_to_native(self, model: str) -> str:
        # Se il chiamante ha già passato il nome nativo, lasciamo passare.
        return self._MODEL_MAP.get(model, model)

    def _ensure_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        return self._client

    def complete(self, *, model: str, system_prompt: str, user_prompt: str,
                 temperature: float) -> LLMResponse:
        client = self._ensure_client()
        native = self.canonical_to_native(model)
        t0 = time.time()
        try:
            # with_raw_response ci dà accesso agli header di rate-limit.
            raw_resp = client.chat.completions.with_raw_response.create(
                model=native,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status_code", None)
            msg = str(e).lower()
            if status == 429 or "rate limit" in msg or "quota" in msg:
                raise _RateLimited(self.name, detail=str(e)[:200]) from e
            raise
        dt = int((time.time() - t0) * 1000)
        headers = getattr(raw_resp, "headers", {}) or {}
        parsed = raw_resp.parse()
        return _build_response(
            provider=self.name, model=model, native_model=native,
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, parsed=parsed, latency_ms=dt,
            headers=headers,
        )


# =========================================================================
# Cerebras backend
# =========================================================================
class CerebrasBackend(BaseBackend):
    name = "cerebras"

    _MODEL_MAP = {
        "gpt-oss-120b": "gpt-oss-120b",
        "gemma-4-31b": "gemma-4-31b",
    }

    def __init__(self) -> None:
        self._client = None
        self._api_key = os.getenv("CEREBRAS_API_KEY")

    def is_available(self) -> bool:
        return bool(self._api_key)

    def canonical_to_native(self, model: str) -> str:
        # Se il modello canonico non è mappato per Cerebras, ritorniamo il
        # nome così com'è: il provider risponderà con un errore chiaro se
        # non lo supporta (lo intercettiamo come non-rate-limit e non
        # tentiamo fallback in loop).
        return self._MODEL_MAP.get(model, model)

    def _ensure_client(self):
        if self._client is None:
            from cerebras.cloud.sdk import Cerebras
            self._client = Cerebras(api_key=self._api_key)
        return self._client

    def complete(self, *, model: str, system_prompt: str, user_prompt: str,
                 temperature: float) -> LLMResponse:
        client = self._ensure_client()
        native = self.canonical_to_native(model)
        t0 = time.time()
        try:
            raw_resp = client.chat.completions.with_raw_response.create(
                model=native,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "status_code", None)
            msg = str(e).lower()
            if status == 429 or "rate limit" in msg or "quota" in msg:
                raise _RateLimited(self.name, detail=str(e)[:200]) from e
            raise
        dt = int((time.time() - t0) * 1000)
        headers = getattr(raw_resp, "headers", {}) or {}
        parsed = raw_resp.parse()
        return _build_response(
            provider=self.name, model=model, native_model=native,
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, parsed=parsed, latency_ms=dt,
            headers=headers,
        )


# =========================================================================
# Helper condiviso per costruire la LLMResponse dal parsed SDK object
# =========================================================================
def _build_response(*, provider: str, model: str, native_model: str,
                    system_prompt: str, user_prompt: str, temperature: float,
                    parsed: Any, latency_ms: int, headers: dict) -> LLMResponse:
    raw = parsed.choices[0].message.content or ""
    cleaned = _THINK_RE.sub("", raw).strip()
    usage = getattr(parsed, "usage", None)

    def _hget(k: str) -> Any:
        # requests-style headers: case-insensitive; alcuni SDK ritornano dict
        # normali. Proviamo entrambe le forme.
        if hasattr(headers, "get"):
            v = headers.get(k) or headers.get(k.lower()) or headers.get(k.upper())
            return v
        return None

    remaining = _hget("x-ratelimit-remaining-tokens")
    reset = _parse_reset_string(_hget("x-ratelimit-reset-tokens"))

    return LLMResponse(
        text=cleaned,
        raw_text=raw,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
        provider=provider,
        model=model,
        native_model=native_model,
        request_fingerprint=request_fingerprint(model, system_prompt,
                                                user_prompt, temperature),
        latency_ms=latency_ms,
        remaining_tokens=int(remaining) if remaining is not None else None,
        reset_seconds=reset,
    )


# =========================================================================
# Client orchestratore multi-provider
# =========================================================================
class LLMClient:
    """Orchestratore multi-provider con fallback e rate-limit adattivo.

    L'API pubblica resta `.complete(system, user) -> LLMResponse` per
    compatibilità con gli agents esistenti. Sotto, prova i backend in
    ordine di priorità configurato; su rate-limit del primario passa al
    secondario. Prima di ogni chiamata al primario, se la remaining_tokens
    dell'ultima risposta è sotto la soglia, aspetta il reset (adaptive
    sleep) invece di sbattere contro il 429.
    """

    def __init__(
        self,
        model: str = config.MODEL,
        temperature: float = config.TEMPERATURE,
        provider_priority: list[str] | None = None,
        backends: list[BaseBackend] | None = None,
        low_water_tokens: int = 2000,
    ) -> None:
        self.model = model
        self.temperature = temperature
        # low_water_tokens: soglia sotto la quale il client aspetta il reset
        # invece di rischiare un 429. Valore conservativo: 2000 basta per un
        # planner/classifier medio.
        self.low_water_tokens = low_water_tokens

        # Costruzione backend
        if backends is not None:
            self._backends = backends
        else:
            priority = provider_priority or config.PROVIDER_PRIORITY
            all_backends = {"groq": GroqBackend(), "cerebras": CerebrasBackend()}
            self._backends = [all_backends[p] for p in priority
                              if p in all_backends and all_backends[p].is_available()]
        if not self._backends:
            raise NoBackendAvailable(
                "Nessun provider LLM configurato. Impostare GROQ_API_KEY "
                "e/o CEREBRAS_API_KEY in .env."
            )
        # Cache dell'ultima info di rate-limit per-backend (per adaptive sleep).
        self._last_info: dict[str, dict] = {}

    # --------- API pubblica -----------------------------------------
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        errors: list[str] = []
        fallback_from: list[str] = []
        for i, backend in enumerate(self._backends):
            # Adaptive sleep: se il backend è sotto-soglia da precedente risposta
            # e siamo su primario, aspetta invece di rischiare 429.
            if i == 0:
                self._maybe_wait_for_reset(backend)
            try:
                resp = backend.complete(
                    model=self.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.temperature,
                )
                # Registra info di rate-limit per il prossimo giro.
                self._last_info[backend.name] = {
                    "remaining_tokens": resp.remaining_tokens,
                    "reset_seconds": resp.reset_seconds,
                    "ts": time.time(),
                }
                if fallback_from:
                    resp.fallback_from = fallback_from
                return resp
            except _RateLimited as e:
                fallback_from.append(backend.name)
                errors.append(f"{backend.name}: {e.detail}")
                # marca il backend come "esausto" per lo sleep
                self._last_info[backend.name] = {
                    "remaining_tokens": 0,
                    "reset_seconds": e.reset_seconds,
                    "ts": time.time(),
                }
                continue
            except Exception as e:  # noqa: BLE001
                # Errore non-429: registra e passa al prossimo (potrebbe
                # essere un modello non disponibile su questo provider).
                fallback_from.append(backend.name)
                errors.append(f"{backend.name}: {type(e).__name__}: {str(e)[:200]}")
                continue

        # Tutti i backend hanno fallito.
        raise NoBackendAvailable(
            "Tutti i provider hanno fallito:\n- " + "\n- ".join(errors)
        )

    # --------- Adaptive sleep ---------------------------------------
    def _maybe_wait_for_reset(self, backend: BaseBackend) -> None:
        info = self._last_info.get(backend.name)
        if not info:
            return
        remaining = info.get("remaining_tokens")
        if remaining is None or remaining >= self.low_water_tokens:
            return
        # Sotto-soglia: aspetta il reset se conosciuto (bounded a 60s per
        # evitare stall imprevisti).
        reset = info.get("reset_seconds")
        if reset is None or reset <= 0:
            return
        elapsed = time.time() - info.get("ts", time.time())
        wait = max(0.0, min(60.0, reset - elapsed + 0.5))
        if wait > 0:
            time.sleep(wait)

    # --------- Introspection ----------------------------------------
    @property
    def active_backends(self) -> list[str]:
        return [b.name for b in self._backends]
