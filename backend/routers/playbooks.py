"""Playbooks router — analyst-defined agentic workflows.

A Playbook is an ordered list of Phases. Each Phase picks an agent skill (from
`agent/skills/` or user uploads in `agent/skills_user/`) and assembles its
inputs from datasets, scenarios, prior-phase outputs, or free-text prompts.
Optionally a Phase has a `gate` — the runner pauses for the analyst to approve,
modify, or reject the agent's output before continuing.

Run lifecycle (synchronous, request-driven):
- POST /playbooks/{id}/run  → executes phases until the first gate (or end).
- POST /runs/{run_id}/gate  → submits an approve/modify/reject decision and
                              resumes execution to the next gate (or end).
- POST /runs/{run_id}/publish → snapshots the final report into the function's
                                Published Reports registry.

If the orchestrator can't reach the LLM (the openai SDK couldn't resolve a
backend at request time), phases fail with the upstream error surfaced —
no mock fallback.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from agent.skill_loader import list_skills
from models.schemas import (
    GateDecisionRequest,
    PhaseExecution,
    Playbook,
    PlaybookCreate,
    PlaybookPhase,
    PlaybookRun,
    PlaybookUpdate,
    PublishedReport,
    PublishRequest,
    TraceStep,
)
from routers.auth import get_current_user, get_user_record
from routers.datasets import _DATASETS, _read_dataframe, _resolve_path, _synthesize_sample
from routers.scenarios import _SCENARIOS

router = APIRouter()


_PLAYBOOKS: dict[str, Playbook] = {}
_RUNS: dict[str, PlaybookRun] = {}
_PUBLISHED: dict[str, PublishedReport] = {}


# ── helpers ───────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _summarize_dataset(dataset_id: str) -> str | None:
    d = _DATASETS.get(dataset_id)
    if not d:
        return None
    parts = [f"`{d.name}` (id={d.id}) — {d.source_kind}, {len(d.columns)} columns"]
    cols = ", ".join(c.name for c in d.columns[:12])
    if cols:
        parts.append(f"columns: {cols}")
    if d.row_count:
        parts.append(f"rows: {d.row_count:,}")
    # Try to attach a small sample
    try:
        if d.source_kind == "upload" and d.file_path and d.file_format:
            df = _read_dataframe(_resolve_path(d), d.file_format).head(5)
        else:
            df = pd.DataFrame(_synthesize_sample(d.columns, 5))
        sample = df.to_string(index=False, max_cols=8, max_colwidth=18)
        parts.append("sample (first 5 rows):\n" + sample)
    except Exception:
        pass
    return "\n".join(parts)


def _summarize_scenario(scenario_id: str) -> str | None:
    s = _SCENARIOS.get(scenario_id)
    if not s:
        return None
    return (
        f"`{s.name}` (id={s.id}) — severity={s.severity}, "
        f"variables={s.variables}, horizon_months={s.horizon_months}"
    )


def _build_phase_context(
    phase: PlaybookPhase,
    run: PlaybookRun,
    function_id: str,
    playbook: Playbook,
) -> tuple[str, str]:
    """Return (extra_context, user_message) for the agent call."""
    ctx_parts: list[str] = [
        f"function_id: {function_id}",
        f"playbook: {playbook.name}",
        f"phase_id: {phase.id}",
        f"phase_name: {phase.name}",
    ]
    if playbook.description:
        ctx_parts.append(f"playbook_description: {playbook.description}")

    for inp in phase.inputs:
        if inp.kind == "dataset" and inp.ref_id:
            summary = _summarize_dataset(inp.ref_id)
            if summary:
                ctx_parts.append(f"--- input dataset ---\n{summary}")
        elif inp.kind == "scenario" and inp.ref_id:
            summary = _summarize_scenario(inp.ref_id)
            if summary:
                ctx_parts.append(f"--- input scenario ---\n{summary}")
        elif inp.kind == "phase_output" and inp.ref_id:
            prior = next((p for p in run.phases if p.phase_id == inp.ref_id), None)
            if prior and prior.output:
                ctx_parts.append(
                    f"--- output of prior phase `{inp.ref_id}` ({prior.phase_name}) ---\n"
                    + prior.output[:3000]
                )
        elif inp.kind == "prompt" and inp.text:
            ctx_parts.append(f"--- prompt ---\n{inp.text}")

    extra_context = "\n\n".join(ctx_parts)
    user_message = (
        phase.instructions
        or f"Execute phase '{phase.name}' using the inputs in the [Context]. "
           "Return a markdown report with headers, key numbers, and any recommendations."
    )
    return extra_context, user_message


async def _execute_phase(
    phase: PlaybookPhase,
    run: PlaybookRun,
    playbook: Playbook,
    pe: PhaseExecution,
) -> None:
    """Execute a phase, mutating the supplied PhaseExecution row in place.

    The row is the same object that lives in `run.phases[idx]`, so every state
    change (status, trace.append, output) becomes visible to GET pollers
    without a second copy step.
    """
    started = datetime.utcnow()
    pe.status = "running"
    pe.started_at = started.isoformat() + "Z"
    pe.error = None
    pe.output = None
    pe.trace = []
    extra_context, user_message = _build_phase_context(phase, run, playbook.function_id, playbook)

    # Late import to dodge any circular dependency
    from routers.chat import _ORCH

    if not _ORCH.available:
        pe.status = "failed"
        pe.error = (
            _ORCH.init_error
            or "LLM not reachable. Inside the corporate environment, no env vars are needed. Outside it, set OPENAI_API_KEY in backend/.env."
        )
        completed = datetime.utcnow()
        pe.completed_at = completed.isoformat() + "Z"
        pe.duration_ms = (completed - started).total_seconds() * 1000
        return

    def _on_step(step_dict: dict) -> None:
        """Live append: each tool call / output / message / handoff lands here
        as the agent emits it, so polling sees the trace grow during the run."""
        try:
            pe.trace.append(TraceStep(**step_dict))
        except Exception:
            pass  # never let a malformed step break the phase

    try:
        text, _final_trace = await _ORCH.chat_specialist_with_trace(
            phase.skill_name, user_message,
            extra_context=extra_context,
            on_step=_on_step,
        )
        pe.output = text
        pe.agent_id = phase.skill_name
        pe.status = "awaiting_gate" if phase.gate else "completed"
    except Exception as e:
        pe.status = "failed"
        pe.error = str(e)
    finally:
        completed = datetime.utcnow()
        pe.completed_at = completed.isoformat() + "Z"
        pe.duration_ms = (completed - started).total_seconds() * 1000


async def _run_to_next_gate(run: PlaybookRun, playbook: Playbook) -> None:
    """Execute phases starting at run.current_phase_idx, stopping at the next gate
    or at the end of the playbook (or on the first failure).

    Mutates `run.phases[idx]` in place so that GET pollers see partial progress
    (status flipping idle → running → completed, trace steps appended live)."""
    while run.current_phase_idx < len(playbook.phases) and run.status == "running":
        phase = playbook.phases[run.current_phase_idx]
        # The phase row is pre-populated by start_run / submit_gate; if for some
        # reason it isn't (legacy run data), create one and slot it in.
        if run.current_phase_idx >= len(run.phases):
            run.phases.append(PhaseExecution(
                phase_id=phase.id,
                phase_name=phase.name,
                skill_name=phase.skill_name,
                status="idle",
                duration_ms=0.0,
            ))
        pe = run.phases[run.current_phase_idx]
        await _execute_phase(phase, run, playbook, pe)

        if pe.status == "failed":
            run.status = "failed"
            run.completed_at = _now()
            return
        if pe.status == "awaiting_gate":
            run.status = "awaiting_gate"
            return
        # completed — advance
        run.current_phase_idx += 1

    # All phases consumed — finalise
    run.status = "completed"
    run.completed_at = _now()
    run.final_report = _build_final_report(run, playbook)


def _build_final_report(run: PlaybookRun, playbook: Playbook) -> str:
    lines: list[str] = [
        f"# {playbook.name}",
        "",
    ]
    if playbook.description:
        lines.append(f"_{playbook.description}_")
        lines.append("")
    lines.append(
        f"**Run id**: `{run.id}` &middot; "
        f"**Function**: `{run.function_id}` &middot; "
        f"**Status**: {run.status}"
    )
    lines.append("")
    for i, pe in enumerate(run.phases, start=1):
        phase_def = playbook.phases[i - 1] if i - 1 < len(playbook.phases) else None
        lines.append(f"## Phase {i}: {pe.phase_name}")
        lines.append(f"_Skill_: `{pe.skill_name}` &middot; _Duration_: {pe.duration_ms:.0f} ms")
        if pe.error:
            lines.append("")
            lines.append(f"> **Error**: {pe.error}")
        if pe.output:
            lines.append("")
            lines.append(pe.output)
        if pe.gate_decision:
            lines.append("")
            badge = {"approve": "✓ APPROVED", "modify": "✎ MODIFIED", "reject": "✗ REJECTED"}[pe.gate_decision]
            lines.append(f"> **Analyst gate**: {badge}")
            if pe.gate_notes:
                lines.append(f"> _{pe.gate_notes}_")
        lines.append("")
    return "\n".join(lines)


# ── route ordering: literal paths must come before /{playbook_id} ───────
# (FastAPI matches in registration order; otherwise /runs etc. get swallowed)

@router.get("/_skills")
async def list_available_skills(_: str = Depends(get_current_user)):
    """List loadable skill names for the phase skill picker."""
    return [
        {
            "name": s.name,
            "description": s.description,
            "source": s.source,
            "pack_id": s.pack_id,
            "color": s.color,
            "icon": s.icon,
        }
        for s in list_skills()
    ]


@router.get("/runs", response_model=list[PlaybookRun])
async def list_runs(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_RUNS.values())
    if function_id:
        items = [r for r in items if r.function_id == function_id]
    items.sort(key=lambda r: r.created_at, reverse=True)
    return items


@router.get("/runs/{run_id}", response_model=PlaybookRun)
async def get_run(run_id: str, _: str = Depends(get_current_user)):
    r = _RUNS.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return r


@router.post("/runs/{run_id}/gate", response_model=PlaybookRun)
async def submit_gate(
    run_id: str,
    req: GateDecisionRequest,
    _: str = Depends(get_current_user),
):
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_gate":
        raise HTTPException(status_code=400, detail=f"Run is not awaiting a gate (status={run.status})")
    pb = _PLAYBOOKS.get(run.playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Underlying playbook is gone")

    pe = run.phases[run.current_phase_idx]
    pe.gate_decision = req.decision
    pe.gate_notes = req.notes
    if req.decision == "modify" and req.modified_output:
        pe.output = req.modified_output

    if req.decision == "reject":
        pe.status = "rejected"
        run.status = "rejected"
        run.completed_at = _now()
        run.final_report = _build_final_report(run, pb)
        return run

    pe.status = "completed"
    run.current_phase_idx += 1
    run.status = "running"
    asyncio.create_task(_run_to_next_gate(run, pb))
    return run


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: str, _: str = Depends(get_current_user)):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    del _RUNS[run_id]


@router.post("/runs/{run_id}/publish", response_model=PublishedReport, status_code=201)
async def publish_run(
    run_id: str,
    req: PublishRequest,
    user: dict = Depends(get_user_record),
):
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("completed", "rejected"):
        raise HTTPException(status_code=400, detail="Can only publish completed or rejected runs")
    pb = _PLAYBOOKS.get(run.playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook is gone")
    body = run.final_report or _build_final_report(run, pb)

    pid = f"pbpub-{uuid.uuid4().hex[:10]}"
    rep = PublishedReport(
        id=pid,
        function_id=run.function_id,
        playbook_id=run.playbook_id,
        playbook_name=run.playbook_name,
        run_id=run.id,
        title=req.title or f"{pb.name} — {run.created_at[:10]}",
        body_markdown=body,
        published_by=user["username"],
        published_at=_now(),
    )
    _PUBLISHED[pid] = rep
    return rep


@router.get("/published", response_model=list[PublishedReport])
async def list_published(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_PUBLISHED.values())
    if function_id:
        items = [p for p in items if p.function_id == function_id]
    items.sort(key=lambda p: p.published_at, reverse=True)
    return items


@router.delete("/published/{report_id}", status_code=204)
async def delete_published(report_id: str, _: str = Depends(get_current_user)):
    if report_id not in _PUBLISHED:
        raise HTTPException(status_code=404, detail="Report not found")
    del _PUBLISHED[report_id]


# ── playbook CRUD (parameter routes registered last) ─────────────────────
@router.get("", response_model=list[Playbook])
async def list_playbooks(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_PLAYBOOKS.values())
    if function_id:
        items = [p for p in items if p.function_id == function_id]
    items.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
    return items


@router.get("/{playbook_id}", response_model=Playbook)
async def get_playbook(playbook_id: str, _: str = Depends(get_current_user)):
    p = _PLAYBOOKS.get(playbook_id)
    if not p:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return p


@router.post("", response_model=Playbook, status_code=201)
async def create_playbook(req: PlaybookCreate, _: str = Depends(get_current_user)):
    pid = f"pbk-{uuid.uuid4().hex[:10]}"
    # Re-id phases sequentially so they're predictable
    fixed_phases = [
        PlaybookPhase(**{**ph.model_dump(), "id": f"phase-{i + 1}"})
        for i, ph in enumerate(req.phases)
    ]
    pb = Playbook(
        id=pid,
        function_id=req.function_id,
        name=req.name,
        description=req.description,
        phases=fixed_phases,
        created_at=_now(),
    )
    _PLAYBOOKS[pid] = pb
    return pb


@router.patch("/{playbook_id}", response_model=Playbook)
async def update_playbook(
    playbook_id: str,
    req: PlaybookUpdate,
    _: str = Depends(get_current_user),
):
    p = _PLAYBOOKS.get(playbook_id)
    if not p:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if req.name is not None:
        p.name = req.name
    if req.description is not None:
        p.description = req.description
    if req.phases is not None:
        p.phases = [
            PlaybookPhase(**{**ph.model_dump(), "id": f"phase-{i + 1}"})
            for i, ph in enumerate(req.phases)
        ]
    p.updated_at = _now()
    return p


@router.delete("/{playbook_id}", status_code=204)
async def delete_playbook(playbook_id: str, _: str = Depends(get_current_user)):
    if playbook_id not in _PLAYBOOKS:
        raise HTTPException(status_code=404, detail="Playbook not found")
    del _PLAYBOOKS[playbook_id]


# ── runs ─────────────────────────────────────────────────────────────────
@router.post("/{playbook_id}/run", response_model=PlaybookRun, status_code=201)
async def start_run(playbook_id: str, _: str = Depends(get_current_user)):
    pb = _PLAYBOOKS.get(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    if not pb.phases:
        raise HTTPException(status_code=400, detail="Playbook has no phases")

    rid = f"pbr-{uuid.uuid4().hex[:10]}"
    # Pre-populate idle phase records so the frontend can render the timeline
    # immediately and show each one flip to "running" / "completed" as polling
    # picks up state.
    initial_phases = [
        PhaseExecution(
            phase_id=ph.id,
            phase_name=ph.name,
            skill_name=ph.skill_name,
            status="idle",
            duration_ms=0.0,
        )
        for ph in pb.phases
    ]
    run = PlaybookRun(
        id=rid,
        playbook_id=playbook_id,
        playbook_name=pb.name,
        function_id=pb.function_id,
        status="running",
        phases=initial_phases,
        current_phase_idx=0,
        created_at=_now(),
    )
    _RUNS[rid] = run
    # Fire-and-forget: the task mutates _RUNS[rid] as it goes, polling sees it.
    asyncio.create_task(_run_to_next_gate(run, pb))
    return run

