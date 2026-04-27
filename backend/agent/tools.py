"""Tools the LLM agents can call.

Every tool is a read-only lookup against the workbench's existing in-process
state — workspace data, datasets, models, runs, plots, the workflow validator.
The OpenAI / agents SDK calls `handle_tool_call(name, args)` which dispatches
to the implementation here.

Filters / writes (`apply_tile_filter`) intentionally exist so the Tile Tuner can
materially change the tile when the analyst clicks an action chip.
"""
from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd

from routers.datasets import _DATASETS, _read_dataframe, _resolve_path, _synthesize_sample
from routers.models_registry import _MODELS
from routers.plots import _PLOTS, _apply_filters
from routers.scenarios import _RUNS, _SCENARIOS
from services.workspace_data import get_workspace


# OpenAI-format tool schemas — these are advertised to the LLM
OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_workspace",
            "description": "Fetch the live Overview workspace snapshot for a function — KPIs, charts, tables, insights.",
            "parameters": {
                "type": "object",
                "properties": {
                    "function_id": {"type": "string", "description": "Function id, e.g. investment_portfolio"},
                },
                "required": ["function_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_function_meta",
            "description": "Get metadata about a function (description, default views, sample metrics).",
            "parameters": {
                "type": "object",
                "properties": {"function_id": {"type": "string"}},
                "required": ["function_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_dataset",
            "description": "Statistically profile a dataset: row count, per-column null %, IQR outliers, dtype drift, constant columns.",
            "parameters": {
                "type": "object",
                "properties": {"dataset_id": {"type": "string"}},
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_preview",
            "description": "Return the first N rows of a dataset along with its schema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "n": {"type": "integer", "description": "Max rows (default 25)."},
                },
                "required": ["dataset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_model",
            "description": "Get a registered model's full metadata — coefficients, intercept, target, features, train metrics.",
            "parameters": {
                "type": "object",
                "properties": {"model_id": {"type": "string"}},
                "required": ["model_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_model_metrics",
            "description": "Get a model's monitoring metric trace (R²/AUC/PSI over time).",
            "parameters": {
                "type": "object",
                "properties": {"model_id": {"type": "string"}},
                "required": ["model_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_workflow",
            "description": (
                "Validate a workflow design. The analyst's [Context] block contains a `payload` "
                "field that is a JSON string with `nodes` (each {id, kind, ref_id, config}) and "
                "`edges` (each {source, target}). Copy that JSON into `workflow_json` and call. "
                "Returns a list of issues with severity (error / warning / info)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_json": {
                        "type": "string",
                        "description": "JSON object with `nodes` and `edges` arrays, copied from the [Context] payload.",
                    },
                },
                "required": ["workflow_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run",
            "description": "Fetch a single analytics run by id — status, error, summary, series.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tile",
            "description": "Get a tile's saved configuration (plot/table type, source, filters).",
            "parameters": {
                "type": "object",
                "properties": {"tile_id": {"type": "string"}},
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tile_preview",
            "description": "Get a tile's live preview rows + column metadata. Use this to know the actual data ranges before suggesting filters.",
            "parameters": {
                "type": "object",
                "properties": {"tile_id": {"type": "string"}},
                "required": ["tile_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_tile_filter",
            "description": "Append a filter to a tile so the next preview reflects it. Use this to surface filter chips the analyst can click.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tile_id": {"type": "string"},
                    "field": {"type": "string"},
                    "op": {"type": "string", "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"]},
                    "value": {
                        "description": "Filter value — string, number, boolean, or list of strings/numbers.",
                        "anyOf": [
                            {"type": "string"},
                            {"type": "number"},
                            {"type": "boolean"},
                            {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "number"}]}},
                        ],
                    },
                },
                "required": ["tile_id", "field", "op", "value"],
            },
        },
    },
]


# ── Implementations ───────────────────────────────────────────────────────
def _t_get_workspace(args: dict) -> str:
    fid = args.get("function_id", "")
    ws = get_workspace(fid)
    if not ws:
        return json.dumps({"error": f"No workspace for function `{fid}`"})
    return ws.model_dump_json(indent=2)


def _t_get_function_meta(args: dict) -> str:
    from routers.functions import BUSINESS_FUNCTIONS
    fid = args.get("function_id", "")
    f = next((x for x in BUSINESS_FUNCTIONS if x.id == fid), None)
    return f.model_dump_json(indent=2) if f else json.dumps({"error": f"Unknown function `{fid}`"})


def _t_profile_dataset(args: dict) -> str:
    did = args.get("dataset_id", "")
    d = _DATASETS.get(did)
    if not d:
        return json.dumps({"error": f"Dataset `{did}` not found"})
    df = _read_or_synth(d)
    if df is None or df.empty:
        return json.dumps({"error": f"Could not read dataset `{did}`"})

    profile: dict[str, Any] = {
        "dataset_id": did, "name": d.name, "rows": int(len(df)), "columns": int(len(df.columns)),
        "null_rate": {}, "outliers": {}, "constant_columns": [], "dtype_drift": [],
    }
    for col in df.columns:
        null_pct = float(df[col].isnull().mean() * 100)
        if null_pct > 0:
            profile["null_rate"][col] = round(null_pct, 2)
        if df[col].nunique(dropna=True) <= 1:
            profile["constant_columns"].append(col)

    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        out = s[(s < lo) | (s > hi)]
        if len(out) > 0:
            profile["outliers"][col] = {
                "count": int(len(out)),
                "pct": round(len(out) / len(s) * 100, 2),
                "bounds": [round(lo, 4), round(hi, 4)],
            }

    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().astype(str)
        if sample.empty:
            continue
        as_num = pd.to_numeric(sample, errors="coerce")
        rate = float(as_num.notna().mean())
        if 0.9 <= rate < 1.0:
            profile["dtype_drift"].append({
                "column": col,
                "parse_rate_as_numeric": round(rate * 100, 1),
            })
    return json.dumps(profile, default=_json_default)


def _t_get_dataset_preview(args: dict) -> str:
    did = args.get("dataset_id", "")
    n = int(args.get("n", 25))
    d = _DATASETS.get(did)
    if not d:
        return json.dumps({"error": f"Dataset `{did}` not found"})
    df = _read_or_synth(d, n)
    if df is None:
        return json.dumps({"error": "Read failed"})
    return json.dumps({
        "name": d.name,
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "rows": _df_records(df, n),
    }, default=_json_default)


def _t_get_model(args: dict) -> str:
    mid = args.get("model_id", "")
    m = _MODELS.get(mid)
    return m.model_dump_json(indent=2) if m else json.dumps({"error": f"Model `{mid}` not found"})


def _t_get_model_metrics(args: dict) -> str:
    mid = args.get("model_id", "")
    m = _MODELS.get(mid)
    if not m:
        return json.dumps({"error": f"Model `{mid}` not found"})
    series: dict[str, list[dict[str, Any]]] = {}
    for entry in m.monitoring_metrics:
        series.setdefault(entry.name, []).append({"asof": entry.asof, "value": entry.value})
    return json.dumps({"model_id": mid, "series": series, "train_metrics": m.train_metrics})


def _t_validate_workflow(args: dict) -> str:
    from routers.chat_validation import validate_workflow_payload  # local helper module
    raw = args.get("workflow_json")
    # Backwards-compat: also accept the older shape with explicit fields
    if raw is None and ("nodes" in args or "edges" in args):
        nodes = args.get("nodes", [])
        edges = args.get("edges", [])
    else:
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"workflow_json was not valid JSON: {e}"})
        elif isinstance(raw, dict):
            data = raw
        else:
            return json.dumps({"error": "workflow_json must be a JSON object string"})
        nodes = data.get("nodes", []) or []
        edges = data.get("edges", []) or []
    issues = validate_workflow_payload(nodes, edges)
    return json.dumps({
        "ok": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
        "node_count": len(nodes),
        "edge_count": len(edges),
    })


def _t_get_run(args: dict) -> str:
    rid = args.get("run_id", "")
    r = _RUNS.get(rid)
    return r.model_dump_json(indent=2) if r else json.dumps({"error": f"Run `{rid}` not found"})


def _t_get_tile(args: dict) -> str:
    tid = args.get("tile_id", "")
    p = _PLOTS.get(tid)
    return p.model_dump_json(indent=2) if p else json.dumps({"error": f"Tile `{tid}` not found"})


def _t_get_tile_preview(args: dict) -> str:
    tid = args.get("tile_id", "")
    p = _PLOTS.get(tid)
    if not p:
        return json.dumps({"error": f"Tile `{tid}` not found"})
    df = _tile_dataframe(p)
    if df is None or df.empty:
        return json.dumps({"name": p.name, "rows": [], "note": "No live data — using sample"})
    df = _apply_filters(df, p.filters)
    return json.dumps({
        "name": p.name,
        "tile_type": p.tile_type,
        "chart_type": p.chart_type,
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "row_count": int(len(df)),
        "sample_rows": _df_records(df, 25),
        "summary": _summarize(df),
    }, default=_json_default)


def _t_apply_tile_filter(args: dict) -> str:
    tid = args.get("tile_id", "")
    p = _PLOTS.get(tid)
    if not p:
        return json.dumps({"error": f"Tile `{tid}` not found"})
    f = {"field": args.get("field"), "op": args.get("op"), "value": args.get("value")}
    p.filters = list(p.filters) + [f]
    return json.dumps({"ok": True, "filters": p.filters})


# ── Handler ───────────────────────────────────────────────────────────────
_HANDLERS = {
    "get_workspace":      _t_get_workspace,
    "get_function_meta":  _t_get_function_meta,
    "profile_dataset":    _t_profile_dataset,
    "get_dataset_preview": _t_get_dataset_preview,
    "get_model":          _t_get_model,
    "get_model_metrics":  _t_get_model_metrics,
    "validate_workflow":  _t_validate_workflow,
    "get_run":            _t_get_run,
    "get_tile":           _t_get_tile,
    "get_tile_preview":   _t_get_tile_preview,
    "apply_tile_filter":  _t_apply_tile_filter,
}


def handle_tool_call(name: str, args: dict) -> str:
    handler = _HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool `{name}`"})
    try:
        return handler(args)
    except Exception as e:
        import traceback
        return json.dumps({"error": str(e), "traceback": traceback.format_exc()[-500:]})


# ── Helpers ───────────────────────────────────────────────────────────────
def _read_or_synth(d, n: int = 2000) -> pd.DataFrame | None:
    if d.source_kind == "upload" and d.file_path and d.file_format:
        try:
            return _read_dataframe(_resolve_path(d), d.file_format).head(n)
        except Exception:
            return None
    rows = _synthesize_sample(d.columns, n)
    return pd.DataFrame(rows)


def _tile_dataframe(p) -> pd.DataFrame | None:
    if p.dataset_id:
        d = _DATASETS.get(p.dataset_id)
        if d and d.source_kind == "upload" and d.file_path and d.file_format:
            try:
                return _read_dataframe(_resolve_path(d), d.file_format)
            except Exception:
                return None
    if p.run_id:
        run = _RUNS.get(p.run_id)
        if run and run.series:
            return pd.DataFrame(run.series)
    return None


def _df_records(df: pd.DataFrame, n: int) -> list[dict[str, Any]]:
    out = df.head(n).copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    return json.loads(out.to_json(orient="records", date_format="iso"))


def _summarize(df: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for col in df.select_dtypes(include="number").columns[:6]:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        summary[col] = {
            "min": float(s.min()), "max": float(s.max()),
            "median": float(s.median()), "p90": float(s.quantile(0.9)),
        }
    for col in df.select_dtypes(include="object").columns[:3]:
        vc = df[col].value_counts().head(3)
        summary[col] = {str(k): int(v) for k, v in vc.items()}
    return summary


def _json_default(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return str(o)
