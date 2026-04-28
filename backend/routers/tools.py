"""Python tool registry - users can register Python functions as agent tools.

Each tool stores its source code, a JSON-schema-shaped parameter list, and the
name of the entry-point function. The /test endpoint runs the function in a
fresh subprocess with a timeout; this is good enough for a local workbench but
NOT a hardened sandbox: production deployments should add an imports allowlist,
seccomp / cgroup limits, and a non-privileged user. (See _run_tool below.)
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from cof.llm_config import resolve_model
from models.schemas import (
    PythonTool,
    PythonToolCreate,
    PythonToolUpdate,
    ToolDraftRequest,
    ToolDraftResponse,
    ToolParameter,
    ToolTestRequest,
    ToolTestResponse,
)
from packs import is_pack_visible
from routers.auth import get_current_user, get_current_user_groups

router = APIRouter()


_TOOLS: dict[str, PythonTool] = {}

DEFAULT_SOURCE = '''def my_tool(symbol: str, lookback_days: int = 30):
    """Example tool — replace with your own logic.

    Returns a small dict the agent can summarize.
    """
    return {
        "symbol": symbol,
        "lookback_days": lookback_days,
        "note": "Replace this body with a real lookup against your data source.",
    }
'''


def _seed():
    if _TOOLS:
        return
    builtin_seeds = [
        PythonTool(
            id="tool-sql-query",
            name="sql_query",
            description="Run a read-only SQL query against the active data source and return the rows.",
            parameters=[
                {"name": "sql", "type": "string", "description": "The SQL query to execute (read-only).", "required": True},
                {"name": "limit", "type": "integer", "description": "Max rows to return.", "required": False},
            ],
            python_source=(
                'def sql_query(sql: str, limit: int = 100):\n'
                '    """Mock SQL runner. Replace with snowflake/onelake driver."""\n'
                '    return {"rows_returned": min(limit, 42), "preview": ["row_1", "row_2", "row_3"], "sql": sql}\n'
            ),
            function_name="sql_query",
            enabled=True,
            source="builtin",
        ),
        PythonTool(
            id="tool-metadata-lookup",
            name="metadata_lookup",
            description="Return data-lineage metadata for a metric: source table, formula, as-of.",
            parameters=[
                {"name": "metric", "type": "string", "description": "Name of the metric to look up.", "required": True},
            ],
            python_source=(
                'def metadata_lookup(metric: str):\n'
                '    """Mock metadata lookup."""\n'
                '    return {\n'
                '        "metric": metric,\n'
                '        "source": "cma_warehouse.fact_positions",\n'
                '        "formula": "weighted by market_value",\n'
                '        "as_of": "EOD prior business day",\n'
                '    }\n'
            ),
            function_name="metadata_lookup",
            enabled=True,
            source="builtin",
        ),
        PythonTool(
            id="tool-scenario-parallel",
            name="scenario_parallel",
            description="Apply a parallel rate shock and return the EVE % impact.",
            parameters=[
                {"name": "shock_bps", "type": "integer", "description": "Parallel shock in bps (e.g. 200, -100).", "required": True},
            ],
            python_source=(
                'def scenario_parallel(shock_bps: int):\n'
                '    """Mock EVE shock — illustrative quadratic in shock_bps."""\n'
                '    eve = -0.01 * shock_bps - 0.000005 * (shock_bps ** 2)\n'
                '    return {"shock_bps": shock_bps, "eve_pct": round(eve * 100, 2)}\n'
            ),
            function_name="scenario_parallel",
            enabled=True,
            source="builtin",
        ),
    ]
    for t in builtin_seeds:
        _TOOLS[t.id] = t

    # Pull in pack-registered tools (each domain pack registers its tools at
    # startup via PackContext.register_python_tool; the seeds end up in
    # `packs.python_tool_seeds()`).
    _ingest_pack_seeds()


def _ingest_pack_seeds() -> None:
    """Idempotent — pack-registered tools land in `_TOOLS` keyed by id.
    Safe to call again after `discover_and_register()` runs."""
    from packs import python_tool_seeds
    for s in python_tool_seeds():
        if s["id"] in _TOOLS:
            continue
        _TOOLS[s["id"]] = PythonTool(**s)




_seed()


def _validate_source(source: str, function_name: str) -> tuple[bool, str | None]:
    """Parse the source with ast and check the named function is defined."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return True, None
    return False, f"Function '{function_name}' is not defined in the source."


def _run_tool(source: str, function_name: str, args: dict[str, Any], timeout: float = 5.0) -> ToolTestResponse:
    """Execute the tool in a subprocess with a timeout.

    NOT a real sandbox — this only buys process isolation and a wall-clock cap.
    For production, add: imports allowlist, resource limits (RLIMIT_*), seccomp,
    chroot or container, and a non-privileged user.
    """
    harness = (
        "import json, sys, traceback\n"
        "\n"
        "# === user source begins ===\n"
        f"{source}\n"
        "# === user source ends ===\n"
        "\n"
        "try:\n"
        "    args = json.loads(sys.stdin.read() or '{}')\n"
        f"    result = {function_name}(**args)\n"
        "    sys.stdout.write('__CMA_RESULT__:' + json.dumps({'ok': True, 'result': result}, default=str))\n"
        "except Exception as e:\n"
        "    sys.stdout.write('__CMA_RESULT__:' + json.dumps({\n"
        "        'ok': False, 'error': str(e), 'traceback': traceback.format_exc()\n"
        "    }))\n"
    )

    fd, path = tempfile.mkstemp(suffix=".py")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(harness)

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, path],
            input=json.dumps(args),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ToolTestResponse(ok=False, error=f"Timed out after {timeout}s", duration_ms=timeout * 1000)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    duration_ms = (time.perf_counter() - started) * 1000

    if completed.returncode != 0:
        return ToolTestResponse(
            ok=False,
            error=f"Subprocess exited with code {completed.returncode}",
            traceback=(completed.stderr or completed.stdout)[-4000:],
            duration_ms=duration_ms,
        )

    out = completed.stdout
    marker = "__CMA_RESULT__:"
    idx = out.rfind(marker)
    if idx == -1:
        return ToolTestResponse(ok=False, error="Tool produced no result envelope", traceback=out[-4000:], duration_ms=duration_ms)
    try:
        payload = json.loads(out[idx + len(marker):].strip())
    except json.JSONDecodeError as e:
        return ToolTestResponse(ok=False, error=f"Could not parse result: {e}", traceback=out[-4000:], duration_ms=duration_ms)

    return ToolTestResponse(
        ok=bool(payload.get("ok")),
        result=payload.get("result"),
        error=payload.get("error"),
        traceback=payload.get("traceback"),
        duration_ms=duration_ms,
    )


@router.get("/template")
async def get_template(_: str = Depends(get_current_user)):
    return {"python_source": DEFAULT_SOURCE, "function_name": "my_tool"}


_DRAFT_SYSTEM_PROMPT = """You are a senior Python engineer helping an analyst draft a single
Python function that will be registered as an agent tool in the CMA Workbench.

You produce ONE pure Python function only. It must:
- Use only the standard library (no third-party imports).
- Have explicit type hints on every parameter and on the return type.
- Have a one-line docstring summarizing what it does.
- Return a JSON-serializable result (dict / list / str / number / bool).
- Be deterministic — no randomness, no time-dependent behavior unless required.
- Avoid network calls, file IO outside `tempfile`, and `os.system` / `subprocess` shell calls.
- Keep the body short (under ~40 lines). If the task needs more, summarize the
  approach in `notes` and keep the body to a clean skeleton.

You respond with STRICT JSON matching this schema (no markdown, no prose):

{
  "name":          string  // snake_case, the public tool name
  "description":   string  // ONE sentence describing what it does
  "function_name": string  // matches `name` exactly
  "parameters":    [ { "name": string, "type": "string"|"integer"|"number"|"boolean"|"object"|"array",
                       "description": string, "required": boolean } ]
  "python_source": string  // the full `def ...:` definition, ready to paste into an editor
  "notes":         string  // optional caveats, e.g. "stub data — replace with real query"
}

If the analyst's request is ambiguous, pick a sensible interpretation and mention
your assumptions in `notes`. Never refuse — produce a working starting point even
if the spec is fuzzy."""


@router.post("/draft", response_model=ToolDraftResponse)
async def draft_tool(req: ToolDraftRequest, _: str = Depends(get_current_user)):
    """Ask the LLM to draft a Python tool from a plain-English description.

    Returns a structured draft the analyst can review, edit, test, and save.
    Uses the same OpenAI/COF connection the orchestrator uses; if neither is
    configured, returns 503 with a setup-required message.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed.")

    # Match oasia: AsyncOpenAI() with no arguments. The SDK auto-resolves
    # OPENAI_BASE_URL / OPENAI_API_KEY from the environment; corporate COF
    # proxy environments preconfigure these so no env vars need to be set.
    client = AsyncOpenAI()

    user_msg = req.prompt.strip()
    if req.context:
        user_msg += f"\n\n[Additional context]\n{req.context.strip()}"

    try:
        completion = await client.chat.completions.create(
            model=resolve_model(os.getenv("CMA_TOOL_DRAFT_MODEL")),
            messages=[
                {"role": "system", "content": _DRAFT_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    raw = completion.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"LLM returned non-JSON: {e}")

    # Normalize and validate the agent's draft before returning. We are lenient
    # — accept missing optional fields, reject only on clearly-broken outputs.
    name = (data.get("name") or "").strip()
    fn_name = (data.get("function_name") or name).strip() or "my_tool"
    if not name:
        name = fn_name
    description = (data.get("description") or "").strip() or "Generated tool"
    raw_params = data.get("parameters") or []
    params: list[ToolParameter] = []
    for p in raw_params:
        if not isinstance(p, dict) or "name" not in p:
            continue
        ptype = p.get("type", "string")
        if ptype not in ("string", "integer", "number", "boolean", "object", "array"):
            ptype = "string"
        params.append(ToolParameter(
            name=str(p["name"]),
            type=ptype,
            description=str(p.get("description") or "") or None,
            required=bool(p.get("required", True)),
        ))
    source = data.get("python_source") or ""
    if not source.strip():
        raise HTTPException(status_code=502, detail="LLM returned empty python_source.")

    # Sanity-check the source parses and defines fn_name. If not, surface that
    # to the analyst as a `notes` warning rather than rejecting — they may
    # still want to see what the agent produced and fix it themselves.
    notes = data.get("notes")
    ok, err = _validate_source(source, fn_name)
    if not ok:
        warning = f"Draft validation: {err}"
        notes = f"{notes}\n{warning}" if notes else warning

    return ToolDraftResponse(
        name=name,
        description=description,
        function_name=fn_name,
        parameters=params,
        python_source=source,
        notes=notes,
    )


@router.get("", response_model=list[PythonTool])
async def list_tools(groups: list[str] = Depends(get_current_user_groups)):
    """Pack-scoped tools are filtered by the user's groups; universal
    (`builtin` / `user`) tools are always returned."""
    return [t for t in _TOOLS.values() if is_pack_visible(t.pack_id, groups)]


@router.get("/{tool_id}", response_model=PythonTool)
async def get_tool(tool_id: str, _: str = Depends(get_current_user)):
    t = _TOOLS.get(tool_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tool not found")
    return t


@router.post("", response_model=PythonTool, status_code=201)
async def create_tool(req: PythonToolCreate, _: str = Depends(get_current_user)):
    ok, err = _validate_source(req.python_source, req.function_name)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    tid = f"tool-{uuid.uuid4().hex[:8]}"
    t = PythonTool(id=tid, enabled=True, **req.model_dump())
    _TOOLS[tid] = t
    return t


@router.patch("/{tool_id}", response_model=PythonTool)
async def update_tool(tool_id: str, req: PythonToolUpdate, _: str = Depends(get_current_user)):
    t = _TOOLS.get(tool_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tool not found")
    update = req.model_dump(exclude_unset=True)
    if "python_source" in update or "function_name" in update:
        new_source = update.get("python_source", t.python_source)
        new_fn = update.get("function_name", t.function_name)
        ok, err = _validate_source(new_source, new_fn)
        if not ok:
            raise HTTPException(status_code=400, detail=err)
    for k, v in update.items():
        setattr(t, k, v)
    return t


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(tool_id: str, _: str = Depends(get_current_user)):
    if tool_id not in _TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    del _TOOLS[tool_id]


@router.patch("/{tool_id}/toggle", response_model=PythonTool)
async def toggle_tool(tool_id: str, _: str = Depends(get_current_user)):
    t = _TOOLS.get(tool_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tool not found")
    t.enabled = not t.enabled
    return t


@router.post("/{tool_id}/test", response_model=ToolTestResponse)
async def test_tool(tool_id: str, req: ToolTestRequest, _: str = Depends(get_current_user)):
    t = _TOOLS.get(tool_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tool not found")
    res = _run_tool(t.python_source, t.function_name, req.args)
    t.last_test_result = res.model_dump()
    return res
