"""Plots router - per-function report plots that can read from datasets,
analytics runs, or fall back to sample data for the live designer.
"""
import uuid
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from models.schemas import PlotConfig, PlotConfigCreate
from routers.auth import get_current_user
from routers.datasets import _DATASETS, _read_dataframe, _resolve_path
from routers.scenarios import _RUNS

router = APIRouter()


_PLOTS: dict[str, PlotConfig] = {}


# Sample fields by data source (used by the designer when no dataset is bound)
SAMPLE_FIELDS = {
    "ds-snowflake-prod": [
        "month", "quarter", "as_of_date", "product_type", "sector",
        "nav", "market_value", "book_yield", "oas_bps", "oad_years",
        "eve_pct", "shock_bp", "var_99", "svar",
    ],
    "ds-onelake-finance": [
        "month", "segment", "revenue", "opex", "ppnr",
        "plan_revenue", "plan_opex", "variance",
    ],
}


def _seed():
    if _PLOTS:
        return
    seeds = [
        PlotConfig(
            id="plot-nav-trend",
            function_id="investment_portfolio",
            name="NAV Trend",
            chart_type="line",
            data_source_id="ds-snowflake-prod",
            x_field="month",
            y_fields=["nav"],
            aggregation="sum",
            description="Monthly NAV trajectory over the trailing year.",
        ),
    ]
    for p in seeds:
        _PLOTS[p.id] = p


_seed()


# ── helpers ─────────────────────────────────────────────────────────────────
def _df_records(df: pd.DataFrame, n: int = 100) -> list[dict[str, Any]]:
    out = df.head(n).copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    return out.to_dict(orient="records")


def _aggregate(df: pd.DataFrame, x: str, ys: list[str], how: str) -> pd.DataFrame:
    if how == "none":
        return df
    if x not in df.columns:
        return df
    available_ys = [y for y in ys if y in df.columns]
    if not available_ys:
        return df
    agg_map = {y: how if how != "avg" else "mean" for y in available_ys}
    grouped = df.groupby(x, as_index=False).agg(agg_map)
    return grouped


# ── routes ──────────────────────────────────────────────────────────────────
@router.get("", response_model=list[PlotConfig])
async def list_plots(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_PLOTS.values())
    if function_id:
        items = [p for p in items if p.function_id == function_id]
    return items


@router.post("", response_model=PlotConfig, status_code=201)
async def create_plot(req: PlotConfigCreate, _: str = Depends(get_current_user)):
    pid = f"plot-{uuid.uuid4().hex[:10]}"
    p = PlotConfig(id=pid, **req.model_dump())
    _PLOTS[pid] = p
    return p


@router.delete("/{plot_id}", status_code=204)
async def delete_plot(plot_id: str, _: str = Depends(get_current_user)):
    if plot_id not in _PLOTS:
        raise HTTPException(status_code=404, detail="Plot not found")
    del _PLOTS[plot_id]


@router.get("/fields")
async def get_fields(
    data_source_id: str | None = None,
    dataset_id: str | None = None,
    run_id: str | None = None,
    _: str = Depends(get_current_user),
):
    if dataset_id:
        d = _DATASETS.get(dataset_id)
        if not d:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return {"fields": [c.name for c in d.columns]}
    if run_id:
        run = _RUNS.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.series:
            return {"fields": list(run.series[0].keys())}
        return {"fields": []}
    return {"fields": SAMPLE_FIELDS.get(data_source_id or "", SAMPLE_FIELDS["ds-snowflake-prod"])}


@router.get("/{plot_id}/preview")
async def preview_plot(plot_id: str, _: str = Depends(get_current_user)):
    p = _PLOTS.get(plot_id)
    if not p:
        raise HTTPException(status_code=404, detail="Plot not found")

    # Pull data from the configured source
    rows: list[dict[str, Any]] | None = None
    if p.dataset_id:
        d = _DATASETS.get(p.dataset_id)
        if d and d.source_kind == "upload" and d.file_path and d.file_format:
            try:
                df = _read_dataframe(_resolve_path(d), d.file_format)
                df = _aggregate(df, p.x_field, p.y_fields, p.aggregation)
                rows = _df_records(df, 200)
            except Exception:
                rows = None
    if rows is None and p.run_id:
        run = _RUNS.get(p.run_id)
        if run and run.series:
            df = pd.DataFrame(run.series)
            df = _aggregate(df, p.x_field, p.y_fields, p.aggregation)
            rows = _df_records(df, 200)

    if rows is not None:
        return {"plot": p, "preview_data": rows, "source": "live"}

    # Fall back to a synthetic sample
    if p.chart_type in ("line", "area", "bar", "stacked_bar"):
        sample = [
            {p.x_field: m, **{f: round(100 + i * 12 + j * 8, 2) for j, f in enumerate(p.y_fields)}}
            for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
        ]
    elif p.chart_type == "pie":
        sample = [
            {p.x_field: c, p.y_fields[0]: v}
            for c, v in [("Cat A", 38), ("Cat B", 27), ("Cat C", 18), ("Cat D", 17)]
        ]
    elif p.chart_type == "scatter":
        sample = [
            {p.x_field: i, p.y_fields[0]: round((i % 5) * 1.4 + 0.6, 2)}
            for i in range(1, 21)
        ]
    else:
        sample = []
    return {"plot": p, "preview_data": sample, "source": "sample"}
