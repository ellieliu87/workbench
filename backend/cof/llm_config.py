"""LLM model selection for COF vs direct-OpenAI environments.

Inside the Capital One COF proxy environment the corporate `openai` SDK fork
auto-resolves the endpoint and auth, and `gpt-oss-120b` is the default model.
Outside that environment we fall back to direct OpenAI, where `gpt-oss-120b`
does not exist on the model catalog — `gpt-4o` is the equivalent default.

Skill `.md` frontmatter declares `model: gpt-oss-120b` (the COF default).
`resolve_model()` swaps that to `gpt-4o` only when we detect direct-OpenAI
mode, leaving any explicitly-non-default model name (e.g. a skill that pins
`gpt-4o-mini`) alone.
"""
from __future__ import annotations

import os

COF_DEFAULT_MODEL = "gpt-oss-120b"
OPENAI_DEFAULT_MODEL = "gpt-4o"


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
