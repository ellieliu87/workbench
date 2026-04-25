"""Agent skills router - configure which capabilities the agent should expose.

A skill describes *what* the agent should do (system instructions + category +
the names of tools it should rely on). The actual tool implementations live in
the Python tool registry (see routers/tools.py). Skill.tools is a list of tool
names that, in a real LLM setup, would be advertised to the model as callable.
"""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from models.schemas import AgentSkill, AgentSkillCreate, AgentSkillUpdate
from routers.auth import get_current_user

router = APIRouter()


_SKILLS: dict[str, AgentSkill] = {}


SKILL_TEMPLATE = """# {{ skill_name }}

## Goal
Describe in one or two sentences what this skill accomplishes for the analyst.

## When to use
- Trigger phrase 1 (e.g. "explain how X is computed")
- Trigger phrase 2
- Trigger phrase 3

## Inputs
- Required: which page-context fields, KPIs, or pool/account IDs the agent needs.
- Optional: any analyst-supplied modifiers (date range, scenario, segment).

## Steps
1. Look up the underlying source from the metadata tool.
2. Pull the relevant rows / aggregates via `sql.query` or your custom tool.
3. Compute / compare / explain.
4. Return a markdown response with the answer and a short rationale.

## Output format
- Lead with the headline number or finding (bold, with units).
- Follow with a small markdown table of the key drivers.
- Close with a one-sentence interpretation.

## Tools this skill uses
- `tool_name_1` — what it does
- `tool_name_2` — what it does

## Guardrails
- Never invent numbers — if a tool fails, say so.
- Always cite the as-of date.
- If the analyst's question is ambiguous, ask one clarifying question, then proceed.
"""


def _seed():
    if _SKILLS:
        return
    seeds = [
        AgentSkill(
            id="sk-explain-metric",
            name="Explain Metric",
            description="Walks through how a KPI is computed, including source tables, joins, and weighting.",
            category="data",
            enabled=True,
            instructions="When asked 'how is X computed', respond with: source, formula, filters, as-of date.",
            tools=["sql_query", "metadata_lookup"],
        ),
        AgentSkill(
            id="sk-risk-monitor",
            name="Risk Limit Monitor",
            description="Compares current metrics to mandate limits and flags soft / hard breaches.",
            category="risk",
            enabled=True,
            instructions="Compare every visible KPI to its mandate limit and surface breaches.",
            tools=["limits_lookup", "alerting_send"],
        ),
        AgentSkill(
            id="sk-alco-report",
            name="ALCO Report",
            description="Drafts a one-page ALCO-ready memo from the visible KPIs and insights.",
            category="reporting",
            enabled=True,
            instructions="Use the formal ALCO template; lead with risk posture, then key metrics, then actions.",
            tools=["html_render"],
        ),
        AgentSkill(
            id="sk-rate-shock",
            name="Rate Shock Scenario",
            description="Runs parallel and twist shocks against the IRR and portfolio engines.",
            category="analytical",
            enabled=True,
            instructions="Default shocks: -200, -100, +100, +200, +300 bps parallel, plus a steepener and flattener.",
            tools=["scenario_parallel"],
        ),
        AgentSkill(
            id="sk-sql",
            name="Text-to-SQL",
            description="Translates analyst questions into SQL against the active warehouse.",
            category="data",
            enabled=False,
            instructions="Use Snowflake dialect by default; respect the analyst's role-based row filters.",
            tools=["sql_query"],
        ),
    ]
    for s in seeds:
        _SKILLS[s.id] = s


_seed()


def _render_template(skill_name: str) -> str:
    return SKILL_TEMPLATE.replace("{{ skill_name }}", skill_name or "Untitled Skill")


@router.get("/template")
async def get_template(name: str = "Untitled Skill", _: str = Depends(get_current_user)):
    return {"template": _render_template(name)}


@router.get("", response_model=list[AgentSkill])
async def list_skills(_: str = Depends(get_current_user)):
    return list(_SKILLS.values())


@router.get("/{skill_id}", response_model=AgentSkill)
async def get_skill(skill_id: str, _: str = Depends(get_current_user)):
    s = _SKILLS.get(skill_id)
    if not s:
        raise HTTPException(status_code=404, detail="Skill not found")
    return s


@router.post("", response_model=AgentSkill, status_code=201)
async def create_skill(req: AgentSkillCreate, _: str = Depends(get_current_user)):
    sid = f"sk-{uuid.uuid4().hex[:8]}"
    sk = AgentSkill(
        id=sid,
        name=req.name,
        description=req.description,
        category=req.category,
        enabled=True,
        instructions=req.instructions or _render_template(req.name),
        tools=req.tools,
    )
    _SKILLS[sid] = sk
    return sk


@router.patch("/{skill_id}", response_model=AgentSkill)
async def update_skill(skill_id: str, req: AgentSkillUpdate, _: str = Depends(get_current_user)):
    sk = _SKILLS.get(skill_id)
    if not sk:
        raise HTTPException(status_code=404, detail="Skill not found")
    update = req.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(sk, k, v)
    return sk


@router.patch("/{skill_id}/toggle", response_model=AgentSkill)
async def toggle_skill(skill_id: str, _: str = Depends(get_current_user)):
    sk = _SKILLS.get(skill_id)
    if not sk:
        raise HTTPException(status_code=404, detail="Skill not found")
    sk.enabled = not sk.enabled
    return sk


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, _: str = Depends(get_current_user)):
    if skill_id not in _SKILLS:
        raise HTTPException(status_code=404, detail="Skill not found")
    del _SKILLS[skill_id]


@router.post("/upload", response_model=AgentSkill, status_code=201)
async def upload_skill(
    file: Annotated[UploadFile, File()],
    _: str = Depends(get_current_user),
):
    contents = await file.read()
    sid = f"sk-upload-{uuid.uuid4().hex[:6]}"
    name = (file.filename or "Custom Skill").rsplit(".", 1)[0]
    sk = AgentSkill(
        id=sid,
        name=name,
        description=f"Uploaded skill manifest ({len(contents):,} bytes).",
        category="custom",
        enabled=False,
        instructions=contents.decode("utf-8", errors="replace")[:8000],
        tools=[],
    )
    _SKILLS[sid] = sk
    return sk
