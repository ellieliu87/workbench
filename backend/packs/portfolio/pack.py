"""Portfolio domain pack — investment-portfolio agents, tools, datasets, models.

A single `register(ctx)` function is the entry point. The Pack registry
discovers this file at startup and calls it; everything below ends up in
the right downstream registry (skill loader / tool registry / dataset
seeds / model seeds) without touching any router.

Artifacts shipped:

  Skills    — 8 portfolio-planning agents (in `skills/`)
  Tools     — 21 Python tools (defined inline in `tools.py`)
  Datasets  — `macro_history.csv` + `macro_forecast.csv` from
              `sample_data/portfolio/` attached to the
              `investment_portfolio` function
  Models    — `bgm_term_structure.pkl` from `sample_models/portfolio/`
              attached to `investment_portfolio` (and `interest_rate_risk`,
              for cross-domain rate scenario work)
"""
from __future__ import annotations

from pathlib import Path

from packs import Pack, PackContext
from packs.portfolio.tools import register_python_tools

# Repo-relative roots for sample artifacts the pack references.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SAMPLE_DATA = _REPO_ROOT / "sample_data" / "portfolio"
_SAMPLE_MODELS = _REPO_ROOT / "sample_models" / "portfolio"


def register(ctx: PackContext) -> None:
    # 1) Pack metadata. Filling in the stub `Pack(id="portfolio")` the loader
    #    constructed from the directory name.
    ctx.pack = Pack(
        id="portfolio",
        label="Investment Portfolio",
        description=(
            "Fixed-income portfolio planning bundle — gap analysis, risk "
            "guardrails, allocation, MBS decomposition, universe screening, "
            "pool analytics, and IC trade recommendation."
        ),
        attach_to_functions=["investment_portfolio"],
        # Empty user_groups means the pack is visible to everyone for now.
        # Lock down later by listing groups (e.g. ["portfolio_managers"]).
        user_groups=[],
        color="#004977",
        icon="briefcase",
    )

    # 2) Skills — load every .md from this pack's `skills/` directory.
    ctx.register_skill_dir()  # defaults to <pack_dir>/skills

    # 3) Python tools — defined in tools.py to keep this file readable.
    register_python_tools(ctx)

    # 4) Datasets — bundled macro time series for portfolio analysis,
    #    plus the demo destination-result table used by the starter
    #    Reporting-tab dashboard below.
    ctx.attach_dataset(
        function_id="investment_portfolio",
        dataset_id="ds-macro-history",
        name="Macro History",
        description=(
            "Historical macroeconomic time series (rates, spreads, prepay, "
            "growth). Bundled sample for portfolio analytics."
        ),
        source_path=_SAMPLE_DATA / "macro_history.csv",
    )
    ctx.attach_dataset(
        function_id="investment_portfolio",
        dataset_id="ds-macro-forecast",
        name="Macro Forecast",
        description=(
            "Forward-looking macro projections used for scenario analysis "
            "and Monte Carlo runs. Bundled sample."
        ),
        source_path=_SAMPLE_DATA / "macro_forecast.csv",
    )
    ctx.attach_dataset(
        function_id="investment_portfolio",
        dataset_id="ds-ip-results",
        name="Portfolio Results (ip_results)",
        description=(
            "Long-format destination table with one row per (month × pool): "
            "as_of_date, pool, sector, coupon_pct, market_value_mm, "
            "book_yield_pct, oas_bps, oad_yr. Drives the starter Reporting "
            "tiles for KPIs, NAV trajectory, sector mix, and top holdings."
        ),
        source_path=_SAMPLE_DATA / "ip_results.csv",
    )

    # 4b) Pre-built Reporting-tab tiles backed by ip_results. These appear
    #     in the Reporting tab as if a user had built them; the user pins
    #     to surface on the Overview tab. Filtered to the latest snapshot
    #     (2026-04-01) where a point-in-time view is wanted.
    _LATEST_DATE = "2026-04-01"

    # ── KPIs (4) ──────────────────────────────────────────────────────
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-kpi-nav",
        config={
            "name": "NAV",
            "tile_type": "kpi",
            "dataset_id": "ds-ip-results",
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "kpi_field": "market_value_mm",
            "kpi_aggregation": "sum",
            "kpi_prefix": "$",
            "kpi_suffix": "B",
            "kpi_decimals": 2,
            "kpi_scale": 0.001,            # MM → B
            "kpi_sublabel": "as of latest month",
            "description": "Total net asset value at the latest snapshot.",
            "pinned_to_overview": True,
        },
    )
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-kpi-yield",
        config={
            "name": "Book Yield",
            "tile_type": "kpi",
            "dataset_id": "ds-ip-results",
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "kpi_field": "book_yield_pct",
            "kpi_aggregation": "weighted_avg",
            "kpi_weight_field": "market_value_mm",
            "kpi_suffix": "%",
            "kpi_decimals": 2,
            "kpi_sublabel": "weighted by MV",
            "description": "Market-value-weighted book yield.",
            "pinned_to_overview": True,
        },
    )
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-kpi-oad",
        config={
            "name": "OAD",
            "tile_type": "kpi",
            "dataset_id": "ds-ip-results",
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "kpi_field": "oad_yr",
            "kpi_aggregation": "weighted_avg",
            "kpi_weight_field": "market_value_mm",
            "kpi_suffix": " yr",
            "kpi_decimals": 2,
            "kpi_sublabel": "option-adjusted, weighted",
            "description": "Market-value-weighted option-adjusted duration.",
            "pinned_to_overview": True,
        },
    )
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-kpi-oas",
        config={
            "name": "OAS",
            "tile_type": "kpi",
            "dataset_id": "ds-ip-results",
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "kpi_field": "oas_bps",
            "kpi_aggregation": "weighted_avg",
            "kpi_weight_field": "market_value_mm",
            "kpi_suffix": " bps",
            "kpi_decimals": 0,
            "kpi_sublabel": "spread, weighted",
            "description": "Market-value-weighted option-adjusted spread.",
            "pinned_to_overview": True,
        },
    )

    # ── Plots (2) ─────────────────────────────────────────────────────
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-nav-trajectory",
        config={
            "name": "NAV Trajectory",
            "tile_type": "plot",
            "chart_type": "area",
            "dataset_id": "ds-ip-results",
            "x_field": "as_of_date",
            "y_fields": ["market_value_mm"],
            "aggregation": "sum",            # group-by date, sum across pools
            "filters": [],
            "description": "Total portfolio NAV ($MM) over the trailing 8 months.",
            "pinned_to_overview": True,
        },
    )
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-sector-mix",
        config={
            "name": "Sector Allocation",
            "tile_type": "plot",
            "chart_type": "bar",
            "dataset_id": "ds-ip-results",
            "x_field": "sector",
            "y_fields": ["market_value_mm"],
            "aggregation": "sum",
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "description": "Portfolio allocation by sector at the latest snapshot.",
            "pinned_to_overview": True,
        },
    )

    # ── Tables (1) ────────────────────────────────────────────────────
    ctx.attach_plot(
        function_id="investment_portfolio",
        plot_id="plot-portfolio-top-holdings",
        config={
            "name": "Top Holdings",
            "tile_type": "table",
            "dataset_id": "ds-ip-results",
            "table_columns": [
                "pool", "sector", "coupon_pct", "market_value_mm",
                "book_yield_pct", "oas_bps", "oad_yr",
            ],
            "table_default_sort": "market_value_mm",
            "table_default_sort_desc": True,
            "filters": [{"field": "as_of_date", "op": "eq", "value": _LATEST_DATE}],
            "description": "Holdings at the latest snapshot, sorted by market value.",
            "pinned_to_overview": True,
        },
    )

    # 5) Models — BGM term-structure for both IRR and Portfolio.
    bgm_pkl = _SAMPLE_MODELS / "bgm_term_structure.pkl"
    bgm_metrics = {
        "calibration_rmse_bps": 4.2,
        "tenors_supported": 12.0,
        "monte_carlo_paths": 10000.0,
    }
    ctx.attach_model(
        function_id="investment_portfolio",
        model_id="mdl-bgm-term-structure-portfolio",
        name="BGM Term-Structure Model",
        description=(
            "Brace-Gatarek-Musiela (BGM / LIBOR Market Model) calibrated "
            "for forward-rate evolution across the curve. Used for repricing "
            "fixed-income positions and stress-testing the portfolio."
        ),
        source_path=bgm_pkl,
        train_metrics=bgm_metrics,
    )
    ctx.attach_model(
        function_id="interest_rate_risk",
        model_id="mdl-bgm-term-structure-irr",
        name="BGM Term-Structure Model",
        description=(
            "Brace-Gatarek-Musiela (BGM / LIBOR Market Model) calibrated "
            "for forward-rate evolution across the curve. Sample artifact "
            "for scenario / Monte Carlo work on the rates book."
        ),
        source_path=bgm_pkl,
        train_metrics=bgm_metrics,
    )
