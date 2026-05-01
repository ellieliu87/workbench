"""Deposit forecasting demo pack.

Bundles the three deposit-MaaS models (retail / commercial / small-business),
the Data Harness ETL transform that feeds them, the dataset it
materializes, and a starter Reporting-tab dashboard backed by
pre-computed `deposit_results.csv` so the Overview looks alive the
moment the function loads.

Canvas demo flow (intuitive end-to-end):
  Data Harness (reads OneLake / Finance) ─→ RDMaaS    ─┐
                                          ├→ CommMaaS  ─┼─→ CSV (combined w/ `segment` col)
                                          └→ SBBMaaS   ─┘
"""
from __future__ import annotations

from pathlib import Path

from packs import Pack, PackContext

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SAMPLE_DATA = _REPO_ROOT / "sample_data" / "deposits"
_SAMPLE_MODELS = _REPO_ROOT / "sample_models" / "deposits"


def register(ctx: PackContext) -> None:
    # 1) Pack metadata. The deposit-suite forecast is one workstream
    # under Capital Planning & CCAR (the overall capital plan needs a
    # deposit balance + NII path), so this pack attaches to that
    # function rather than living on its own.
    ctx.pack = Pack(
        id="deposits",
        label="Deposit Forecasting Suite",
        description=(
            "Deposit-suite forecasting workstream within Capital Planning & "
            "CCAR — Retail (RDMaaS), Commercial (CommMaaS), and Small-Business "
            "(SBBMaaS) projections of end balances and interest income across "
            "nine quarters."
        ),
        attach_to_functions=["capital_planning"],
        user_groups=[],
        color="#0EA5E9",
        icon="piggy-bank",
    )

    # 2) Dataset — the macro-scenario wide table the Data Harness reads.
    #    Logically sourced from OneLake: in the corporate proxy
    #    environment this dataset is fetched live by the OneLake
    #    extractor (see docs/ORCHESTRATOR.md, "Wiring OneLake to a
    #    dataset"). For the demo it ships as a staged CSV so the canvas
    #    works end-to-end without proxy connectivity.
    ctx.attach_dataset(
        function_id="capital_planning",
        dataset_id="ds-onelake-macro-scenario",
        name="Macro scenario from OneLake",
        description=(
            "Wide monthly time series of macro + segment-specific drivers "
            "(rates, deposit pricing, account info, treasury demand, "
            "merchant volume). Sourced from the OneLake macro-scenario "
            "table via the corporate OneLake extractor; bundled CSV is "
            "the offline fallback shape so the demo runs without a proxy."
        ),
        source_path=_SAMPLE_DATA / "data_harness.csv",
    )

    # 2b) Data Harness transform — the ETL step on the canvas that reads
    #     from OneLake / Finance and materializes the harness table. The
    #     recipe is informational (read-only in the side panel); the
    #     orchestrator resolves the node to its `output_dataset_id` so the
    #     downstream models see the same rows the recipe would produce.
    _DATA_HARNESS_RECIPE = '''
"""Data Harness — Deposit Suite ETL recipe.

Pulls raw deposit drivers from OneLake (Finance lakehouse), aligns them
to the requested scenario severity + horizon, engineers the features
the three MaaS libraries expect, and returns one wide monthly DataFrame.
"""
def build(*, scenario_severity="base", horizon_months=27, onelake):
    raw = onelake.read_lakehouse_table(
        workspace="Finance",
        lakehouse="cma",
        tables=[
            "deposit_balances_monthly",
            "deposit_pricing_strategy",
            "deposit_competitive_pricing",
            "deposit_account_metrics",
            "macro_scenario_paths",
        ],
        scenario=scenario_severity,
        horizon_months=horizon_months,
    )

    df = (
        raw["macro_scenario_paths"]
        .merge(raw["deposit_pricing_strategy"], on="as_of_date")
        .merge(raw["deposit_competitive_pricing"], on="as_of_date")
        .merge(raw["deposit_account_metrics"], on="as_of_date")
        .sort_values("as_of_date")
        .reset_index(drop=True)
    )

    # Engineered competitive feature: APY spread vs market average, in bps
    df["apy_spread_vs_market_bps"] = (
        (df["retail_promo_apy_pct"] - df["competitor_apy_avg_pct"]) * 100.0
    )

    # Validate every column the MaaS contract expects is present.
    required = {
        "fed_funds_pct", "ust_2y_pct", "unemployment_pct", "gdp_yoy_pct",
        "retail_promo_apy_pct", "retail_standard_apy_pct",
        "competitor_apy_avg_pct", "apy_spread_vs_market_bps",
        "active_accounts_k", "avg_balance_per_acct_usd", "account_attrition_pct",
        "commercial_deposit_beta", "corp_treasury_demand_idx", "loc_utilization_pct",
        "sb_deposit_beta", "merchant_volume_yoy_pct", "sb_loan_originations_mm",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Data Harness: columns missing from OneLake feed: {missing}")

    return df.assign(month_index=range(1, len(df) + 1))
'''

    ctx.attach_transform(
        function_id="capital_planning",
        transform_id="tr-deposits-data-harness",
        name="Data Harness",
        description=(
            "Deposit Suite ETL recipe. Reads raw deposit drivers from "
            "OneLake (Finance lakehouse), aligns them to the requested "
            "scenario severity + horizon, engineers the features the "
            "three MaaS libraries expect, and materializes the result "
            "as the Data Harness Output dataset."
        ),
        input_data_source_ids=["ds-onelake-finance"],
        output_dataset_id="ds-onelake-macro-scenario",
        recipe_python=_DATA_HARNESS_RECIPE.strip(),
        parameters=[
            {
                "name": "scenario_severity",
                "label": "Scenario Severity",
                "type": "select",
                "default": "base",
                "options": ["base", "outlook", "adverse", "severely_adverse"],
                "description": "Macro scenario path to pull from OneLake.",
            },
            {
                "name": "horizon_months",
                "label": "Horizon (months)",
                "type": "number",
                "default": 27,
                "description": "Number of monthly rows to materialize.",
            },
        ],
    )

    # Data Quality Check — runtime gate that runs immediately downstream
    # of the Data Harness and right before the models. Treated as a
    # passthrough transform on the canvas (its `output_dataset_id` is
    # the same as the Harness so consumers see identical rows); the
    # value is the signal: it fails the run fast when the inbound data
    # drifts outside acceptable bands.
    _DQC_RECIPE = '''
"""Data Quality Check — pre-model runtime gate.

Runs row-count, null-rate, range, and distribution checks on whatever
dataset is wired to its input. Fails the workflow with a structured
error when any check trips. Pass-through on success — downstream models
see the same rows.
"""
def check(df, *, min_rows=12, max_null_rate=0.05, value_bounds=None):
    if len(df) < min_rows:
        raise RuntimeError(f"DQC: only {len(df)} rows; need at least {min_rows}")
    null_rate = df.isna().mean().max()
    if null_rate > max_null_rate:
        raise RuntimeError(f"DQC: max column null rate {null_rate:.1%} > {max_null_rate:.1%}")
    if value_bounds:
        for col, (lo, hi) in value_bounds.items():
            if col in df.columns:
                if df[col].min() < lo or df[col].max() > hi:
                    raise RuntimeError(f"DQC: {col} outside [{lo}, {hi}]")
    return df  # passthrough — no transformation, just validation
'''

    ctx.attach_transform(
        function_id="capital_planning",
        transform_id="tr-deposits-dqc",
        name="Data Quality Check",
        description=(
            "Runtime data-quality gate. Runs row-count, null-rate, range, "
            "and distribution checks on the inbound dataset right before "
            "models consume it. Fails the workflow fast when the data "
            "drifts outside acceptable bands; passthrough on success."
        ),
        input_data_source_ids=["ds-onelake-finance"],
        output_dataset_id="ds-onelake-macro-scenario",
        recipe_python=_DQC_RECIPE.strip(),
        parameters=[
            {
                "name": "min_rows",
                "label": "Minimum rows",
                "type": "number",
                "default": 12,
                "description": "Reject the dataset if it has fewer rows than this.",
            },
            {
                "name": "max_null_rate",
                "label": "Max null rate per column",
                "type": "number",
                "default": 0.05,
                "description": "Reject if any column has a higher null rate.",
            },
        ],
    )

    # 3) Models — three MaaS pickles. multi_target output_kind so the
    #    sandbox returns a 2-column matrix and `_post_process` writes
    #    `end_balance_mm` and `interest_income_mm` into each row.
    common_target_names = ["end_balance_mm", "interest_income_mm"]

    ctx.attach_model(
        function_id="capital_planning",
        model_id="mdl-deposits-rdmaas",
        name="RDMaaS",
        description=(
            "Retail Deposit Model-as-a-Service. Projects end-of-month "
            "balance and interest income for the retail deposit book given "
            "pricing strategy (promo/standard APY), competitive pricing "
            "(market gap), and account information (active accounts, avg "
            "balance, attrition)."
        ),
        source_path=_SAMPLE_MODELS / "rdmaas.pkl",
        train_metrics={
            "starting_balance_mm": 240_000.0,
            "horizon_months": 27.0,
            "promo_account_share_pct": 30.0,
        },
        output_kind="multi_target",
        target_names=common_target_names,
    )
    ctx.attach_model(
        function_id="capital_planning",
        model_id="mdl-deposits-commmaas",
        name="CommMaaS",
        description=(
            "Commercial Deposit Model-as-a-Service. Projects end-of-month "
            "balance and interest income for the commercial deposit book "
            "based on corporate treasury demand, line-of-credit utilization, "
            "and rate-sensitivity beta."
        ),
        source_path=_SAMPLE_MODELS / "commmaas.pkl",
        train_metrics={
            "starting_balance_mm": 180_000.0,
            "horizon_months": 27.0,
            "deposit_beta": 0.45,
        },
        output_kind="multi_target",
        target_names=common_target_names,
    )
    ctx.attach_model(
        function_id="capital_planning",
        model_id="mdl-deposits-sbbmaas",
        name="SBBMaaS",
        description=(
            "Small-Business Banking Deposit Model-as-a-Service. Projects "
            "end-of-month balance and interest income for the small-business "
            "deposit book using merchant-acquiring volume, new SB loan "
            "originations, and rate-sensitivity beta."
        ),
        source_path=_SAMPLE_MODELS / "sbbmaas.pkl",
        train_metrics={
            "starting_balance_mm": 45_000.0,
            "horizon_months": 27.0,
            "deposit_beta": 0.38,
        },
        output_kind="multi_target",
        target_names=common_target_names,
    )

    # No reporting tiles attached. The starter tiles were backed by the
    # `ds-deposits-results` dataset (a workflow output staged as a CSV);
    # removing that dataset means the Capital Planning Overview starts
    # empty. Analysts populate it by running their workflow, then pinning
    # tiles from the Reporting catalog onto Overview.
