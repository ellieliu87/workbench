"""Chat router — routes analyst queries to a real LLM-backed agent team.

Connection priority:
  1. `COF_BASE_URL` (+ optional `COF_API_KEY`) — Capital One company endpoint, no key in UI
  2. `OPENAI_API_KEY` — direct OpenAI

If neither is set, every chat call returns a clear setup-required message
(NOT a mock). Set the env vars and restart the backend.

The backend pre-routes via the page context the frontend ships with each
message (tab + entity_kind + entity_id) so we usually go straight to the right
specialist without invoking the orchestrator's delegate-tools loop. When the
context isn't enough, we fall back to the orchestrator agent.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from agent.skill_loader import AgentSkill, list_skills
from cof.orchestrator import AsyncOrchestrator
from models.schemas import (
    AgentInfo,
    ChatAction,
    ChatMessage,
    ChatResponse,
)
from routers.auth import get_current_user

router = APIRouter()
log = logging.getLogger("cma.chat")

# Single shared orchestrator instance (skills reload from disk on demand)
_ORCH = AsyncOrchestrator()


# ── Routing (frontend context → specialist agent_id) ─────────────────────
def _route(req: ChatMessage) -> str:
    msg = (req.message or "").lower()

    if "error:" in msg or "traceback" in msg or "failed:" in msg:
        return "troubleshooter"
    if req.entity_kind == "kpi":
        return "kpi-explainer"
    if req.entity_kind == "dataset":
        return "data-quality"
    if req.entity_kind == "scenario":
        return "macro-economist"
    if req.entity_kind == "model":
        return "model-explainer"
    if req.entity_kind == "run":
        return "run-troubleshooter" if ("fail" in msg or "error" in msg) else "model-explainer"
    if req.entity_kind == "tile":
        # Tune if the user explicitly asked for filter / sort / change work,
        # otherwise default to the explainer (the Sparkles button on a tile).
        if any(k in msg for k in ("tune", "filter", "sort", "limit", "change", "modify")):
            return "tile-tuner"
        return "tile-explainer"
    if req.entity_kind == "workflow":
        return "workflow-validator"
    if req.tab == "data" and any(k in msg for k in ("quality", "anomal", "outlier", "null")):
        return "data-quality"
    if req.tab == "models" and "explain" in msg:
        return "model-explainer"
    if req.tab == "workflow":
        if "valid" in msg or "check" in msg or "make sense" in msg:
            return "workflow-validator"
        if "trouble" in msg or "fail" in msg or "error" in msg:
            return "run-troubleshooter"
        return "workflow-validator"
    if req.tab == "reporting":
        # Default Reporting-tab chat (no specific tile picked) → tile explainer.
        # Tune intent is handled above when entity_kind == 'tile'.
        return "tile-explainer"
    if req.tab == "analytics":
        # New self-serve analytics tab — no dedicated specialist yet, so route
        # to the orchestrator and let it pick or answer directly.
        return "orchestrator"
    return "orchestrator"


# ── Build context bundle for the LLM ─────────────────────────────────────
def _build_context(req: ChatMessage) -> str:
    parts: list[str] = []
    if req.function_id:
        parts.append(f"function_id: {req.function_id}")
    if req.tab:
        parts.append(f"tab: {req.tab}")
    if req.entity_kind:
        parts.append(f"entity_kind: {req.entity_kind}")
    if req.entity_id:
        parts.append(f"entity_id: {req.entity_id}")
    if req.context:
        parts.append(f"page_context: {req.context}")
    if req.payload:
        # Workflow validator passes nodes/edges in payload
        import json
        parts.append(f"payload: {json.dumps(req.payload, default=str)[:4000]}")
    return "\n".join(parts)


def _agent_meta(agent_id: str) -> tuple[str, str | None, str | None]:
    """Return (display_name, color, icon) for the responding agent."""
    skill = _ORCH.get_skill(agent_id)
    if skill:
        # If user uploaded their own version, show that name; otherwise use the skill's name
        name = skill.name
        return (name.replace("-", " ").title(), skill.color, skill.icon)
    return (agent_id.replace("-", " ").title(), None, None)


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(_: str = Depends(get_current_user)):
    """Return one AgentInfo per loaded skill — built-ins + user uploads."""
    out: list[AgentInfo] = []
    for s in list_skills():
        out.append(AgentInfo(
            id=s.name, name=s.name.replace("-", " ").title(),
            description=s.description,
            icon=s.icon or "sparkles",
            color=s.color or "#004977",
        ))
    return out


@router.post("/message", response_model=ChatResponse)
async def send_message(req: ChatMessage, _: str = Depends(get_current_user)):
    if not _ORCH.available:
        return ChatResponse(
            response=(
                "## LLM not configured\n\n"
                f"{_ORCH.init_error or 'Set COF_BASE_URL or OPENAI_API_KEY in backend/.env and restart.'}"
            ),
            agent_id="setup_required",
            agent_name="Setup Required",
            agent_color="#FF5C5C",
            agent_icon="alert-triangle",
        )

    target = _route(req)
    ctx = _build_context(req)

    try:
        if target == "orchestrator":
            text = await _ORCH.chat_orchestrator(req.message, extra_context=ctx)
        else:
            text = await _ORCH.chat_specialist(target, req.message, extra_context=ctx)
    except Exception as e:
        log.error("Chat call failed: %s", e)
        return ChatResponse(
            response=f"## Agent error\n\n```\n{e}\n```\nCheck the backend log for the full traceback.",
            agent_id="troubleshooter",
            agent_name="Troubleshooter",
            agent_color="#FF5C5C",
            agent_icon="life-buoy",
        )

    name, color, icon = _agent_meta(target)

    # The Tile Tuner emits action chips by calling apply_tile_filter — surface
    # those as ChatAction items so the frontend renders clickable filter chips.
    actions: list[ChatAction] = []
    if target == "tile-tuner" and req.entity_id:
        # Ask the agent's tool log for filters it just appended (we keep it simple
        # by inspecting the tile's current filter list pre/post is overkill —
        # the agent returns chip suggestions in markdown text and the analyst
        # can also click the saved filters indicator on the tile).
        pass  # filter actions are written via the tool itself; see tools.py:apply_tile_filter

    return ChatResponse(
        response=text,
        agent_id=target,
        agent_name=name,
        agent_color=color,
        agent_icon=icon,
        actions=actions,
    )


# Re-export the validation helper (kept for backwards compatibility with the
# scenarios.py /workflow-validate endpoint that imports from here).
from routers.chat_validation import validate_workflow_payload as _validate_workflow_payload  # noqa: F401
