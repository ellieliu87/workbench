"""Generate realistic sample data files for the Investment Portfolio function.

Produces four CSVs in this directory, each shaped to match exactly what the
matching sample model in `cma/sample_models/portfolio/` consumes:

  - mbs_positions.csv   — InterestIncomeCalc.project() expects rows like these.
  - embs_deal_info.csv  — PrepaymentNN.predict() expects these feature columns.
  - macro_history.csv   — MortgageRateTSModel.predict() (after small feature
                          engineering) expects these columns; also fine input
                          for any custom regression an analyst builds in-app.
  - macro_forecast.csv  — Forward macro paths the analyst can plug into runs.

Run once: `python generate.py`. Deterministic seeds, no network needed.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

# ── Reusable seed pools ────────────────────────────────────────────────
AGENCIES = ["FNMA", "FHLMC", "GNMA"]
SECTORS = ["CC30", "CC15", "GN30", "Treasury"]
STATES = ["CA", "TX", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "WA"]


def _gen_positions(n: int = 30, seed: int = 11) -> pd.DataFrame:
    """SimCorp-style position book. One row per position.

    Columns are a superset of what InterestIncomeCalc.project() needs
    (`cusip`, `coupon`, `par_amount` / `balance`, `wam` / `wam_months`,
    `cpr_pct`) plus standard reporting fields.
    """
    rng = np.random.default_rng(seed)
    rows = []
    today = date(2026, 4, 25)
    for i in range(n):
        agency = rng.choice(AGENCIES, p=[0.55, 0.30, 0.15])
        sector = rng.choice(["CC30", "CC15", "GN30"], p=[0.55, 0.25, 0.20])
        coupon = round(float(rng.choice([4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0],
                                       p=[0.10, 0.15, 0.20, 0.20, 0.20, 0.10, 0.05])), 3)
        par = round(float(rng.uniform(20_000_000, 500_000_000)), 0)
        wala = int(rng.uniform(0, 180))
        term = 360 if sector == "CC30" or sector == "GN30" else 180
        wam = max(term - wala, 24)
        # WAC slightly above coupon (gross-net spread ~50 bps for agency)
        wac = round(coupon + rng.uniform(0.40, 0.65), 3)
        # Price tied to coupon vs current ~6.85% mortgage rate
        current_rate = 6.85
        price = round(100 + (coupon - current_rate) * 4.2 + rng.normal(0, 0.6), 2)
        market_value = round(par * price / 100, 0)
        unrealized = round(market_value - par, 0)
        oad = round(rng.uniform(3.5, 5.8), 2)
        oas = round(rng.uniform(28, 62), 1)
        book_yield = round(coupon - 0.6 + rng.normal(0, 0.15), 3)
        cpr = round(rng.uniform(4.5, 18.5), 2)
        # Pool-level stats useful for the prepay model later
        fico = int(np.clip(rng.normal(745, 18), 670, 810))
        ltv = round(rng.uniform(0.62, 0.85), 3)
        loan_size_k = round(rng.uniform(180, 620), 0)

        cusip = f"31418{rng.integers(100, 999)}{chr(65 + i % 26)}"
        rows.append({
            "position_id": f"POS-{2000 + i:04d}",
            "cusip": cusip,
            "pool_id": f"{agency}_{int(coupon * 10):02d}_{i:03d}",
            "agency": agency,
            "sector": sector,
            "coupon": coupon,
            "wac": wac,
            "wala_months": wala,
            "wam_months": wam,
            "par_amount": par,
            "factor": round(rng.uniform(0.78, 1.00), 4),
            "price": price,
            "market_value": market_value,
            "unrealized_pnl": unrealized,
            "oad_years": oad,
            "oas_bps": oas,
            "book_yield": book_yield,
            "cpr_pct": cpr,
            "fico_avg": fico,
            "ltv_avg": ltv,
            "loan_size_avg_k": loan_size_k,
            "as_of_date": today.isoformat(),
            "trader": rng.choice(["alice", "bob", "carol", "david"]),
            "portfolio": "MAIN_BOOK",
        })
    df = pd.DataFrame(rows)
    return df


def _gen_embs_deals(n: int = 40, seed: int = 27) -> pd.DataFrame:
    """eMBS-style pool-level deal info.

    Columns are named to match the PrepaymentNN feature names exactly so the
    model can be applied directly without renames:
      `wac, age_months, rate_incentive_bps, burnout, fico, ltv, loan_size_k`
    """
    rng = np.random.default_rng(seed)
    current_rate_bps = 685  # 6.85% mortgage primary
    rows = []
    for i in range(n):
        agency = rng.choice(AGENCIES, p=[0.55, 0.30, 0.15])
        coupon = round(float(rng.choice([3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0],
                                        p=[0.05, 0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05])), 3)
        wac = round(coupon + rng.uniform(0.35, 0.70), 3)
        age = int(rng.uniform(0, 240))
        wam = max(360 - age, 12)
        # Rate incentive: positive when WAC > current; refi pressure
        rate_incentive_bps = round(wac * 100 - current_rate_bps + rng.normal(0, 8), 1)
        # Burnout: pools that have already had refi waves dampen further response
        burnout = round(min(max(rng.normal(age / 240, 0.18), 0.0), 1.0), 3)
        fico = int(np.clip(rng.normal(740, 30), 640, 820))
        ltv = round(rng.uniform(0.55, 0.92), 3)
        loan_size_k = round(rng.uniform(160, 700), 0)
        dti = round(rng.uniform(0.28, 0.45), 3)
        # Realistic prepay history: faster when incentive high & not burnt out
        s_curve = 12.0 / (1.0 + np.exp(-(rate_incentive_bps - 50) / 30))
        seasoning = min(age / 30, 1.0) * 4.0
        prepay = float((s_curve + seasoning) * (1.0 - 0.5 * burnout)
                        + (loan_size_k - 200) / 250 * 1.5
                        + rng.normal(0, 0.8))
        prepay = max(0.5, prepay)

        rows.append({
            "cusip": f"36202{rng.integers(100, 999)}{chr(65 + i % 26)}",
            "pool_id": f"{agency}_{int(coupon * 10):02d}_pool_{i:04d}",
            "agency": agency,
            "coupon": coupon,
            # PrepaymentNN feature names ↓ exact match
            "wac": wac,
            "age_months": age,
            "rate_incentive_bps": rate_incentive_bps,
            "burnout": burnout,
            "fico": fico,
            "ltv": ltv,
            "loan_size_k": loan_size_k,
            # additional standard columns
            "wam_months": wam,
            "factor": round(rng.uniform(0.55, 1.00), 4),
            "current_balance_mm": round(rng.uniform(120, 1200), 1),
            "loan_count": int(rng.uniform(180, 4500)),
            "dti_avg": dti,
            "top_state": rng.choice(STATES),
            "top_state_pct": round(rng.uniform(0.10, 0.32), 3),
            "lien_position": 1,
            "occupancy": rng.choice(["OWNER", "INVESTOR", "SECOND"], p=[0.85, 0.10, 0.05]),
            "cpr_3m": round(prepay * 0.95, 2),
            "cpr_6m": round(prepay, 2),
            "cpr_12m": round(prepay * 1.05, 2),
        })
    return pd.DataFrame(rows)


def _gen_macro_history(months: int = 36, seed: int = 41) -> pd.DataFrame:
    """36 months of historical rates + macro variables.

    Columns are aligned with what MortgageRateTSModel expects after light
    feature engineering (`ust_10y_pct`, `mbs_oas_bps`, `move_index`, plus a
    derived lag and first-difference). The verify.py script shows how.
    """
    rng = np.random.default_rng(seed)
    end = date(2026, 4, 1)

    # Build trending base series with realistic levels
    base_10y = 4.55
    walk = rng.normal(0, 0.18, months).cumsum() / np.sqrt(months)
    ust_10y = (base_10y + walk).clip(2.6, 5.5)
    ust_2y = (ust_10y + 0.20 + rng.normal(0, 0.18, months)).clip(2.0, 5.8)
    ust_5y = (ust_10y + 0.05 + rng.normal(0, 0.13, months)).clip(2.4, 5.4)
    ust_30y = (ust_10y + 0.30 + rng.normal(0, 0.10, months)).clip(2.8, 5.5)
    sofr = (ust_2y + 0.10 + rng.normal(0, 0.06, months)).clip(2.0, 5.7)

    mbs_oas_bps = (45 + rng.normal(0, 9, months)).clip(15, 95).round(1)
    move = (110 + rng.normal(0, 15, months)).clip(70, 180).round(1)
    vix = (16 + rng.normal(0, 4, months)).clip(10, 38).round(1)

    # Mortgage primary ≈ 0.92 * UST10Y + 0.012 * OAS + 0.0015 * MOVE + intercept
    mortgage_primary = (
        0.20 + 0.92 * ust_10y + 0.012 * mbs_oas_bps + 0.0015 * move
        + rng.normal(0, 0.06, months)
    ).clip(3.0, 9.0)
    mortgage_secondary = mortgage_primary - 0.45 - rng.normal(0, 0.05, months)

    unemployment = (3.85 + rng.normal(0, 0.18, months).cumsum() / np.sqrt(months)).clip(3.2, 7.5)
    gdp_yoy = (2.10 + rng.normal(0, 0.35, months)).clip(-2.0, 4.5)
    hpi_yoy = (3.40 + rng.normal(0, 1.2, months)).clip(-6.0, 8.0)
    cpi_yoy = (2.80 + rng.normal(0, 0.45, months)).clip(0.5, 6.0)

    dates = pd.date_range(end - pd.DateOffset(months=months - 1), periods=months, freq="MS")

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "ust_2y": ust_2y.round(3),
        "ust_5y": ust_5y.round(3),
        "ust_10y": ust_10y.round(3),
        "ust_30y": ust_30y.round(3),
        "sofr": sofr.round(3),
        "mortgage_30y_primary": mortgage_primary.round(3),
        "mortgage_30y_secondary": mortgage_secondary.round(3),
        "mbs_oas_bps": mbs_oas_bps,
        "move_index": move,
        "vix": vix,
        "unemployment_pct": unemployment.round(2),
        "gdp_yoy_pct": gdp_yoy.round(2),
        "cpi_yoy_pct": cpi_yoy.round(2),
        "hpi_yoy_pct": hpi_yoy.round(2),
    })


def _gen_macro_forecast(seed: int = 57) -> pd.DataFrame:
    """Forward-looking macro paths under four CCAR-style scenarios.

    12 months × 4 scenarios = 48 rows. Mirrors the structure of the built-in
    scenarios in `backend/routers/scenarios.py` but stored as a flat CSV the
    analyst can upload as a Dataset and wire into a workflow.
    """
    rng = np.random.default_rng(seed)
    horizons = list(range(1, 13))
    scenarios = {
        "Base": {
            "ust_10y":          [4.46, 4.42, 4.38, 4.30, 4.22, 4.15, 4.10, 4.05, 4.00, 3.95, 3.92, 3.90],
            "sofr":             [4.30, 4.20, 4.05, 3.90, 3.78, 3.65, 3.55, 3.50, 3.45, 3.42, 3.40, 3.38],
            "mortgage_30y":     [6.85, 6.80, 6.75, 6.65, 6.55, 6.45, 6.35, 6.30, 6.25, 6.20, 6.15, 6.10],
            "unemployment_pct": [3.80, 3.85, 3.90, 3.95, 4.00, 4.05, 4.10, 4.10, 4.10, 4.10, 4.10, 4.10],
            "gdp_yoy_pct":      [2.10, 2.05, 2.00, 1.95, 1.95, 2.00, 2.05, 2.10, 2.15, 2.15, 2.15, 2.15],
            "hpi_yoy_pct":      [3.50, 3.40, 3.30, 3.20, 3.10, 3.00, 2.90, 2.80, 2.75, 2.70, 2.70, 2.70],
            "mbs_oas_bps":      [44, 43, 42, 42, 41, 41, 40, 40, 40, 40, 40, 40],
            "move_index":       [112, 110, 108, 106, 104, 102, 100, 99, 98, 97, 96, 96],
        },
        "Adverse": {
            "ust_10y":          [4.46, 4.30, 4.10, 3.85, 3.60, 3.40, 3.25, 3.15, 3.10, 3.10, 3.15, 3.20],
            "sofr":             [4.30, 4.10, 3.85, 3.55, 3.20, 2.85, 2.60, 2.45, 2.35, 2.35, 2.40, 2.45],
            "mortgage_30y":     [6.85, 6.75, 6.55, 6.30, 6.00, 5.75, 5.55, 5.40, 5.30, 5.30, 5.35, 5.40],
            "unemployment_pct": [3.80, 4.10, 4.45, 4.85, 5.30, 5.75, 6.10, 6.30, 6.40, 6.40, 6.30, 6.20],
            "gdp_yoy_pct":      [2.10, 1.50, 0.80, -0.20, -0.90, -1.20, -1.00, -0.50, 0.20, 0.80, 1.20, 1.50],
            "hpi_yoy_pct":      [3.50, 2.20, 0.40, -1.50, -3.00, -4.00, -4.20, -3.80, -3.00, -2.00, -1.00, 0.00],
            "mbs_oas_bps":      [44, 50, 58, 68, 78, 84, 86, 84, 80, 75, 70, 66],
            "move_index":       [112, 125, 140, 155, 170, 175, 170, 160, 150, 140, 132, 126],
        },
        "Severely Adverse": {
            "ust_10y":          [4.46, 4.10, 3.65, 3.10, 2.55, 2.10, 1.80, 1.65, 1.60, 1.65, 1.75, 1.85],
            "sofr":             [4.30, 3.85, 3.30, 2.65, 2.00, 1.45, 1.05, 0.80, 0.65, 0.65, 0.75, 0.85],
            "mortgage_30y":     [6.85, 6.55, 6.05, 5.40, 4.75, 4.20, 3.85, 3.65, 3.55, 3.55, 3.65, 3.75],
            "unemployment_pct": [3.80, 4.50, 5.40, 6.50, 7.80, 9.00, 9.80, 10.20, 10.30, 10.10, 9.80, 9.40],
            "gdp_yoy_pct":      [2.10, 0.80, -1.20, -3.50, -5.20, -6.00, -5.20, -3.80, -2.20, -0.80, 0.40, 1.40],
            "hpi_yoy_pct":      [3.50, 0.50, -3.00, -7.00, -10.50, -13.00, -14.00, -13.20, -11.50, -9.00, -6.00, -3.00],
            "mbs_oas_bps":      [44, 58, 76, 96, 116, 130, 134, 128, 116, 102, 90, 80],
            "move_index":       [112, 138, 168, 200, 230, 248, 240, 220, 198, 178, 160, 146],
        },
        "Outlook": {
            "ust_10y":          [4.46, 4.40, 4.32, 4.25, 4.18, 4.12, 4.08, 4.05, 4.02, 4.00, 4.00, 4.00],
            "sofr":             [4.30, 4.22, 4.10, 3.98, 3.86, 3.74, 3.66, 3.60, 3.56, 3.54, 3.54, 3.54],
            "mortgage_30y":     [6.85, 6.80, 6.72, 6.65, 6.58, 6.52, 6.48, 6.45, 6.42, 6.40, 6.40, 6.40],
            "unemployment_pct": [3.80, 3.82, 3.85, 3.90, 3.95, 4.00, 4.05, 4.10, 4.10, 4.10, 4.10, 4.05],
            "gdp_yoy_pct":      [2.10, 2.10, 2.05, 2.00, 2.00, 2.05, 2.10, 2.15, 2.20, 2.25, 2.25, 2.25],
            "hpi_yoy_pct":      [3.50, 3.45, 3.40, 3.35, 3.30, 3.25, 3.25, 3.25, 3.25, 3.25, 3.25, 3.25],
            "mbs_oas_bps":      [44, 43, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42],
            "move_index":       [112, 110, 108, 107, 106, 105, 104, 103, 103, 103, 103, 103],
        },
    }

    rows = []
    base_date = pd.Timestamp(date(2026, 5, 1))
    for scen, paths in scenarios.items():
        for i, h in enumerate(horizons):
            row = {
                "scenario": scen,
                "horizon_months": h,
                "date": (base_date + pd.DateOffset(months=h - 1)).strftime("%Y-%m-%d"),
            }
            for var, vals in paths.items():
                row[var] = vals[i]
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    artifacts = [
        ("mbs_positions.csv",   _gen_positions(n=30)),
        ("embs_deal_info.csv",  _gen_embs_deals(n=40)),
        ("macro_history.csv",   _gen_macro_history(months=36)),
        ("macro_forecast.csv",  _gen_macro_forecast()),
    ]
    print(f"Writing sample data to {HERE}\n")
    for name, df in artifacts:
        path = HERE / name
        df.to_csv(path, index=False)
        size_kb = path.stat().st_size / 1024
        print(f"  [ok] {name:24s}  {len(df):>4} rows x {len(df.columns):>2} cols   {size_kb:>5.1f} KB")
    print("\nNext: run `python verify.py` to confirm each model can consume its file.")


if __name__ == "__main__":
    main()
