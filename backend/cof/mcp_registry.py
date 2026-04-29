"""Live MCP server registry — built once at startup from pack attachments.

A pack registers MCP servers via `PackContext.register_mcp_server(...)`,
which appends a config dict to `packs._MCP_SERVER_ATTACHMENTS`. At
startup we walk that list, instantiate one client per entry using the
agents SDK's transport classes, and store them in `_MCP_SERVERS` keyed
by the short id the pack chose (e.g. "github", "onelake").

Skills opt in by listing those ids under `mcp_servers:` in their YAML
frontmatter. `CofBaseAgent` resolves the ids to live clients when it
constructs its `Agent`, and the agents SDK advertises every MCP tool to
the model alongside the skill's in-process Python tools.

Connection lifecycle: each MCP server connects lazily on first tool
call (the SDK handles that). We don't pool — one client per server is
sufficient for this app's traffic. If you grow to multi-tenant, swap in
a per-request connection wrapper.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("cma.cof.mcp")

# id → MCPServer instance (typed Any to avoid hard-importing the SDK at
# module load when MCP support is optional in some environments).
_MCP_SERVERS: dict[str, Any] = {}
_MCP_META: dict[str, dict] = {}


def register_pack_mcp_servers() -> None:
    """Instantiate every pack-registered MCP server. Idempotent — already
    registered ids are skipped on a re-call."""
    from packs import mcp_server_attachments
    try:
        from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp
    except ImportError:
        log.warning("agents SDK has no MCP support; pack MCP servers ignored.")
        return

    KIND_TO_CTOR = {
        "stdio": MCPServerStdio,
        "sse": MCPServerSse,
        "streamable_http": MCPServerStreamableHttp,
    }

    for att in mcp_server_attachments():
        sid = att["id"]
        if sid in _MCP_META:
            continue
        # Placeholder servers are listed in the UI but no real client is
        # built — useful for demos before the corporate URLs / tokens are
        # available. Attaching a skill to a placeholder is a no-op at run
        # time; the resolver returns nothing for the unconnected id.
        if att.get("placeholder"):
            _MCP_META[sid] = att
            log.info("[mcp:%s] registered as PLACEHOLDER (pack=%s)",
                     sid, att.get("pack_id", "?"))
            continue
        ctor = KIND_TO_CTOR.get(att["kind"])
        if ctor is None:
            log.error("[mcp:%s] unknown kind '%s' — skipping", sid, att["kind"])
            continue
        try:
            client = ctor(
                params=att["params"],
                name=att.get("label") or sid,
            )
        except Exception as e:
            log.error("[mcp:%s] init failed: %s", sid, e)
            continue
        _MCP_SERVERS[sid] = client
        _MCP_META[sid] = att
        log.info("[mcp:%s] registered (%s, pack=%s)",
                 sid, att["kind"], att.get("pack_id", "?"))


def get_mcp_server(server_id: str) -> Any | None:
    """Return the live MCP client for `server_id`, or None if unknown."""
    return _MCP_SERVERS.get(server_id)


def list_mcp_servers() -> list[dict]:
    """Used by Settings → MCP Servers to render available servers + which
    skills attach to which."""
    out = []
    for sid, meta in _MCP_META.items():
        out.append({
            "id": sid,
            "label": meta.get("label", sid),
            "kind": meta.get("kind"),
            "description": meta.get("description", ""),
            "pack_id": meta.get("pack_id"),
            "tool_filter": meta.get("tool_filter"),
            "placeholder": bool(meta.get("placeholder")),
            "connected": sid in _MCP_SERVERS,
        })
    return out


def resolve_mcp_servers_for_skill(server_ids: list[str]) -> list[Any]:
    """Map the list of ids on a skill's `mcp_servers:` frontmatter to the
    live MCP client objects that will be attached to its Agent. Unknown
    ids are dropped with a warning. Placeholder ids (registered for demo
    purposes only) are silently skipped — they're expected to be unbound."""
    out = []
    for sid in server_ids or []:
        client = _MCP_SERVERS.get(sid)
        if client is None:
            meta = _MCP_META.get(sid)
            if meta is None:
                log.warning("Skill referenced unknown MCP server '%s' — skipping.", sid)
            elif meta.get("placeholder"):
                log.debug("Skill attached placeholder MCP server '%s' — no live client.", sid)
            else:
                log.warning("Skill referenced offline MCP server '%s' — skipping.", sid)
            continue
        out.append(client)
    return out
