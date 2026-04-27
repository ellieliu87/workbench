"""Self-serve Analytics router — user-defined analytic definitions.

Three primitives, each described by a small JSON spec:

* `aggregate`      — group-by + measures (sum/avg/weighted_avg/percentile/...)
* `compare`        — same metric across two slices (period A vs. B, dataset
                     A vs. B, etc.) → delta + % change
* `custom_python`  — escape hatch: user supplies a Python function that
                     receives input DataFrames and returns a structured
                     `{table, chart, kpis}` dict

Definitions are persisted in-memory keyed by id. Each run is recorded as an
`AnalyticDefinitionRun` and surfaced in the tab's history. The agent-assist
endpoints (`/draft`, `/runs/{id}/narrate`) use a direct `AsyncOpenAI` call
with JSON-mode response so the spec can be auto-populated from prose, and
results can carry a one-paragraph narrative the analyst can pin.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query

from models.schemas import (
    AggregateMeasure,
    AggregateSpec,
    AnalyticDefinition,
    AnalyticDefinitionCreate,
    AnalyticDefinitionRun,
    AnalyticDefinitionUpdate,
    AnalyticDraftRequest,
    AnalyticDraftResponse,
    AnalyticInputs,
    AnalyticNarrationResponse,
    AnalyticOutput,
    AnalyticResult,
    AnalyticResultChart,
    AnalyticResultKpi,
    AnalyticResultTable,
    CompareSpec,
    CustomPythonSpec,
)
from routers.auth import get_current_user
from routers.datasets import _DATASETS, _read_dataframe, _resolve_path

router = APIRouter()

_DEFS: dict[str, AnalyticDefinition] = {}
_RUNS: dict[str, AnalyticDefinitionRun] = {}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ── DataFrame loading ──────────────────────────────────────────────────────
def _df_for_dataset(dataset_id: str) -> pd.DataFrame:
    d = _DATASETS.get(dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    try:
        path = _resolve_path(d)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve dataset path: {e}")
    fmt = (d.file_format or "csv").lower()
    try:
        return _read_dataframe(Path(path), fmt)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read dataset {dataset_id}: {e}")


# ── Filter application (used by aggregate + compare) ───────────────────────
def _apply_filters(df: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    if not filters:
        return df
    out = df
    for f in filters:
        col = f.get("column")
        op = (f.get("op") or "eq").lower()
        val = f.get("value")
        if not col or col not in out.columns:
            continue
        try:
            if op == "eq":
                out = out[out[col] == val]
            elif op == "ne":
                out = out[out[col] != val]
            elif op == "gt":
                out = out[out[col] > val]
            elif op == "gte":
                out = out[out[col] >= val]
            elif op == "lt":
                out = out[out[col] < val]
            elif op == "lte":
                out = out[out[col] <= val]
            elif op == "in":
                vs = val if isinstance(val, list) else [val]
                out = out[out[col].isin(vs)]
            elif op == "contains":
                out = out[out[col].astype(str).str.contains(str(val), case=False, na=False)]
        except Exception:
            # filter that doesn't apply cleanly is silently dropped — better
            # to render *something* than to fail the whole run.
            pass
    return out


# ── Aggregation ────────────────────────────────────────────────────────────
_AGG_FNS = {
    "sum":   lambda s: s.sum(),
    "avg":   lambda s: s.mean(),
    "count": lambda s: s.count(),
    "min":   lambda s: s.min(),
    "max":   lambda s: s.max(),
    "median": lambda s: s.median(),
    "p25":   lambda s: s.quantile(0.25),
    "p75":   lambda s: s.quantile(0.75),
    "p90":   lambda s: s.quantile(0.90),
    "p99":   lambda s: s.quantile(0.99),
    "stddev": lambda s: s.std(),
}


def _measure_alias(m: AggregateMeasure) -> str:
    return m.alias or f"{m.agg}_{m.column}"


def _apply_aggregate(df: pd.DataFrame, spec: AggregateSpec) -> pd.DataFrame:
    df = _apply_filters(df, spec.filters)
    if not spec.measures:
        # No measures = just count rows by group
        if spec.group_by:
            out = df.groupby(spec.group_by, dropna=False).size().reset_index(name="row_count")
        else:
            out = pd.DataFrame([{"row_count": len(df)}])
    elif spec.group_by:
        cols_needed = set(spec.group_by)
        for m in spec.measures:
            cols_needed.add(m.column)
            if m.weight_by:
                cols_needed.add(m.weight_by)
        missing = cols_needed - set(df.columns)
        if missing:
            raise HTTPException(status_code=400, detail=f"Columns not in dataset: {sorted(missing)}")

        groups = df.groupby(spec.group_by, dropna=False)
        result_records: list[dict[str, Any]] = []
        for keys, sub in groups:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row: dict[str, Any] = {k: v for k, v in zip(spec.group_by, keys)}
            for m in spec.measures:
                row[_measure_alias(m)] = _eval_measure(sub, m)
            result_records.append(row)
        out = pd.DataFrame(result_records)
    else:
        # No group-by: a single row of measure values
        row: dict[str, Any] = {}
        for m in spec.measures:
            row[_measure_alias(m)] = _eval_measure(df, m)
        out = pd.DataFrame([row])

    if spec.sort_by and spec.sort_by in out.columns:
        out = out.sort_values(spec.sort_by, ascending=not spec.sort_desc, kind="mergesort")
    if spec.limit and spec.limit > 0:
        out = out.head(int(spec.limit))
    return out.reset_index(drop=True)


_NUMERIC_AGGS = {"sum", "avg", "min", "max", "median", "p25", "p75", "p90", "p99",
                 "weighted_avg", "stddev"}


def _is_numeric_series(s: pd.Series) -> bool:
    """Best-effort: is this column actually numeric? `pd.to_numeric(coerce)`
    can silently turn a string column into all-NaN, which then makes a sum
    or mean look like '0' or 'null' — so we explicitly reject string columns
    on numeric aggregators rather than papering over the bug."""
    if pd.api.types.is_numeric_dtype(s):
        return True
    # Mixed-object columns can still be valid numerics (CSVs read as object
    # with numeric content). Try a coerce and require >50% non-NaN.
    coerced = pd.to_numeric(s, errors="coerce")
    return float(coerced.notna().mean()) > 0.5


def _eval_measure(sub: pd.DataFrame, m: AggregateMeasure):
    if not m.column:
        raise HTTPException(
            status_code=400,
            detail=f"Measure has no column selected (agg={m.agg!r}). "
                   f"Pick a numeric column to {m.agg} on.",
        )
    if m.column not in sub.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Measure column {m.column!r} not in dataset",
        )
    series = sub[m.column]

    # Reject numeric aggs on non-numeric columns up-front so the user gets
    # a clear "wrong column type" message instead of a silent NaN cell.
    if m.agg in _NUMERIC_AGGS and not _is_numeric_series(series):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {m.agg} column {m.column!r} — it isn't numeric "
                   f"(dtype={series.dtype}). Use 'count' for non-numeric "
                   f"columns, or pick a different column.",
        )

    if m.agg == "weighted_avg":
        if not m.weight_by:
            raise HTTPException(status_code=400, detail=f"weighted_avg requires weight_by ({m.column})")
        if m.weight_by not in sub.columns:
            raise HTTPException(status_code=400, detail=f"weight_by column {m.weight_by!r} not in dataset")
        w = sub[m.weight_by]
        if not _is_numeric_series(w):
            raise HTTPException(status_code=400, detail=f"weight_by column {m.weight_by!r} isn't numeric")
        s = pd.to_numeric(series, errors="coerce")
        wn = pd.to_numeric(w, errors="coerce")
        mask = (~s.isna()) & (~wn.isna())
        if not mask.any() or wn[mask].sum() == 0:
            return None
        return float((s[mask] * wn[mask]).sum() / wn[mask].sum())
    fn = _AGG_FNS.get(m.agg)
    if not fn:
        raise HTTPException(status_code=400, detail=f"Unknown aggregator: {m.agg}")
    val = fn(pd.to_numeric(series, errors="coerce") if m.agg != "count" else series)
    if pd.isna(val):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


# ── Primitive runners ──────────────────────────────────────────────────────
def _run_aggregate(d: AnalyticDefinition) -> AnalyticResult:
    if not d.aggregate_spec:
        raise HTTPException(status_code=400, detail="aggregate_spec missing")
    if not d.inputs.dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id required")
    df = _df_for_dataset(d.inputs.dataset_id)
    out_df = _apply_aggregate(df, d.aggregate_spec)
    return _result_from_df(out_df, d.output)


def _run_compare(d: AnalyticDefinition) -> AnalyticResult:
    if not d.compare_spec:
        raise HTTPException(status_code=400, detail="compare_spec missing")
    if not d.inputs.dataset_id or not d.inputs.dataset_id_b:
        raise HTTPException(
            status_code=400,
            detail=(
                "Compare needs two datasets — pick both Dataset A and "
                "Dataset B in the editor. If you only want to compare "
                "two measures inside a single dataset, switch the kind "
                "to Aggregate and add multiple measures."
            ),
        )
    if d.inputs.dataset_id == d.inputs.dataset_id_b:
        raise HTTPException(
            status_code=400,
            detail=(
                "Compare requires two DIFFERENT datasets — Dataset A and "
                "Dataset B point at the same id. Pick a different B, or "
                "switch the kind to Aggregate."
            ),
        )
    df_a = _df_for_dataset(d.inputs.dataset_id)
    df_b = _df_for_dataset(d.inputs.dataset_id_b)
    spec = d.compare_spec
    inner = AggregateSpec(
        group_by=spec.group_by,
        measures=[spec.measure],
        filters=[],
        sort_by=None,
        limit=None,
    )
    a = _apply_aggregate(df_a, inner)
    b = _apply_aggregate(df_b, inner)
    measure_alias = _measure_alias(spec.measure)
    a = a.rename(columns={measure_alias: spec.label_a})
    b = b.rename(columns={measure_alias: spec.label_b})
    if spec.group_by:
        merged = a.merge(b, on=spec.group_by, how="outer")
    else:
        merged = pd.concat([a.reset_index(drop=True), b.reset_index(drop=True)], axis=1)

    merged[spec.label_a] = pd.to_numeric(merged[spec.label_a], errors="coerce").fillna(0)
    merged[spec.label_b] = pd.to_numeric(merged[spec.label_b], errors="coerce").fillna(0)
    merged["delta"] = merged[spec.label_b] - merged[spec.label_a]
    if spec.show_pct_change:
        denom = merged[spec.label_a].replace(0, np.nan)
        merged["pct_change"] = (merged["delta"] / denom) * 100.0
        merged["pct_change"] = merged["pct_change"].replace([np.inf, -np.inf], np.nan)

    if spec.group_by:
        merged = merged.sort_values("delta", ascending=False, kind="mergesort").reset_index(drop=True)

    out = d.output
    if not out.x_field and spec.group_by:
        out = AnalyticOutput(
            chart_type=out.chart_type or "bar",
            x_field=spec.group_by[0],
            y_fields=out.y_fields or ["delta"],
            description=out.description,
        )
    return _result_from_df(merged, out)


def _run_custom_python(d: AnalyticDefinition) -> AnalyticResult:
    if not d.custom_python_spec:
        raise HTTPException(status_code=400, detail="custom_python_spec missing")
    spec = d.custom_python_spec
    ds_ids = list(d.inputs.dataset_ids)
    if d.inputs.dataset_id and d.inputs.dataset_id not in ds_ids:
        ds_ids.insert(0, d.inputs.dataset_id)
    if not ds_ids:
        raise HTTPException(status_code=400, detail="At least one dataset must be bound for custom_python")

    # Stage every dataset into a temp dir as parquet so the subprocess can
    # read them deterministically without having to share the in-process
    # _DATASETS dict.
    workdir = Path(tempfile.mkdtemp(prefix="cma_anal_"))
    try:
        for did in ds_ids:
            df = _df_for_dataset(did)
            df.to_parquet(workdir / f"{did}.parquet")
        harness = _custom_python_harness(spec.python_source, spec.function_name, ds_ids, str(workdir))
        result = _exec_subprocess(harness)
    finally:
        for f in workdir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            workdir.rmdir()
        except OSError:
            pass

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Custom python failed")
    payload = result.get("result") or {}
    table = payload.get("table")
    chart = payload.get("chart")
    kpis = payload.get("kpis") or []
    return AnalyticResult(
        table=AnalyticResultTable(**table) if isinstance(table, dict) and "columns" in table else None,
        chart=AnalyticResultChart(**chart) if isinstance(chart, dict) and "type" in chart else None,
        kpis=[AnalyticResultKpi(**k) for k in kpis if isinstance(k, dict) and "label" in k],
    )


def _custom_python_harness(source: str, function_name: str, ds_ids: list[str], workdir: str) -> str:
    """Build the Python harness that loads each dataset as a DataFrame and
    invokes the user's function with `dfs` (dict id→DataFrame).

    The user's function may also accept a single positional arg if there's
    only one dataset — we try both calling conventions.
    """
    return (
        "import json, sys, traceback\n"
        "import pandas as pd\n"
        "from pathlib import Path\n"
        "\n"
        f"WORKDIR = Path(r'''{workdir}''')\n"
        f"DS_IDS = {ds_ids!r}\n"
        "\n"
        "# === user source begins ===\n"
        f"{source}\n"
        "# === user source ends ===\n"
        "\n"
        "try:\n"
        "    dfs = {did: pd.read_parquet(WORKDIR / f'{did}.parquet') for did in DS_IDS}\n"
        f"    fn = {function_name}\n"
        "    try:\n"
        "        out = fn(dfs)\n"
        "    except TypeError:\n"
        "        if len(DS_IDS) == 1:\n"
        "            out = fn(dfs[DS_IDS[0]])\n"
        "        else:\n"
        "            raise\n"
        "    if not isinstance(out, dict):\n"
        "        out = {'kpis': [{'label': 'result', 'value': str(out)}]}\n"
        "    sys.stdout.write('__CMA_RESULT__:' + json.dumps({'ok': True, 'result': out}, default=str))\n"
        "except Exception as e:\n"
        "    sys.stdout.write('__CMA_RESULT__:' + json.dumps({\n"
        "        'ok': False, 'error': str(e), 'traceback': traceback.format_exc()\n"
        "    }))\n"
    )


def _exec_subprocess(harness: str, timeout: float = 15.0) -> dict[str, Any]:
    fd, path = tempfile.mkstemp(suffix=".py")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(harness)
    try:
        completed = subprocess.run(
            [sys.executable, path],
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Custom python timed out after {timeout}s"}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    out = completed.stdout
    marker = "__CMA_RESULT__:"
    idx = out.rfind(marker)
    if idx == -1:
        return {"ok": False, "error": "No result envelope from subprocess",
                "traceback": (completed.stderr or out)[-2000:]}
    try:
        return json.loads(out[idx + len(marker):].strip())
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Could not parse result: {e}", "traceback": out[-2000:]}


# ── Result rendering ───────────────────────────────────────────────────────
def _result_from_df(df: pd.DataFrame, output: AnalyticOutput) -> AnalyticResult:
    """Convert a tabular result + output spec into a chart + table + kpis."""
    table = AnalyticResultTable(
        columns=list(df.columns),
        rows=df.where(pd.notna(df), None).values.tolist(),
    )
    chart: AnalyticResultChart | None = None
    kpis: list[AnalyticResultKpi] = []

    if output.chart_type == "kpi":
        # render up to 4 kpi cards from the first row's numeric columns
        if not df.empty:
            first = df.iloc[0]
            for col in df.columns:
                v = first[col]
                if isinstance(v, (int, float, np.integer, np.floating)):
                    kpis.append(AnalyticResultKpi(label=str(col), value=_fmt_num(v)))
                if len(kpis) >= 4:
                    break
    elif output.chart_type != "table":
        x = output.x_field or (df.columns[0] if len(df.columns) else None)
        y = output.y_fields or [c for c in df.columns if c != x][:1]
        if x and y:
            data = []
            for _, row in df.iterrows():
                rec: dict[str, Any] = {x: row[x]}
                for yf in y:
                    if yf in df.columns:
                        v = row[yf]
                        if isinstance(v, (np.integer,)):
                            v = int(v)
                        elif isinstance(v, (np.floating,)):
                            v = float(v) if not np.isnan(v) else None
                        rec[yf] = v
                data.append(rec)
            chart = AnalyticResultChart(type=output.chart_type, x_field=x, y_fields=y, data=data)
    return AnalyticResult(table=table, chart=chart, kpis=kpis)


def _fmt_num(v) -> str:
    try:
        f = float(v)
    except Exception:
        return str(v)
    if abs(f) >= 1e9:
        return f"{f/1e9:.2f}B"
    if abs(f) >= 1e6:
        return f"{f/1e6:.2f}M"
    if abs(f) >= 1e3:
        return f"{f/1e3:.2f}K"
    if abs(f) < 1 and f != 0:
        return f"{f:.4f}"
    return f"{f:,.2f}"


# ── Run a definition ───────────────────────────────────────────────────────
def _execute_definition(d: AnalyticDefinition) -> AnalyticDefinitionRun:
    started = time.perf_counter()
    rid = f"adr-{uuid.uuid4().hex[:10]}"
    try:
        if d.kind == "aggregate":
            result = _run_aggregate(d)
        elif d.kind == "compare":
            result = _run_compare(d)
        elif d.kind == "custom_python":
            result = _run_custom_python(d)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown kind: {d.kind}")
        run = AnalyticDefinitionRun(
            id=rid,
            definition_id=d.id,
            function_id=d.function_id,
            name=d.name,
            kind=d.kind,
            status="completed",
            result=result,
            created_at=_now(),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except HTTPException as he:
        run = AnalyticDefinitionRun(
            id=rid, definition_id=d.id, function_id=d.function_id,
            name=d.name, kind=d.kind, status="failed",
            error=str(he.detail), created_at=_now(),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    except Exception as e:
        run = AnalyticDefinitionRun(
            id=rid, definition_id=d.id, function_id=d.function_id,
            name=d.name, kind=d.kind, status="failed",
            error=str(e), created_at=_now(),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
    _RUNS[run.id] = run
    return run


# ── CRUD endpoints ─────────────────────────────────────────────────────────
@router.get("", response_model=list[AnalyticDefinition])
async def list_definitions(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_DEFS.values())
    if function_id:
        items = [d for d in items if d.function_id == function_id]
    items.sort(key=lambda d: d.updated_at or d.created_at, reverse=True)
    return items


@router.post("", response_model=AnalyticDefinition, status_code=201)
async def create_definition(req: AnalyticDefinitionCreate, _: str = Depends(get_current_user)):
    did = f"adef-{uuid.uuid4().hex[:8]}"
    d = AnalyticDefinition(
        id=did,
        created_at=_now(),
        **req.model_dump(),
    )
    _DEFS[did] = d
    return d


# Literal route comes before /{def_id} parameter route
@router.get("/runs", response_model=list[AnalyticDefinitionRun])
async def list_runs(
    function_id: str | None = Query(default=None),
    definition_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_RUNS.values())
    if function_id:
        items = [r for r in items if r.function_id == function_id]
    if definition_id:
        items = [r for r in items if r.definition_id == definition_id]
    items.sort(key=lambda r: r.created_at, reverse=True)
    return items


@router.get("/runs/{run_id}", response_model=AnalyticDefinitionRun)
async def get_run(run_id: str, _: str = Depends(get_current_user)):
    r = _RUNS.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return r


@router.post("/runs/{run_id}/narrate", response_model=AnalyticNarrationResponse)
async def narrate_run(run_id: str, _: str = Depends(get_current_user)):
    r = _RUNS.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return AnalyticNarrationResponse(markdown=await _narrate(r))


@router.post("/draft", response_model=AnalyticDraftResponse)
async def draft_definition(req: AnalyticDraftRequest, _: str = Depends(get_current_user)):
    return await _draft(req)


@router.get("/{def_id}", response_model=AnalyticDefinition)
async def get_definition(def_id: str, _: str = Depends(get_current_user)):
    d = _DEFS.get(def_id)
    if not d:
        raise HTTPException(status_code=404, detail="Definition not found")
    return d


@router.patch("/{def_id}", response_model=AnalyticDefinition)
async def update_definition(def_id: str, req: AnalyticDefinitionUpdate, _: str = Depends(get_current_user)):
    d = _DEFS.get(def_id)
    if not d:
        raise HTTPException(status_code=404, detail="Definition not found")
    update = req.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(d, k, v)
    d.updated_at = _now()
    return d


@router.delete("/{def_id}", status_code=204)
async def delete_definition(def_id: str, _: str = Depends(get_current_user)):
    if def_id not in _DEFS:
        raise HTTPException(status_code=404, detail="Definition not found")
    del _DEFS[def_id]


@router.post("/{def_id}/run", response_model=AnalyticDefinitionRun)
async def run_definition(def_id: str, _: str = Depends(get_current_user)):
    d = _DEFS.get(def_id)
    if not d:
        raise HTTPException(status_code=404, detail="Definition not found")
    return _execute_definition(d)


# ── Agent assist: draft + narrate ─────────────────────────────────────────
def _llm_client():
    cof_base = os.getenv("COF_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    if not (cof_base or api_key):
        raise HTTPException(
            status_code=503,
            detail="LLM not configured. Set OPENAI_API_KEY or COF_BASE_URL in backend/.env and restart.",
        )
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed.")
    kwargs: dict[str, Any] = {}
    if cof_base:
        kwargs["base_url"] = cof_base
        kwargs["api_key"] = os.getenv("COF_API_KEY", "cof-internal")
    else:
        kwargs["api_key"] = api_key
    return AsyncOpenAI(**kwargs)


_DRAFT_SYSTEM = """You design self-serve analytics for a domain-agnostic
analytics workbench. Given a plain-English prompt and a list of available
datasets (with column names + dtypes), you pick ONE primitive and produce a
JSON spec the runner can execute.

Three primitive kinds, each with its own spec key:

1. "aggregate" — group-by + measures
   aggregate_spec: {
     group_by: [<column>...],          // 0+ categorical/date columns
     measures: [{
        column: <numeric column>,
        agg: "sum"|"avg"|"count"|"min"|"max"|"median"|"p25"|"p75"|"p90"|"p99"|"weighted_avg"|"stddev",
        alias: <optional output name>,
        weight_by: <numeric column>    // ONLY when agg == "weighted_avg"
     }],
     filters: [{column, op: "eq"|"ne"|"gt"|"gte"|"lt"|"lte"|"in"|"contains", value}],
     sort_by: <output column or null>,
     sort_desc: true,
     limit: 100
   }
   inputs: { dataset_id: <id of the chosen dataset> }

2. "compare" — same metric across two datasets/slices
   compare_spec: {
     group_by: [<column>...],
     measure: { column, agg, alias?, weight_by? },
     label_a: "<short>", label_b: "<short>",
     show_pct_change: true
   }
   inputs: { dataset_id: <A>, dataset_id_b: <B> }

3. "custom_python" — only when neither aggregate nor compare fits
   custom_python_spec: {
     function_name: "run",
     python_source: "def run(dfs):\\n    df = dfs['<id>']\\n    ...\\n    return {'kpis': [...], 'chart': {...}, 'table': {...}}"
   }
   inputs: { dataset_ids: [<id>, ...] }
   The function must return a dict with any combination of:
     - "kpis": [{label, value, sublabel?}]
     - "chart": {type: "bar"|"line"|"area"|"stacked_bar"|"scatter"|"pie", x_field, y_fields:[...], data:[{...}]}
     - "table": {columns:[...], rows:[[...],...]}
   Use ONLY pandas + numpy + python stdlib.

Always include `output`: {chart_type, x_field, y_fields, description}.

Pick column names ONLY from the supplied datasets. If the prompt refers to a
metric not present, pick the closest match and explain in `notes`.

Reply with STRICT JSON, NO prose, NO markdown:
{
  "name": "<concise label>",
  "description": "<one sentence>",
  "kind": "aggregate" | "compare" | "custom_python",
  "inputs": {...},
  "aggregate_spec": {...} | null,
  "compare_spec": {...} | null,
  "custom_python_spec": {...} | null,
  "output": {...},
  "notes": "<optional caveats>"
}
Set the two unused spec keys to null."""


async def _draft(req: AnalyticDraftRequest) -> AnalyticDraftResponse:
    client = _llm_client()
    user = req.prompt.strip()
    if req.available_datasets:
        user += "\n\n[Available datasets]\n" + json.dumps(req.available_datasets, default=str)[:6000]
    try:
        completion = await client.chat.completions.create(
            model=os.getenv("CMA_TOOL_DRAFT_MODEL", "gpt-oss-120b"),
            messages=[
                {"role": "system", "content": _DRAFT_SYSTEM},
                {"role": "user", "content": user},
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

    kind = data.get("kind") or "aggregate"
    if kind not in ("aggregate", "compare", "custom_python"):
        kind = "aggregate"

    inputs_raw = data.get("inputs") or {}
    output_raw = data.get("output") or {}
    notes = data.get("notes")

    # ── Post-validation: catch the common LLM mistakes before they reach
    #    the runner. Two specific failures we've seen on real prompts:
    #
    #    (1) `kind == "compare"` with no `dataset_id_b` (or A == B).
    #        That fails at run time with "dataset_id and dataset_id_b
    #        required". The user's intent was almost always "show two
    #        measures on one dataset" — i.e. an aggregate. Downgrade the
    #        spec and surface the assumption in `notes`.
    #
    #    (2) An aggregate spec with empty `column` on a measure. We
    #        let the runner reject this with a clear message — drafting
    #        rarely emits empty columns since the prompt asks for column
    #        names, but the runner now catches it explicitly.
    if kind == "compare":
        ds_a = inputs_raw.get("dataset_id")
        ds_b = inputs_raw.get("dataset_id_b")
        cspec = data.get("compare_spec") or {}
        if not ds_b or ds_b == ds_a:
            measure = cspec.get("measure") or {}
            kind = "aggregate"
            data["aggregate_spec"] = {
                "group_by": cspec.get("group_by", []),
                "measures": [measure] if measure.get("column") else [],
                "filters": [],
                "sort_by": None,
                "sort_desc": True,
                "limit": 200,
            }
            data["compare_spec"] = None
            warning = (
                "Auto-converted to an Aggregate — your prompt didn't supply "
                "two distinct datasets, which Compare requires. If you want a "
                "true A-vs-B comparison, pick a second dataset and switch "
                "the kind back to Compare."
            )
            notes = f"{notes}\n{warning}" if notes else warning

    try:
        return AnalyticDraftResponse(
            name=(data.get("name") or "Untitled analytic").strip(),
            description=(data.get("description") or "").strip(),
            kind=kind,
            inputs=AnalyticInputs(**{k: v for k, v in inputs_raw.items() if v is not None}),
            aggregate_spec=AggregateSpec(**data["aggregate_spec"])
                if kind == "aggregate" and data.get("aggregate_spec") else None,
            compare_spec=CompareSpec(**data["compare_spec"])
                if kind == "compare" and data.get("compare_spec") else None,
            custom_python_spec=CustomPythonSpec(**data["custom_python_spec"])
                if kind == "custom_python" and data.get("custom_python_spec") else None,
            output=AnalyticOutput(**output_raw) if output_raw else AnalyticOutput(),
            notes=notes,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM draft did not parse: {e}")


_NARRATE_SYSTEM = """You write a concise one-paragraph executive summary of an
analytics result. Read the kpis / chart data / table sample. Identify the 1-3
most notable facts (largest contributor, biggest delta, distribution shape,
anomaly). Keep it under 80 words. Plain markdown — no headings, no bullets
unless the finding genuinely benefits from them. Prefer numbers from the
result over generalities."""


async def _narrate(run: AnalyticDefinitionRun) -> str:
    client = _llm_client()
    if not run.result:
        return run.error or "(no result to narrate)"

    payload: dict[str, Any] = {
        "name": run.name,
        "kind": run.kind,
        "kpis": [k.model_dump() for k in run.result.kpis],
    }
    if run.result.chart:
        c = run.result.chart.model_dump()
        c["data"] = c.get("data", [])[:30]  # cap context
        payload["chart"] = c
    if run.result.table:
        t = run.result.table.model_dump()
        t["rows"] = t.get("rows", [])[:30]
        payload["table"] = t

    try:
        completion = await client.chat.completions.create(
            model=os.getenv("CMA_TOOL_DRAFT_MODEL", "gpt-oss-120b"),
            messages=[
                {"role": "system", "content": _NARRATE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, default=str)[:8000]},
            ],
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")
    return (completion.choices[0].message.content or "").strip() or "(empty narrative)"
