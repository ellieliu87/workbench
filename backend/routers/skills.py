"""Agent Skills router — exposes built-in markdown skills + user uploads.

Listing: every `.md` in `agent/skills/` (built-in) and `agent/skills_user/`.
A user file with the same `name` as a built-in overrides it.

Upload: drop a `.md` file with the standard frontmatter; saved to
`agent/skills_user/<safe_name>.md`. Takes effect immediately on the next chat
call (the orchestrator reloads skills on demand).

Delete: only user uploads can be deleted; built-ins are read-only.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from agent.skill_loader import (
    USER_SKILLS_DIR,
    BUILTIN_SKILLS_DIR,
    AgentSkill,
    list_skills,
    load_all_skills,
    _parse_frontmatter,
)
from models.schemas import AgentSkill as AgentSkillSchema, AgentSkillCreate, AgentSkillUpdate
from packs import is_pack_visible
from routers.auth import get_current_user, get_current_user_groups

router = APIRouter()


def _to_schema(s: AgentSkill) -> AgentSkillSchema:
    """Adapt an AgentSkill (loader) into the wire-format schema."""
    cat_map = {
        "kpi-explainer": "data",
        "data-quality": "data",
        "model-explainer": "analytical",
        "workflow-validator": "analytical",
        "run-troubleshooter": "risk",
        "tile-tuner": "analytical",
        "troubleshooter": "risk",
        "orchestrator": "custom",
    }
    return AgentSkillSchema(
        id=s.name,
        name=s.name,
        description=s.description,
        category=cat_map.get(s.name, "custom"),  # type: ignore[arg-type]
        enabled=True,
        instructions=s.system_prompt,
        tools=s.tools,
        source=s.source,  # type: ignore[arg-type]
        pack_id=s.pack_id,
    )


def _safe_filename(name: str) -> str:
    norm = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    return f"{norm or 'skill'}.md"


def _is_user_skill(skill_name: str) -> bool:
    path = USER_SKILLS_DIR / f"{skill_name.replace('-', '_')}.md"
    return path.exists()


# ── Routes ───────────────────────────────────────────────────────────────
@router.get("", response_model=list[AgentSkillSchema])
async def get_skills(groups: list[str] = Depends(get_current_user_groups)):
    """List every skill the calling user is allowed to see.

    Universal (built-in / user) skills are always returned. Pack-scoped
    skills are filtered through `is_pack_visible(pack_id, groups)`."""
    return [
        _to_schema(s) for s in list_skills()
        if is_pack_visible(s.pack_id, groups)
    ]


@router.get("/_available_tools")
async def get_available_tools(_: str = Depends(get_current_user)):
    """Return the full catalog of tools a skill can declare.

    Two sources are merged:
      - **introspection** — tools exposed by `agent/tools.py` (get_workspace,
        get_dataset_preview, validate_workflow, …). These are baked into the
        agent runtime and always callable; the user can't add or remove them.
      - **python** — user-registered Python tools from the Tools tab. Source
        is either 'builtin' (sample) or 'user' (analyst-registered).

    The Skills editor needs both so it can show what's actually available
    to a skill, not just the user-registered subset."""
    # Lazy import to avoid pulling agent.tools at module load time.
    from agent.tools import OPENAI_TOOLS
    from routers.tools import _TOOLS as PYTHON_TOOLS

    intro = []
    for spec in OPENAI_TOOLS:
        fn = spec.get("function", spec)
        intro.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "kind": "introspection",
            "source": "builtin",
            "parameter_count": len((fn.get("parameters") or {}).get("properties", {})),
            "enabled": True,
        })

    py = []
    for t in PYTHON_TOOLS.values():
        py.append({
            "name": t.name,
            "description": t.description,
            "kind": "python",
            "source": getattr(t, "source", "user"),
            "parameter_count": len(t.parameters),
            "enabled": t.enabled,
        })

    intro.sort(key=lambda x: x["name"])
    py.sort(key=lambda x: (x["source"] != "user", x["name"]))
    return intro + py


@router.get("/template")
async def get_template(name: str = "my-skill", _: str = Depends(get_current_user)):
    """Return a skill markdown scaffold for analysts to start from."""
    template = f"""---
name: {name}
description: One-sentence summary of what this skill does for the analyst.
model: gpt-oss-120b
max_tokens: 1024
color: "#0891B2"
icon: sparkles
tools:
  - get_workspace
  - get_dataset_preview
quick_queries:
  - Brief me on this view
  - Explain the highlighted card
---

# {name.replace('-', ' ').title()}

Replace this body with your agent's system prompt.

## When to use
- Trigger phrase 1
- Trigger phrase 2

## Available tools
- `get_workspace` — fetch the live Overview snapshot for the current function
- `get_dataset_preview` — fetch a dataset's first N rows + dtypes
- (See `backend/agent/tools.py` for the full list)

## Output style
- Lead with numbers; pull them via tools, never invent.
- Use markdown headers and short bullets.
- Bold key metrics; prefix warnings with **⚠**.
- Keep responses under 200 words unless a table is needed.

## Guardrails
- If a tool errors, say so — don't fabricate.
- If the question is ambiguous, ask one clarifying question, then proceed.
"""
    return {"template": template}


@router.post("/upload", response_model=AgentSkillSchema, status_code=201)
async def upload_skill(
    file: Annotated[UploadFile, File()],
    _: str = Depends(get_current_user),
):
    """Upload a `.md` skill file. Overrides any built-in with the same `name`."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    if not file.filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="Skill files must be .md")

    contents = await file.read()
    text = contents.decode("utf-8", errors="replace")
    meta, _body = _parse_frontmatter(text)
    skill_name = meta.get("name", file.filename.rsplit(".", 1)[0])

    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = USER_SKILLS_DIR / _safe_filename(skill_name)
    out_path.write_text(text, encoding="utf-8")

    # Reload and return the now-active skill (which may be either user or builtin override)
    skills = load_all_skills()
    norm = skill_name.replace("-", "_").lower()
    s = skills.get(norm)
    if not s:
        raise HTTPException(status_code=400, detail="Skill saved but failed to load — check frontmatter syntax")

    # Hot-reload the orchestrator's view of skills
    try:
        from routers.chat import _ORCH
        _ORCH._reload_skills()  # type: ignore[attr-defined]
    except Exception:
        pass

    return _to_schema(s)


@router.post("", response_model=AgentSkillSchema, status_code=201)
async def create_skill(req: AgentSkillCreate, _: str = Depends(get_current_user)):
    """Compose a new skill from form fields (turns into a markdown file under skills_user/)."""
    skill_name = req.name.lower().replace(" ", "-")
    body = req.instructions or f"# {req.name}\n\nDescribe how this agent should behave."
    md = f"""---
name: {skill_name}
description: {req.description}
model: gpt-oss-120b
max_tokens: 1024
icon: sparkles
tools:
{chr(10).join(f'  - {t}' for t in req.tools) if req.tools else '  - get_workspace'}
---

{body}
"""
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = USER_SKILLS_DIR / _safe_filename(skill_name)
    out_path.write_text(md, encoding="utf-8")

    skills = load_all_skills()
    s = skills.get(skill_name.replace("-", "_"))
    if not s:
        raise HTTPException(status_code=400, detail="Skill failed to load after save")

    try:
        from routers.chat import _ORCH
        _ORCH._reload_skills()  # type: ignore[attr-defined]
    except Exception:
        pass
    return _to_schema(s)


@router.patch("/{skill_id}", response_model=AgentSkillSchema)
async def update_skill(skill_id: str, req: AgentSkillUpdate, _: str = Depends(get_current_user)):
    """Edit a skill — saves a user-override file even when the source was a built-in.

    This means the analyst's edits never lose the built-in version: deleting the
    user file via DELETE restores the built-in.
    """
    skills = load_all_skills()
    s = skills.get(skill_id.replace("-", "_").lower())
    if not s:
        raise HTTPException(status_code=404, detail="Skill not found")

    new_name = req.name or s.name
    new_desc = req.description or s.description
    new_instructions = req.instructions or s.system_prompt
    new_tools = req.tools if req.tools is not None else s.tools
    md = f"""---
name: {new_name.lower().replace(' ', '-')}
description: {new_desc}
model: {s.model}
max_tokens: {s.max_tokens}
{f'color: "{s.color}"' if s.color else ''}
{f'icon: {s.icon}' if s.icon else ''}
tools:
{chr(10).join(f'  - {t}' for t in new_tools) if new_tools else '  - get_workspace'}
---

{new_instructions}
"""
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = USER_SKILLS_DIR / _safe_filename(new_name)
    out_path.write_text(md, encoding="utf-8")

    skills = load_all_skills()
    s2 = skills.get(new_name.replace("-", "_").lower())
    try:
        from routers.chat import _ORCH
        _ORCH._reload_skills()  # type: ignore[attr-defined]
    except Exception:
        pass
    return _to_schema(s2 or s)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, _: str = Depends(get_current_user)):
    """Delete a user override. Built-in skills cannot be deleted."""
    norm = skill_id.replace("-", "_").lower()
    user_path = USER_SKILLS_DIR / f"{norm}.md"
    if user_path.exists():
        user_path.unlink()
        try:
            from routers.chat import _ORCH
            _ORCH._reload_skills()  # type: ignore[attr-defined]
        except Exception:
            pass
        return
    builtin_path = BUILTIN_SKILLS_DIR / f"{norm}.md"
    if builtin_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Built-in skills are read-only. Edit it to create a user override that hides the built-in, or upload a custom version.",
        )
    raise HTTPException(status_code=404, detail="Skill not found")


@router.patch("/{skill_id}/toggle", response_model=AgentSkillSchema)
async def toggle_skill(skill_id: str, _: str = Depends(get_current_user)):
    """Toggle is a no-op now — every loaded skill is enabled. Returned for API compatibility."""
    skills = load_all_skills()
    s = skills.get(skill_id.replace("-", "_").lower())
    if not s:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _to_schema(s)
