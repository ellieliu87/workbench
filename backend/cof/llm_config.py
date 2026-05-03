"""LLM model selection for COF vs direct-OpenAI environments.

Inside the Capital One COF proxy environment the corporate `openai` SDK fork
auto-resolves the endpoint and auth, and `gpt-oss-120b` is the default model.
Outside that environment we fall back to direct OpenAI, where `gpt-oss-120b`
does not exist on the model catalog — `gpt-4o` is the equivalent default.

Skill `.md` frontmatter declares `model: gpt-oss-120b` (the COF default).
`resolve_model()` swaps that to `gpt-4o` only when we detect direct-OpenAI
mode, leaving any explicitly-non-default model name (e.g. a skill that pins
`gpt-4o-mini`) alone.

This module also owns the **shared `AsyncOpenAI` client**. Every agent in
the system imports `get_async_client()` rather than instantiating its own
`AsyncOpenAI()` — that way the corporate COF proxy SDK only resolves auth
*once*, lazily on first use, instead of N times at startup (where N grows
with every loaded skill). Lazy construction also means the K8s
service-account token is read just before the first real API call, not at
backend boot — important when the token rotates between boot and first
chat.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("cma.llm_config")

COF_DEFAULT_MODEL = "gpt-oss-120b"
OPENAI_DEFAULT_MODEL = "gpt-4o"


# ── Shared AsyncOpenAI client ──────────────────────────────────────────────
_SHARED_CLIENT: Any = None


def get_async_client() -> Any:
    """Return the process-wide shared `AsyncOpenAI` client.

    Construction is lazy and cached — the corporate `openai` SDK fork
    (oasia / COF) reads the K8s service-account token at construction
    time, so we only want to do that once, *just before the first API
    call*, not 28× at backend startup.

    Match oasia exactly: `AsyncOpenAI()` with no arguments. The SDK
    auto-resolves `OPENAI_BASE_URL` / `OPENAI_API_KEY` from the
    environment in direct mode, and the corporate COF proxy resolves
    transparently inside the company network.
    """
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None:
        from openai import AsyncOpenAI
        _SHARED_CLIENT = AsyncOpenAI()
        log.info("Constructed shared AsyncOpenAI client")
    return _SHARED_CLIENT


def reset_async_client() -> None:
    """Drop the cached client so the next `get_async_client()` builds a
    fresh one. Use this when the COF proxy starts rejecting auth (e.g.
    the K8s SA token rotated and the cached client is stuck on the old
    one). Cheaper than restarting the pod.
    """
    global _SHARED_CLIENT
    _SHARED_CLIENT = None
    log.info("Shared AsyncOpenAI client reset; next call will construct fresh")


def is_openai_direct_mode() -> bool:
    """True when the OpenAI SDK will hit api.openai.com directly.

    Heuristic: an `sk-`-prefixed `OPENAI_API_KEY` with no `OPENAI_BASE_URL`
    or `COF_BASE_URL` override means we're outside the COF proxy. Inside
    COF the corporate SDK fork preconfigures the endpoint and these env
    vars are typically empty.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key.startswith("sk-"):
        return False
    if os.getenv("OPENAI_BASE_URL", "").strip():
        return False
    if os.getenv("COF_BASE_URL", "").strip():
        return False
    return True


def default_model() -> str:
    return OPENAI_DEFAULT_MODEL if is_openai_direct_mode() else COF_DEFAULT_MODEL


def resolve_model(declared: str | None) -> str:
    """Return the model to actually use, given a declaration from skill
    YAML or an env override. Swaps the COF default to the OpenAI default
    when in direct-OpenAI mode; passes any other explicit choice through.
    """
    if not declared:
        return default_model()
    if declared == COF_DEFAULT_MODEL and is_openai_direct_mode():
        return OPENAI_DEFAULT_MODEL
    return declared
