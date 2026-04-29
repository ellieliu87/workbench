"""Internal tools pack — wires Capital One's corporate MCP servers into the
workbench so any skill can attach by id (e.g. `mcp_servers: [github]`).

For demo / dev environments the pack registers each server as a
**placeholder** when the corresponding `CMA_MCP_*_URL` env var is unset.
Placeholders appear in Settings → MCP Servers and the skill editor
picker (so the demo flow looks complete) but no real client is built —
attaching a skill to a placeholder is a runtime no-op until the URL is
configured. Set the env vars in `backend/.env` to upgrade a placeholder
to a live MCP client without any UI / pack changes.

Env vars (set any to flip the matching server from placeholder → live):

  CMA_MCP_GITHUB_URL          — GitHub MCP base URL
  CMA_MCP_GITHUB_TOKEN        — GitHub PAT / SAML token
  CMA_MCP_ONELAKE_URL         — OneLake MCP base URL
  CMA_MCP_ONELAKE_TOKEN       — OneLake auth token
  CMA_MCP_EXCHANGE_URL        — Exchange MCP (Kubeflow / batch jobs)
  CMA_MCP_EXCHANGE_TOKEN      — Exchange auth token
  CMA_MCP_JIRA_URL            — JIRA MCP base URL
  CMA_MCP_JIRA_TOKEN          — JIRA API token
"""
from __future__ import annotations

import os

from packs import Pack, PackContext


_DEMO_PREFIX = "[PLACEHOLDER — demo only, not connected to a real server] "


def _http_params(url: str, token: str | None) -> dict:
    """Default param shape for HTTP-transport MCP servers (SSE or
    Streamable). Adjust headers per-server if your gateways need extras."""
    params: dict = {"url": url}
    if token:
        params["headers"] = {"Authorization": f"Bearer {token}"}
    return params


def _register(
    ctx: PackContext,
    *,
    server_id: str,
    label: str,
    description: str,
    url_env: str,
    token_env: str,
    tool_filter: list[str] | None = None,
) -> None:
    """Register `server_id` as a real MCP server when its URL env var is
    set, otherwise as a placeholder so it still surfaces in the demo UI."""
    url = os.getenv(url_env, "").strip()
    if url:
        ctx.register_mcp_server(
            id=server_id,
            label=label,
            kind="streamable_http",
            params=_http_params(url, os.getenv(token_env)),
            description=description,
            tool_filter=tool_filter,
        )
    else:
        ctx.register_mcp_server(
            id=server_id,
            label=label,
            kind="streamable_http",
            params={"url": f"https://placeholder.example/mcp/{server_id}"},
            description=_DEMO_PREFIX + description,
            tool_filter=tool_filter,
            placeholder=True,
        )


def register(ctx: PackContext) -> None:
    ctx.pack = Pack(
        id="internal_tools",
        label="Internal MCP Tools",
        description=(
            "Adapters for Capital One's corporate MCP servers — GitHub, "
            "OneLake, Exchange (Kubeflow / batch), JIRA, and Snowflake. "
            "Skills attach by id under `mcp_servers:` in their YAML "
            "frontmatter. Demo mode: each server appears as a placeholder "
            "until its CMA_MCP_*_URL env var is set."
        ),
        # Available across every function — these are platform-wide tools,
        # not domain-specific.
        attach_to_functions=[],
        user_groups=[],
        color="#475569",
        icon="server",
    )

    # Skills shipped with this pack — release-engineer, etc.
    ctx.register_skill_dir()  # defaults to <pack_dir>/skills

    # ── GitHub ────────────────────────────────────────────────────────────
    _register(
        ctx,
        server_id="github",
        label="GitHub",
        description=(
            "Read PRs, commits, and CI status. Used by the "
            "release-engineer skill to link model artifacts back to "
            "the PRs that produced them."
        ),
        url_env="CMA_MCP_GITHUB_URL",
        token_env="CMA_MCP_GITHUB_TOKEN",
    )

    # ── OneLake ───────────────────────────────────────────────────────────
    _register(
        ctx,
        server_id="onelake",
        label="OneLake",
        description=(
            "Federated read access to OneLake tables. Used by the "
            "data-explainer and data-quality skills to query lake tables "
            "directly instead of going through CSV uploads."
        ),
        url_env="CMA_MCP_ONELAKE_URL",
        token_env="CMA_MCP_ONELAKE_TOKEN",
        # Lock down to read-only operations until lake writes are needed.
        tool_filter=["query", "describe_table", "list_tables", "preview"],
    )

    # ── Exchange (Kubeflow pipelines / batch jobs) ───────────────────────
    _register(
        ctx,
        server_id="exchange",
        label="Exchange (Kubeflow / Batch)",
        description=(
            "Submit and monitor Kubeflow pipelines and batch jobs on "
            "the enterprise platform. Used by the workflow runner so a "
            "saved analytics workflow can execute against production "
            "compute, and by the run-troubleshooter to fetch pod logs."
        ),
        url_env="CMA_MCP_EXCHANGE_URL",
        token_env="CMA_MCP_EXCHANGE_TOKEN",
    )

    # ── JIRA ──────────────────────────────────────────────────────────────
    _register(
        ctx,
        server_id="jira",
        label="JIRA",
        description=(
            "Open / update tickets and pull issue context. Used by "
            "run-troubleshooter to auto-file an incident when a "
            "production run fails, and by playbook gates to attach a "
            "ticket id to each phase's review."
        ),
        url_env="CMA_MCP_JIRA_URL",
        token_env="CMA_MCP_JIRA_TOKEN",
    )

    # ── Snowflake (extra placeholder for demo variety) ───────────────────
    _register(
        ctx,
        server_id="snowflake",
        label="Snowflake",
        description=(
            "Warehouse query access — query and describe tables. Used by "
            "the data-explainer skill when a dataset's source is bound to "
            "Snowflake instead of OneLake."
        ),
        url_env="CMA_MCP_SNOWFLAKE_URL",
        token_env="CMA_MCP_SNOWFLAKE_TOKEN",
        tool_filter=["query", "describe_table", "list_tables"],
    )
