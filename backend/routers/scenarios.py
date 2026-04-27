"""Scenarios + Analytics Runs router.

A Scenario is a named macro path. It can come from three places:
1. **Built-ins** — bank-wide Base / Adverse / Severely Adverse / Outlook, seeded
   below with reference rate-and-macro paths.
2. **Upload** — analyst uploads a CSV / Parquet / XLSX / JSON. The plumbing
   reuses the Datasets pipeline (we register the file as a Dataset *and* a
   Scenario in one step).
3. **SQL table** — analyst points at a table in a connected data source
   (e.g. `CMA.PUBLIC.SCENARIOS`).

An Analytics Run takes (model, scenario, horizon) and produces a result series.
For built-in models (regression-trained in-app) we apply the linear / logistic
formula to the scenario's macro variables. For uploaded / external models we
synthesize a plausible response curve so the UI works end-to-end.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from models.schemas import (
    AnalyticsRun,
    DestinationWrite,
    RunRequest,
    Scenario,
    ScenarioCreateFromDataset,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRequest,
    WorkflowResult,
    WorkflowValidationIssue,
    WorkflowValidationResult,
)
from routers.auth import get_current_user
from routers.datasets import _DATASETS, _read_dataframe, _resolve_path
from routers.models_registry import _MODELS

router = APIRouter()


_SCENARIOS: dict[str, Scenario] = {}
_RUNS: dict[str, AnalyticsRun] = {}


# ── Built-in scenarios ──────────────────────────────────────────────────────
BUILTIN_DATA: dict[str, dict[str, Any]] = {
    "scn-base": {
        "name": "Base Case",
        "description": "CCAR Baseline — moderate growth, gradual rate normalization.",
        "severity": "base",
        "variables": ["10Y_UST", "2Y_UST", "Unemployment", "GDP", "HPI"],
        "horizon_months": 12,
        "paths": {
            "10Y_UST":      [4.46, 4.42, 4.38, 4.30, 4.22, 4.15, 4.10, 4.05, 4.00, 3.95, 3.92, 3.90],
            "2Y_UST":       [4.68, 4.55, 4.40, 4.20, 4.00, 3.85, 3.70, 3.55, 3.45, 3.40, 3.35, 3.30],
            "Unemployment": [3.80, 3.85, 3.90, 3.95, 4.00, 4.05, 4.10, 4.10, 4.10, 4.10, 4.10, 4.10],
            "GDP":          [2.10, 2.05, 2.00, 1.95, 1.95, 2.00, 2.05, 2.10, 2.15, 2.15, 2.15, 2.15],
            "HPI":          [3.50, 3.40, 3.30, 3.20, 3.10, 3.00, 2.90, 2.80, 2.75, 2.70, 2.70, 2.70],
        },
    },
    "scn-adverse": {
        "name": "Adverse",
        "description": "CCAR Adverse — mild recession, slow disinflation.",
        "severity": "adverse",
        "variables": ["10Y_UST", "2Y_UST", "Unemployment", "GDP", "HPI"],
        "horizon_months": 12,
        "paths": {
            "10Y_UST":      [4.46, 4.30, 4.10, 3.85, 3.60, 3.40, 3.25, 3.15, 3.10, 3.10, 3.15, 3.20],
            "2Y_UST":       [4.68, 4.30, 3.85, 3.40, 3.00, 2.65, 2.40, 2.25, 2.20, 2.20, 2.25, 2.30],
            "Unemployment": [3.80, 4.10, 4.45, 4.85, 5.30, 5.75, 6.10, 6.30, 6.40, 6.40, 6.30, 6.20],
            "GDP":          [2.10, 1.50, 0.80, -0.20, -0.90, -1.20, -1.00, -0.50, 0.20, 0.80, 1.20, 1.50],
            "HPI":          [3.50, 2.20, 0.40, -1.50, -3.00, -4.00, -4.20, -3.80, -3.00, -2.00, -1.00, 0.00],
        },
    },
    "scn-severe": {
        "name": "Severely Adverse",
        "description": "CCAR Severely Adverse — deep global recession with sharp asset-price declines.",
        "severity": "severely_adverse",
        "variables": ["10Y_UST", "2Y_UST", "Unemployment", "GDP", "HPI"],
        "horizon_months": 12,
        "paths": {
            "10Y_UST":      [4.46, 4.10, 3.65, 3.10, 2.55, 2.10, 1.80, 1.65, 1.60, 1.65, 1.75, 1.85],
            "2Y_UST":       [4.68, 4.00, 3.20, 2.30, 1.50, 0.85, 0.45, 0.25, 0.20, 0.30, 0.45, 0.65],
            "Unemployment": [3.80, 4.50, 5.40, 6.50, 7.80, 9.00, 9.80, 10.20, 10.30, 10.10, 9.80, 9.40],
            "GDP":          [2.10, 0.80, -1.20, -3.50, -5.20, -6.00, -5.20, -3.80, -2.20, -0.80, 0.40, 1.40],
            "HPI":          [3.50, 0.50, -3.00, -7.00, -10.50, -13.00, -14.00, -13.20, -11.50, -9.00, -6.00, -3.00],
        },
    },
    "scn-outlook": {
        "name": "Internal Outlook",
        "description": "Treasury internal outlook — soft landing with sticky inflation.",
        "severity": "outlook",
        "variables": ["10Y_UST", "2Y_UST", "Unemployment", "GDP", "HPI"],
        "horizon_months": 12,
        "paths": {
            "10Y_UST":      [4.46, 4.40, 4.32, 4.25, 4.18, 4.12, 4.08, 4.05, 4.02, 4.00, 4.00, 4.00],
            "2Y_UST":       [4.68, 4.50, 4.30, 4.10, 3.95, 3.80, 3.70, 3.62, 3.58, 3.55, 3.55, 3.55],
            "Unemployment": [3.80, 3.82, 3.85, 3.90, 3.95, 4.00, 4.05, 4.10, 4.10, 4.10, 4.10, 4.05],
            "GDP":          [2.10, 2.10, 2.05, 2.00, 2.00, 2.05, 2.10, 2.15, 2.20, 2.25, 2.25, 2.25],
            "HPI":          [3.50, 3.45, 3.40, 3.35, 3.30, 3.25, 3.25, 3.25, 3.25, 3.25, 3.25, 3.25],
        },
    },
}


def _seed_builtins():
    if _SCENARIOS:
        return
    now = datetime.utcnow().isoformat() + "Z"
    for sid, data in BUILTIN_DATA.items():
        _SCENARIOS[sid] = Scenario(
            id=sid,
            function_id=None,
            name=data["name"],
            description=data["description"],
            severity=data["severity"],
            source_kind="builtin",
            variables=data["variables"],
            horizon_months=data["horizon_months"],
            created_at=now,
        )


_seed_builtins()


# ── Helpers ────────────────────────────────────────────────────────────────
def _scenario_dataframe(scenario_id: str) -> pd.DataFrame:
    """Return a (horizon_months × variables) wide-format DataFrame for the scenario."""
    sc = _SCENARIOS.get(scenario_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if sc.source_kind == "builtin":
        data = BUILTIN_DATA[sc.id]
        rows = []
        for i in range(data["horizon_months"]):
            row = {"month": i + 1}
            for v in data["variables"]:
                row[v] = data["paths"][v][i]
            rows.append(row)
        return pd.DataFrame(rows)
    # upload / sql_table — parse the bound dataset
    if not sc.dataset_id:
        raise HTTPException(status_code=400, detail="Scenario has no underlying dataset")
    d = _DATASETS.get(sc.dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Bound dataset is missing")
    if d.source_kind == "upload" and d.file_path and d.file_format:
        try:
            df = _read_dataframe(_resolve_path(d), d.file_format)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not read scenario file: {e}")
        return df
    # sql_table — synthesize a 12-step series for the column names
    n = sc.horizon_months or 12
    rng = np.random.default_rng(hash(scenario_id) & 0xFFFFFFFF)
    cols: dict[str, list[float]] = {"month": list(range(1, n + 1))}
    for c in d.columns:
        if c.dtype.startswith(("float", "int")):
            cols[c.name] = list(np.linspace(0, 5, n) + rng.normal(0, 0.5, n))
    return pd.DataFrame(cols)


def _apply_model(model_id: str, scenario_df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    m = _MODELS.get(model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    if m.source_kind == "regression" and m.coefficients:
        # Apply linear (or logistic) formula to scenario rows.
        # Match feature names case-insensitively so e.g. model.gdp aligns with
        # scenario.GDP — analysts shouldn't have to babysit casing.
        row_results: list[dict[str, Any]] = []
        used_features = list(m.coefficients.keys())
        col_lower_to_actual = {str(c).lower(): c for c in scenario_df.columns}
        matched: set[str] = set()
        for _, row in scenario_df.iterrows():
            xb = float(m.intercept or 0.0)
            for f in used_features:
                actual = col_lower_to_actual.get(f.lower())
                if actual is not None:
                    try:
                        xb += float(m.coefficients[f]) * float(row[actual])
                        matched.add(f)
                    except (TypeError, ValueError):
                        pass
            if m.model_type == "logistic":
                pred = 1.0 / (1.0 + np.exp(-xb))
            else:
                pred = xb
            entry = {"month": int(row.get("month", len(row_results) + 1)), "prediction": float(round(pred, 6))}
            for v in scenario_df.columns:
                if v != "month" and v in row.index:
                    try:
                        entry[v] = float(row[v])
                    except (TypeError, ValueError):
                        pass
            row_results.append(entry)
        preds = [r["prediction"] for r in row_results]
        unmatched = [f for f in used_features if f not in matched]
        summary = {
            "min_prediction": round(min(preds), 4),
            "max_prediction": round(max(preds), 4),
            "mean_prediction": round(float(np.mean(preds)), 4),
            "horizon_steps": len(preds),
            "model_type": m.model_type,
            "features_matched": len(matched),
            "features_unmatched": unmatched,
        }
        return row_results, summary

    # Uploaded / external — fabricate a plausible response from the macro vars
    rng = np.random.default_rng(hash((m.id, len(scenario_df))) & 0xFFFFFFFF)
    base_signal = scenario_df.select_dtypes(include="number").drop(columns=["month"], errors="ignore")
    if base_signal.shape[1] == 0:
        signal = np.linspace(0, 1, len(scenario_df))
    else:
        signal = base_signal.mean(axis=1).to_numpy()
        signal = (signal - signal.min()) / (signal.max() - signal.min() + 1e-9)
    noise = rng.normal(0, 0.05, len(signal))
    series = []
    for i, (_, row) in enumerate(scenario_df.iterrows()):
        entry = {
            "month": int(row.get("month", i + 1)),
            "prediction": float(round(0.5 + signal[i] * 0.3 + noise[i], 4)),
        }
        for v in scenario_df.columns:
            if v != "month" and v in row.index:
                try:
                    entry[v] = float(row[v])
                except (TypeError, ValueError):
                    pass
        series.append(entry)
    preds = [r["prediction"] for r in series]
    summary = {
        "min_prediction": round(min(preds), 4),
        "max_prediction": round(max(preds), 4),
        "mean_prediction": round(float(np.mean(preds)), 4),
        "horizon_steps": len(preds),
        "model_type": m.model_type,
        "note": "Synthesized response for non-in-app model",
    }
    return series, summary


# ── Scenario routes ─────────────────────────────────────────────────────────
@router.get("/scenarios", response_model=list[Scenario])
async def list_scenarios(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_SCENARIOS.values())
    # Built-ins (function_id None) are always returned; plus function-scoped ones
    items = [
        s for s in items
        if s.function_id is None or s.function_id == function_id or function_id is None
    ]
    items.sort(key=lambda s: (s.source_kind != "builtin", s.created_at), reverse=False)
    return items


@router.get("/scenarios/{scenario_id}", response_model=Scenario)
async def get_scenario(scenario_id: str, _: str = Depends(get_current_user)):
    s = _SCENARIOS.get(scenario_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


@router.get("/scenarios/{scenario_id}/preview")
async def preview_scenario(
    scenario_id: str,
    _: str = Depends(get_current_user),
):
    s = _SCENARIOS.get(scenario_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    df = _scenario_dataframe(scenario_id)
    # Convert datetimes to strings for JSON safety
    out = df.head(50).copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    return {
        "scenario_id": scenario_id,
        "columns": list(out.columns),
        "rows": out.to_dict(orient="records"),
    }


@router.post("/scenarios/from-dataset", response_model=Scenario, status_code=201)
async def scenario_from_dataset(req: ScenarioCreateFromDataset, _: str = Depends(get_current_user)):
    d = _DATASETS.get(req.dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    sid = f"scn-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat() + "Z"
    sc = Scenario(
        id=sid,
        function_id=req.function_id,
        name=req.name,
        description=req.description,
        severity=req.severity,
        source_kind=d.source_kind,  # 'upload' or 'sql_table'
        dataset_id=req.dataset_id,
        variables=[c.name for c in d.columns if c.dtype.startswith(("float", "int"))],
        horizon_months=d.row_count,
        created_at=now,
    )
    _SCENARIOS[sid] = sc
    return sc


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str, _: str = Depends(get_current_user)):
    s = _SCENARIOS.get(scenario_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if s.source_kind == "builtin":
        raise HTTPException(status_code=403, detail="Built-in scenarios cannot be deleted")
    del _SCENARIOS[scenario_id]


# ── Run routes ─────────────────────────────────────────────────────────────
@router.get("/runs", response_model=list[AnalyticsRun])
async def list_runs(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_RUNS.values())
    if function_id:
        items = [r for r in items if r.function_id == function_id]
    items.sort(key=lambda r: r.created_at, reverse=True)
    return items


@router.get("/runs/{run_id}", response_model=AnalyticsRun)
async def get_run(run_id: str, _: str = Depends(get_current_user)):
    r = _RUNS.get(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return r


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: str, _: str = Depends(get_current_user)):
    if run_id not in _RUNS:
        raise HTTPException(status_code=404, detail="Run not found")
    del _RUNS[run_id]


def _input_dataframe(scenario_id: str | None, dataset_id: str | None, horizon: int) -> tuple[pd.DataFrame, str, str]:
    """Resolve the input frame for a run. Returns (df, input_kind, input_label)."""
    if scenario_id and dataset_id:
        raise HTTPException(status_code=400, detail="Pick either a scenario or a dataset, not both")
    if scenario_id:
        df = _scenario_dataframe(scenario_id)
        if "month" in df.columns:
            df = df[df["month"] <= horizon]
        else:
            df = df.head(horizon)
        s = _SCENARIOS.get(scenario_id)
        return df, "scenario", (s.name if s else scenario_id)
    if dataset_id:
        d = _DATASETS.get(dataset_id)
        if not d:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
        if d.source_kind == "upload" and d.file_path and d.file_format:
            try:
                df = _read_dataframe(_resolve_path(d), d.file_format)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Could not read dataset: {e}")
        else:
            # sql_table — synthesize from declared columns
            n = max(horizon, 12)
            rng = np.random.default_rng(hash(dataset_id) & 0xFFFFFFFF)
            cols: dict[str, list[float]] = {}
            for c in d.columns:
                if c.dtype.startswith(("float", "int")):
                    cols[c.name] = list(np.linspace(0, 5, n) + rng.normal(0, 0.5, n))
            if not cols:
                cols["value"] = list(np.linspace(0, 1, n))
            df = pd.DataFrame(cols)
        df = df.head(horizon)
        if "month" not in df.columns:
            df = df.assign(month=list(range(1, len(df) + 1)))
        return df, "dataset", d.name
    raise HTTPException(status_code=400, detail="Either scenario_id or dataset_id is required")


@router.post("/runs", response_model=AnalyticsRun, status_code=201)
async def create_run(req: RunRequest, _: str = Depends(get_current_user)):
    started = datetime.utcnow()
    rid = f"run-{uuid.uuid4().hex[:10]}"
    try:
        df, input_kind, input_label = _input_dataframe(req.scenario_id, req.dataset_id, req.horizon_months)
        series, summary = _apply_model(req.model_id, df)
        m = _MODELS[req.model_id]
        m.last_run = started.isoformat() + "Z"
        run = AnalyticsRun(
            id=rid,
            function_id=req.function_id,
            name=req.name or f"{m.name} × {input_label}",
            model_id=req.model_id,
            scenario_id=req.scenario_id,
            dataset_id=req.dataset_id,
            input_kind=input_kind,
            horizon_months=req.horizon_months,
            status="completed",
            summary=summary,
            series=series,
            notes=req.notes,
            created_at=started.isoformat() + "Z",
            duration_ms=(datetime.utcnow() - started).total_seconds() * 1000,
        )
    except HTTPException:
        raise
    except Exception as e:
        run = AnalyticsRun(
            id=rid,
            function_id=req.function_id,
            name=req.name or "Run",
            model_id=req.model_id,
            scenario_id=req.scenario_id,
            dataset_id=req.dataset_id,
            input_kind="scenario" if req.scenario_id else "dataset",
            horizon_months=req.horizon_months,
            status="failed",
            summary={},
            series=[],
            notes=req.notes,
            error=str(e),
            created_at=started.isoformat() + "Z",
            duration_ms=(datetime.utcnow() - started).total_seconds() * 1000,
        )
    _RUNS[rid] = run
    return run


# ── Workflow runs ──────────────────────────────────────────────────────
def _topological_sort(nodes: list[WorkflowNode], edges: list[WorkflowEdge]) -> list[WorkflowNode]:
    """Kahn's algorithm. Raises HTTPException on cycles or missing nodes."""
    by_id = {n.id: n for n in nodes}
    for e in edges:
        if e.source not in by_id or e.target not in by_id:
            raise HTTPException(status_code=400, detail=f"Edge {e.source}->{e.target} references missing node")

    in_degree: dict[str, int] = {n.id: 0 for n in nodes}
    children: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        in_degree[e.target] += 1
        children[e.source].append(e.target)

    queue = [n for n in nodes if in_degree[n.id] == 0]
    ordered: list[WorkflowNode] = []
    while queue:
        n = queue.pop(0)
        ordered.append(n)
        for c_id in children[n.id]:
            in_degree[c_id] -= 1
            if in_degree[c_id] == 0:
                queue.append(by_id[c_id])
    if len(ordered) != len(nodes):
        raise HTTPException(status_code=400, detail="Workflow contains a cycle")
    return ordered


def _resolve_input_frame(
    node: WorkflowNode,
    upstream_outputs: dict[str, list[dict[str, Any]]],
    horizon: int,
) -> pd.DataFrame:
    """Turn one upstream node into a DataFrame the consuming model can read."""
    if node.kind == "dataset":
        df, _, _ = _input_dataframe(scenario_id=None, dataset_id=node.ref_id, horizon=horizon)
        return df
    if node.kind == "scenario":
        df, _, _ = _input_dataframe(scenario_id=node.ref_id, dataset_id=None, horizon=horizon)
        return df
    if node.kind == "model":
        # Use the model node's run output as a frame (already shaped with 'month'+driver cols)
        rows = upstream_outputs.get(node.id, [])
        if not rows:
            raise HTTPException(status_code=400, detail=f"Model node {node.id} has no upstream output yet")
        return pd.DataFrame(rows)
    raise HTTPException(status_code=400, detail=f"Unknown node kind {node.kind}")


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Outer-join multiple DataFrames on 'month' (or row index if absent)."""
    if not frames:
        raise HTTPException(status_code=400, detail="Model node has no incoming inputs")
    if len(frames) == 1:
        return frames[0]
    # Ensure each frame has a 'month' key for the join
    norm: list[pd.DataFrame] = []
    for df in frames:
        if "month" not in df.columns:
            df = df.assign(month=list(range(1, len(df) + 1)))
        norm.append(df)
    base = norm[0]
    for other in norm[1:]:
        # Drop columns from the other frame that already exist in base (except 'month')
        dup_cols = [c for c in other.columns if c in base.columns and c != "month"]
        other_clean = other.drop(columns=dup_cols)
        base = base.merge(other_clean, on="month", how="outer")
    base = base.sort_values("month").reset_index(drop=True)
    base = base.ffill().bfill()
    return base


def _write_destination(
    dest_node: WorkflowNode,
    upstream_run: AnalyticsRun,
) -> DestinationWrite:
    """'Write' a model run's series to a destination.

    Snowflake / OneLake / S3 writes are mocked for the demo (we just record the
    target and row count). CSV destinations carry the series back so the
    browser can trigger a file download.
    """
    kind = dest_node.ref_id
    cfg = dest_node.config or {}
    rows = upstream_run.series
    n = len(rows)

    if kind == "snowflake_table":
        target = cfg.get("table") or cfg.get("ref") or "CMA.PUBLIC.OUTPUT"
        return DestinationWrite(
            node_id=dest_node.id, kind="snowflake_table", target=target,
            upstream_model_id=upstream_run.model_id, upstream_run_id=upstream_run.id,
            rows_written=n, status="written",
            note=f"Mock write to Snowflake — {cfg.get('mode', 'append')} mode",
        )
    if kind == "onelake_table":
        target = cfg.get("table") or cfg.get("ref") or "Finance.cma.output"
        return DestinationWrite(
            node_id=dest_node.id, kind="onelake_table", target=target,
            upstream_model_id=upstream_run.model_id, upstream_run_id=upstream_run.id,
            rows_written=n, status="written",
            note="Mock write to OneLake lakehouse table",
        )
    if kind == "s3":
        bucket = cfg.get("bucket") or "cma-outputs"
        key = cfg.get("key") or f"runs/{upstream_run.id}.parquet"
        target = f"s3://{bucket}/{key}"
        return DestinationWrite(
            node_id=dest_node.id, kind="s3", target=target,
            upstream_model_id=upstream_run.model_id, upstream_run_id=upstream_run.id,
            rows_written=n, status="written",
            note=f"Mock write to S3 — {cfg.get('format', 'parquet')} format",
        )
    if kind == "csv":
        filename = cfg.get("filename") or f"{upstream_run.id}.csv"
        return DestinationWrite(
            node_id=dest_node.id, kind="csv", target=filename,
            upstream_model_id=upstream_run.model_id, upstream_run_id=upstream_run.id,
            rows_written=n, status="written",
            csv_filename=filename, csv_data=rows,
            note="CSV bytes returned to browser for download",
        )
    return DestinationWrite(
        node_id=dest_node.id, kind=kind,  # type: ignore[arg-type]
        target=str(cfg), upstream_model_id=upstream_run.model_id,
        upstream_run_id=upstream_run.id, rows_written=0, status="failed",
        note=f"Unknown destination kind '{kind}'",
    )


@router.post("/workflow-runs", response_model=WorkflowResult, status_code=201)
async def create_workflow_run(req: WorkflowRequest, _: str = Depends(get_current_user)):
    started = datetime.utcnow()
    workflow_id = f"wf-{uuid.uuid4().hex[:10]}"

    model_nodes = [n for n in req.nodes if n.kind == "model"]
    if not model_nodes:
        raise HTTPException(status_code=400, detail="Workflow must contain at least one model node")

    try:
        ordered = _topological_sort(req.nodes, req.edges)
    except HTTPException:
        raise

    by_id = {n.id: n for n in req.nodes}
    incoming: dict[str, list[str]] = {n.id: [] for n in req.nodes}
    outgoing: dict[str, list[str]] = {n.id: [] for n in req.nodes}
    for e in req.edges:
        incoming[e.target].append(e.source)
        outgoing[e.source].append(e.target)

    outputs: dict[str, list[dict[str, Any]]] = {}
    model_runs_by_node: dict[str, AnalyticsRun] = {}
    runs: list[AnalyticsRun] = []
    destinations: list[DestinationWrite] = []
    node_status: dict[str, str] = {n.id: "idle" for n in req.nodes}
    step_idx = 0

    for node in ordered:
        if node.kind in ("dataset", "scenario"):
            node_status[node.id] = "completed"
            continue

        if node.kind == "destination":
            # Find the upstream model that feeds this destination
            sources = incoming.get(node.id, [])
            if not sources:
                node_status[node.id] = "skipped"
                continue
            wrote_any = False
            for src in sources:
                src_run = model_runs_by_node.get(src)
                if not src_run or src_run.status != "completed":
                    continue
                dw = _write_destination(node, src_run)
                destinations.append(dw)
                wrote_any = wrote_any or dw.status == "written"
            node_status[node.id] = "completed" if wrote_any else "skipped"
            continue

        # node.kind == 'model'
        sources = incoming.get(node.id, [])
        if not sources:
            raise HTTPException(
                status_code=400,
                detail=f"Model node '{node.id}' has no input — connect a dataset, scenario, or upstream model.",
            )

        frames = [_resolve_input_frame(by_id[s], outputs, req.horizon_months) for s in sources]
        merged = _merge_frames(frames)
        if "month" in merged.columns:
            merged = merged[merged["month"] <= req.horizon_months]
        else:
            merged = merged.head(req.horizon_months)

        m = _MODELS.get(node.ref_id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Model {node.ref_id} not found")

        run_started = datetime.utcnow()
        try:
            series, summary = _apply_model(node.ref_id, merged)
            run_status_lit = "completed"
            run_error = None
        except Exception as e:
            series, summary, run_status_lit, run_error = [], {}, "failed", str(e)

        rid = f"run-{uuid.uuid4().hex[:10]}"
        m.last_run = run_started.isoformat() + "Z"
        run = AnalyticsRun(
            id=rid,
            function_id=req.function_id,
            name=f"{m.name} (step {step_idx + 1})",
            model_id=node.ref_id,
            input_kind="workflow",
            workflow_id=workflow_id,
            workflow_step_index=step_idx,
            input_node_ids=sources,
            horizon_months=req.horizon_months,
            status=run_status_lit,  # type: ignore[arg-type]
            summary=summary,
            series=series,
            notes=req.notes,
            error=run_error,
            created_at=run_started.isoformat() + "Z",
            duration_ms=(datetime.utcnow() - run_started).total_seconds() * 1000,
        )
        _RUNS[rid] = run
        runs.append(run)
        model_runs_by_node[node.id] = run
        outputs[node.id] = series
        node_status[node.id] = run_status_lit
        step_idx += 1

        if run_status_lit == "failed":
            return WorkflowResult(
                workflow_id=workflow_id,
                status="partial",
                runs=runs,
                destinations=destinations,
                node_status=node_status,  # type: ignore[arg-type]
                error=run_error,
                duration_ms=(datetime.utcnow() - started).total_seconds() * 1000,
            )

    return WorkflowResult(
        workflow_id=workflow_id,
        status="completed" if runs else "failed",
        runs=runs,
        destinations=destinations,
        node_status=node_status,  # type: ignore[arg-type]
        duration_ms=(datetime.utcnow() - started).total_seconds() * 1000,
    )


@router.post("/workflow-validate", response_model=WorkflowValidationResult)
async def validate_workflow(req: WorkflowRequest, _: str = Depends(get_current_user)):
    """Reuses the chat router's validator for a single source of truth."""
    from routers.chat import _validate_workflow_payload  # local import to avoid circular
    issues_raw = _validate_workflow_payload(
        [n.model_dump() for n in req.nodes],
        [e.model_dump() for e in req.edges],
    )
    issues = [WorkflowValidationIssue(**i) for i in issues_raw]
    return WorkflowValidationResult(
        ok=not any(i.severity == "error" for i in issues),
        issues=issues,
    )
