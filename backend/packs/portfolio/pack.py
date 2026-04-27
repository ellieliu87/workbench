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

    # 4) Datasets — bundled macro time series for portfolio analysis.
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
