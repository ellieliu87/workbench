"""Generate CCAR_Macro_Inputs.csv + CCAR_Retail_Outputs.csv for the
multi-agent demo (Data Reconciliation → Methodology → Narrative →
Governance).

Both files are LONG format — Agent 1 (the Quant) consumes them with
Pandas to compute Rate / Volume / Mix variances between scenarios.

Scenarios shipped:
  - CCAR_25_BHC_Base    (Q4-2024 start, mild expansion)
  - CCAR_25_BHC_Stress  (Q4-2024 start, mild recession)
  - CCAR_26_BHC_Base    (Q4-2025 start, mild expansion)
  - CCAR_26_BHC_Stress  (Q4-2025 start, mild recession)
  - Jan_2026_OL         (Treasury internal outlook anchored to 2026Q1)

Quarter IDs: PQ0..PQ9. Portfolios: Legacy_COF, Discover_DFS (DFS rows
exist only from CCAR_26 onward — modeling the integration start).

Run: `python generate_retail_inputs.py` from inside `sample_data/ccar/`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
N_PQ = 10

SCENARIOS = [
    "CCAR_25_BHC_Base",
    "CCAR_25_BHC_Stress",
    "CCAR_26_BHC_Base",
    "CCAR_26_BHC_Stress",
    "Jan_2026_OL",
]

MACRO_VARIABLES = [
    "Fed_Funds_Effective_Rate",
    "1YR_Treasury_Rate",
    "10YR_Treasury_Rate",
    "M2_to_GDP",
    "Unemployment_Rate",
    "BBB_Spread_bps",
    "GDP_Growth_QoQ_AnnL",
    "HPI_YoY",
    "Oil_Price_USD_bbl",
]

PRODUCTS = ["Consumer_Savings", "Consumer_CD", "Consumer_Checking", "SBB"]
PORTFOLIOS = ["Legacy_COF", "Discover_DFS"]
METRICS = [
    "Average_Balance_mm",
    "Rate_Paid_APR",
    "FTP_Rate",
    "Interest_Expense_mm",
    "NII_mm",
]


# ── Macro trajectories per scenario ────────────────────────────────────────
def _macro_path(scenario: str) -> dict[str, np.ndarray]:
    pq = np.arange(N_PQ)

    if scenario in ("CCAR_25_BHC_Base", "Jan_2026_OL"):
        # Mild expansion — rates glide down, unemployment drifts up gently
        ff_start = 4.75 if scenario == "CCAR_25_BHC_Base" else 4.40
        ff = ff_start - 0.10 * pq
        u = 3.85 + 0.03 * pq
        gdp = 2.05 - 0.02 * pq
        bbb = 125.0 - 1.0 * pq
        hpi = 3.5 - 0.10 * pq
        oil = 78.0 - 0.40 * pq
        m2_gdp = 0.74 + 0.002 * pq
    elif scenario == "CCAR_26_BHC_Base":
        ff = 4.50 - 0.10 * pq
        u = 4.00 + 0.03 * pq
        gdp = 2.00 - 0.02 * pq
        bbb = 130.0 - 1.0 * pq
        hpi = 3.0 - 0.10 * pq
        oil = 80.0 - 0.45 * pq
        m2_gdp = 0.73 + 0.002 * pq
    elif scenario == "CCAR_25_BHC_Stress":
        # Mild recession — rate cuts, unemployment peak at PQ5
        ff = np.maximum(4.75 - 0.55 * pq, 1.50)
        u = 3.85 + 0.55 * np.minimum(pq, 5) - 0.10 * np.maximum(pq - 5, 0)
        gdp = np.where(pq <= 3, 2.05 - 1.50 * pq, -2.45 + 0.55 * (pq - 3))
        bbb = 125.0 + 25.0 * np.minimum(pq, 4) + 4.0 * np.maximum(pq - 4, 0)
        hpi = 3.5 - 0.80 * np.minimum(pq, 5) + 0.7 * np.maximum(pq - 5, 0)
        oil = np.where(pq <= 4, 78.0 - 6.0 * pq, 54.0 + 2.0 * (pq - 4))
        m2_gdp = 0.74 - 0.005 * np.minimum(pq, 5) + 0.003 * np.maximum(pq - 5, 0)
    else:  # CCAR_26_BHC_Stress
        ff = np.maximum(4.50 - 0.50 * pq, 1.50)
        u = 4.00 + 0.55 * np.minimum(pq, 5) - 0.10 * np.maximum(pq - 5, 0)
        gdp = np.where(pq <= 3, 2.00 - 1.50 * pq, -2.50 + 0.60 * (pq - 3))
        bbb = 130.0 + 25.0 * np.minimum(pq, 4) + 4.0 * np.maximum(pq - 4, 0)
        hpi = 3.0 - 0.80 * np.minimum(pq, 5) + 0.7 * np.maximum(pq - 5, 0)
        oil = np.where(pq <= 4, 80.0 - 6.0 * pq, 56.0 + 2.0 * (pq - 4))
        m2_gdp = 0.73 - 0.005 * np.minimum(pq, 5) + 0.003 * np.maximum(pq - 5, 0)

    return {
        "Fed_Funds_Effective_Rate": ff,
        "1YR_Treasury_Rate":        ff + 0.05,
        "10YR_Treasury_Rate":       np.maximum(ff + 0.10 - 0.02 * pq, 2.0 if "Stress" in scenario else 3.5),
        "M2_to_GDP":                m2_gdp,
        "Unemployment_Rate":        u,
        "BBB_Spread_bps":           bbb,
        "GDP_Growth_QoQ_AnnL":      gdp,
        "HPI_YoY":                  hpi,
        "Oil_Price_USD_bbl":        oil,
    }


# ── Retail PPNR outputs per (scenario, portfolio, product) ────────────────
def _portfolio_balance_path(
    scenario: str, portfolio: str, product: str,
) -> tuple[np.ndarray, float]:
    """Returns (avg_balance_path_mm, base_rate_paid_pct).

    Balance trajectories shift with stress (attrition) and incorporate the
    Discover/DFS integration story — DFS balances are zero before CCAR_26
    cycles, then onboard from CCAR_26 onward."""
    pq = np.arange(N_PQ)

    # Discover/DFS balances exist only in CCAR_26+ scenarios
    if portfolio == "Discover_DFS" and scenario.startswith("CCAR_25"):
        return np.zeros(N_PQ), 0.0

    # Starting balances ($MM)
    base = {
        ("Legacy_COF",   "Consumer_Savings"):  82_400.0,
        ("Legacy_COF",   "Consumer_CD"):       18_700.0,
        ("Legacy_COF",   "Consumer_Checking"): 31_200.0,
        ("Legacy_COF",   "SBB"):                9_400.0,
        ("Discover_DFS", "Consumer_Savings"):  37_500.0,
        ("Discover_DFS", "Consumer_CD"):       12_900.0,
        ("Discover_DFS", "Consumer_Checking"):  4_100.0,
        ("Discover_DFS", "SBB"):                  600.0,
    }[(portfolio, product)]

    # Base rate paid (% APR) per product. Stress shifts these downward.
    rate = {
        "Consumer_Savings":  3.85,
        "Consumer_CD":       4.95,
        "Consumer_Checking": 0.20,
        "SBB":               2.10,
    }[product]

    # Growth driver per product
    if "Stress" in scenario:
        growth = {
            "Consumer_Savings":  -0.005 * pq,        # mild attrition
            "Consumer_CD":        0.010 * pq,        # CD inflows during stress
            "Consumer_Checking": -0.003 * pq,
            "SBB":                0.000 * pq,
        }[product]
    else:
        growth = {
            "Consumer_Savings":  0.004 * pq,
            "Consumer_CD":      -0.002 * pq,
            "Consumer_Checking": 0.003 * pq,
            "SBB":               0.005 * pq,
        }[product]

    bal = base * np.exp(growth)
    return bal, rate


def _retail_rows(scenario: str, macro: dict[str, np.ndarray]) -> list[dict]:
    """For each (portfolio, product), emit Average_Balance, Rate_Paid_APR,
    FTP_Rate, Interest_Expense, NII rows for every PQ."""
    rows: list[dict] = []
    fed_funds = macro["Fed_Funds_Effective_Rate"]

    for portfolio in PORTFOLIOS:
        for product in PRODUCTS:
            bal, base_rate = _portfolio_balance_path(scenario, portfolio, product)
            if np.allclose(bal, 0):
                continue

            # Rate paid tracks fed funds with a beta + shifts under stress.
            beta = {
                "Consumer_Savings": 0.45, "Consumer_CD": 0.85,
                "Consumer_Checking": 0.05, "SBB": 0.55,
            }[product]
            ff_anchor = fed_funds[0]
            rate_paid = np.maximum(base_rate + beta * (fed_funds - ff_anchor), 0.10)
            # Discover applies a "Big 6" benchmark uplift only on CDs in CCAR_26+
            if portfolio == "Discover_DFS" and product == "Consumer_CD":
                rate_paid = rate_paid + 0.10

            ftp = fed_funds + 0.20  # FTP curve rides slightly above policy
            int_expense_mm = bal * (rate_paid / 100.0) * 0.25  # quarterly $MM
            nii_mm = bal * ((ftp - rate_paid) / 100.0) * 0.25

            for q in range(N_PQ):
                rows.extend([
                    dict(Scenario=scenario, Quarter_ID=f"PQ{q}", Portfolio=portfolio,
                         Product_L1=product, Metric="Average_Balance_mm",
                         Value=round(float(bal[q]), 2)),
                    dict(Scenario=scenario, Quarter_ID=f"PQ{q}", Portfolio=portfolio,
                         Product_L1=product, Metric="Rate_Paid_APR",
                         Value=round(float(rate_paid[q]), 4)),
                    dict(Scenario=scenario, Quarter_ID=f"PQ{q}", Portfolio=portfolio,
                         Product_L1=product, Metric="FTP_Rate",
                         Value=round(float(ftp[q]), 4)),
                    dict(Scenario=scenario, Quarter_ID=f"PQ{q}", Portfolio=portfolio,
                         Product_L1=product, Metric="Interest_Expense_mm",
                         Value=round(float(int_expense_mm[q]), 2)),
                    dict(Scenario=scenario, Quarter_ID=f"PQ{q}", Portfolio=portfolio,
                         Product_L1=product, Metric="NII_mm",
                         Value=round(float(nii_mm[q]), 2)),
                ])
    return rows


def main():
    print(f"Generating CCAR multi-agent demo data in: {HERE}")

    # ── Macro inputs ──────────────────────────────────────────────────
    macro_rows: list[dict] = []
    for scenario in SCENARIOS:
        macro = _macro_path(scenario)
        for var in MACRO_VARIABLES:
            for q in range(N_PQ):
                macro_rows.append({
                    "Scenario":      scenario,
                    "Quarter_ID":    f"PQ{q}",
                    "Variable_Name": var,
                    "Value":         round(float(macro[var][q]), 4),
                })
    macro_df = pd.DataFrame(macro_rows)
    macro_path = HERE / "CCAR_Macro_Inputs.csv"
    macro_df.to_csv(macro_path, index=False)
    print(f"  [ok] {macro_path.name}  ({len(macro_df):,} rows × {len(macro_df.columns)} cols)")

    # ── Retail PPNR outputs ───────────────────────────────────────────
    retail_rows: list[dict] = []
    for scenario in SCENARIOS:
        macro = _macro_path(scenario)
        retail_rows.extend(_retail_rows(scenario, macro))
    retail_df = pd.DataFrame(retail_rows)
    retail_path = HERE / "CCAR_Retail_Outputs.csv"
    retail_df.to_csv(retail_path, index=False)
    print(f"  [ok] {retail_path.name}  ({len(retail_df):,} rows × {len(retail_df.columns)} cols)")


if __name__ == "__main__":
    main()
