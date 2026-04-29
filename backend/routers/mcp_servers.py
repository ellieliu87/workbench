"""MCP servers router — read-only listing for the Settings panel.

Returns one entry per pack-registered MCP server: id, label, kind,
description, pack id, connection state, and which skills opt in.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.skill_loader import list_skills
from cof.mcp_registry import list_mcp_servers
from routers.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_servers(_: str = Depends(get_current_user)):
    """Return registered MCP servers along with the skills that attach to
    each. Lets analysts see at a glance which corporate integrations are
    plumbed and which agents will use them."""
    servers = list_mcp_servers()
    # Build a reverse index: server_id → [skill names that use it]
    by_server: dict[str, list[dict]] = {s["id"]: [] for s in servers}
    for skill in list_skills():
        for sid in (skill.mcp_servers or []):
            if sid in by_server:
                by_server[sid].append({
                    "name": skill.name,
                    "source": skill.source,
                    "color": skill.color,
                    "icon": skill.icon,
                })
    for s in servers:
        s["skills"] = by_server.get(s["id"], [])
    return servers
