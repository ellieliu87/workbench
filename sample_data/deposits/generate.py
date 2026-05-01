"""Generate `data_harness.csv` and `deposit_results.csv` for the deposit-suite demo.

  data_harness.csv     27 monthly rows (9 quarters), one wide table the three
                       MaaS models read from. Includes retail (pricing
                       strategy + competitive pricing + account information),
                       commercial, small-business, and shared macro columns.

  deposit_results.csv  Pre-computed long-format workflow output, used to seed
                       Reporting-tab tiles so the Overview looks alive on
                       first load. Schema mirrors what the canvas produces:
                       (segment, month, as_of_date, end_balance_mm,
                       interest_income_mm).

Run: `python generate.py` from inside `sample_data/deposits/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
# Reuse the same model classes the demo ships so the seeded results match
# what the workflow will actually produce.
MODELS_DIR = HERE.parent.parent / "sample_models" / "deposits"
sys.path.insert(0, str(MODELS_DIR))
from _classes import RDMaaS, CommMaaS, SBBMaaS  # noqa: E402

N_MONTHS = 27  # 9 quarters × monthly grain
START = pd.Timestamp("2026-04-01")


def build_data_harness() -> pd.DataFrame:
    """Wide monthly time series — one row per as_of_date."""
    months = pd.date_range(START, periods=N_MONTHS, freq="MS")
    t = np.arange(N_MONTHS)

    # Shared macro: gentle Fed-funds glide path down from current levels.
    fed_funds = 4.50 - 0.05 * t + 0.05 * np.sin(t / 3.0)
    ust_2y = fed_funds + 0.20 + 0.03 * np.cos(t / 4.0)
    unemployment = 3.8 + 0.02 * t + 0.1 * np.sin(t / 6.0)
    gdp_yoy = 2.1 - 0.02 * t + 0.15 * np.cos(t / 5.0)

    # ── Retail ─ pricing strategy ──────────────────────────────────────
    retail_promo = 4.85 - 0.04 * t + 0.10 * np.sin(t / 2.5)
    retail_std = 3.10 - 0.02 * t + 0.05 * np.cos(t / 3.0)

    # ── Retail ─ competitive pricing ───────────────────────────────────
    competitor_apy = 4.55 - 0.03 * t + 0.08 * np.sin(t / 3.5)
    apy_spread_bps = (retail_promo - competitor_apy) * 100.0  # bps

    # ── Retail ─ account information ───────────────────────────────────
    active_accounts_k = 50_000.0 + 80.0 * t + 200.0 * np.sin(t / 4.0)
    avg_balance = 8_200.0 - 12.0 * t + 80.0 * np.cos(t / 5.0)
    attrition = 0.55 + 0.05 * np.sin(t / 3.0)

    # ── Commercial ─────────────────────────────────────────────────────
    commercial_beta = 0.45 + 0.005 * t + 0.02 * np.sin(t / 4.0)
    corp_demand = 100.0 + 0.6 * t + 4.0 * np.sin(t / 5.0)
    loc_util = 52.0 + 0.3 * t + 2.0 * np.cos(t / 4.0)

    # ── Small-business ─────────────────────────────────────────────────
    sb_beta = 0.38 + 0.004 * t + 0.02 * np.cos(t / 4.0)
    merchant_yoy = 6.5 - 0.05 * t + 1.0 * np.sin(t / 3.0)
    sb_loan_originations = 1_200.0 + 30.0 * np.sin(t / 4.0) + 8.0 * t

    df = pd.DataFrame({
        "month_index": t + 1,
        "as_of_date": [d.strftime("%Y-%m-%d") for d in months],
        # Shared macro
        "fed_funds_pct": np.round(fed_funds, 3),
        "ust_2y_pct": np.round(ust_2y, 3),
        "unemployment_pct": np.round(unemployment, 3),
        "gdp_yoy_pct": np.round(gdp_yoy, 3),
        # Retail — pricing strategy
        "retail_promo_apy_pct": np.round(retail_promo, 3),
        "retail_standard_apy_pct": np.round(retail_std, 3),
        # Retail — competitive pricing
        "competitor_apy_avg_pct": np.round(competitor_apy, 3),
        "apy_spread_vs_market_bps": np.round(apy_spread_bps, 1),
        # Retail — account information
        "active_accounts_k": np.round(active_accounts_k, 0).astype(int),
        "avg_balance_per_acct_usd": np.round(avg_balance, 0).astype(int),
        "account_attrition_pct": np.round(attrition, 3),
        # Commercial
        "commercial_deposit_beta": np.round(commercial_beta, 3),
        "corp_treasury_demand_idx": np.round(corp_demand, 2),
        "loc_utilization_pct": np.round(loc_util, 2),
        # Small-business
        "sb_deposit_beta": np.round(sb_beta, 3),
        "merchant_volume_yoy_pct": np.round(merchant_yoy, 2),
        "sb_loan_originations_mm": np.round(sb_loan_originations, 1),
    })
    return df


def build_deposit_results(harness: pd.DataFrame) -> pd.DataFrame:
    """Run each model on the harness and concatenate into a long-format
    table. This is what the canvas workflow would produce — pre-computed
    here so the Reporting tab has data to render before the user runs."""
    months = harness["month_index"].tolist()
    dates = harness["as_of_date"].tolist()
    parts = []

    for label, cls in [
        ("RDMaaS",   RDMaaS),
        ("CommMaaS", CommMaaS),
        ("SBBMaaS",  SBBMaaS),
    ]:
        m = cls()
        X = harness[m.feature_names].to_numpy(dtype=float)
        out = m.predict(X)  # (n, 2) — [end_balance_mm, interest_income_mm]
        parts.append(pd.DataFrame({
            "segment": label,
            "month": months,
            "as_of_date": dates,
            "end_balance_mm": np.round(out[:, 0], 2),
            "interest_income_mm": np.round(out[:, 1], 3),
        }))
    return pd.concat(parts, ignore_index=True)


def main():
    print(f"Generating deposit-suite sample data in: {HERE}")
    harness = build_data_harness()
    harness_path = HERE / "data_harness.csv"
    harness.to_csv(harness_path, index=False)
    print(f"  [ok] {harness_path.name}  ({len(harness)} rows × {len(harness.columns)} cols)")

    results = build_deposit_results(harness)
    results_path = HERE / "deposit_results.csv"
    results.to_csv(results_path, index=False)
    print(f"  [ok] {results_path.name}  ({len(results)} rows × {len(results.columns)} cols)")


if __name__ == "__main__":
    main()
