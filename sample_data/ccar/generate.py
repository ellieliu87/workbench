"""Generate CCAR scenario data — `ccar_scenarios.csv` (wide format).

Two cycles (CCAR25, CCAR26) × four scenarios (BHCB, BHCS, FedB, FedSA)
× ten quarters (PQ0..PQ9). The macro-variable values per
(cycle, scenario, pq) are stored as `<scenario_lower>_<variable>`
columns so the workbench's plot tiles can render two lines per chart
via `y_fields=["bhcb_<x>", "bhcs_<x>"]` — the renderer has no
group-by, so wide format is the contract.

Macro variables shipped (per the user's spec):
  - unemployment_rate_pct
  - employment_growth_yoy_pct
  - hpi_yoy_pct                   (Home Price Appreciation, y/y)
  - cre_price_yoy_pct             (Commercial RE Price, y/y)
  - gdp_qoq_annl_pct              (Real GDP growth, q/q ann'lzd)
  - m2_billions
  - oil_price_usd_bbl
  - fed_funds_pct                 (Fed funds target)
  - ust_1y_pct                    (1-year Treasury)
  - ust_10y_pct                   (10-year Treasury)
  - bbb_spread_bps
  - m2_to_gdp_ratio               (precomputed M2 / nominal GDP)

Run: `python generate.py` from inside `sample_data/ccar/`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
N_PQ = 10  # PQ0..PQ9 — PQ0 is the cycle's start quarter

# Anchored nominal GDP (in $B) used to derive M2/GDP. Real value at the
# scenario start; the scenario evolves it via the q/q ann'l growth path.
GDP_START_BILLIONS = {"CCAR25": 28_500.0, "CCAR26": 29_700.0}


def _smooth(start: float, end: float, n: int = N_PQ) -> np.ndarray:
    """Smooth linear interpolation start → end over n points."""
    return np.linspace(start, end, n)


def _vshape(start: float, trough: float, recovery: float, trough_pq: int = 5, n: int = N_PQ) -> np.ndarray:
    """V-shape trajectory: start → trough at `trough_pq` → recovery at PQ(n-1)."""
    pq = np.arange(n)
    out = np.empty(n)
    descent = trough_pq
    ascent = (n - 1) - trough_pq
    for i in range(n):
        if i <= trough_pq:
            t = i / max(descent, 1)
            out[i] = start + (trough - start) * t
        else:
            t = (i - trough_pq) / max(ascent, 1)
            out[i] = trough + (recovery - trough) * t
    return out


def _trajectory(scenario: str, cycle: str) -> dict[str, np.ndarray]:
    """Build the 10-point trajectory for one (scenario, cycle).

    Anchored on plausible Q4 starting values that drift apart by cycle:
      - CCAR25 starts Q4-2024 (slightly higher rates, slightly lower unemployment)
      - CCAR26 starts Q4-2025 (rates a notch lower, unemployment a notch higher)
    """
    # Cycle-anchored starting values
    if cycle == "CCAR25":
        u0 = 3.8;  ff0 = 4.75; u1y0 = 4.80; u10y0 = 4.40; bbb0 = 125;  hpi0 = 4.0; cre0 = 0.0; oil0 = 78.0
    else:  # CCAR26
        u0 = 4.0;  ff0 = 4.50; u1y0 = 4.55; u10y0 = 4.30; bbb0 = 130;  hpi0 = 3.0; cre0 = -1.0; oil0 = 80.0

    # M2 in $B — same starting level both cycles for cross-cycle comparability;
    # it'll glide differently per scenario.
    m2_0 = 21_000.0

    pq = np.arange(N_PQ)

    if scenario == "BHCB":  # Bank's baseline — mild expansion
        return dict(
            unemployment_rate_pct=     u0 + 0.030 * pq,
            employment_growth_yoy_pct= 1.5 - 0.05 * pq,
            hpi_yoy_pct=               hpi0 - 0.10 * pq,
            cre_price_yoy_pct=         cre0 + 0.20 * pq,
            gdp_qoq_annl_pct=          2.0 - 0.02 * pq,
            m2_billions=               m2_0 * (1.0 + 0.04 / 4) ** pq,
            oil_price_usd_bbl=         oil0 - 0.4 * pq + 0.5 * np.sin(pq / 2.0),
            fed_funds_pct=             ff0 - 0.10 * pq,
            ust_1y_pct=                u1y0 - 0.10 * pq,
            ust_10y_pct=               u10y0 - 0.04 * pq,
            bbb_spread_bps=            bbb0 - 1.2 * pq,
        )

    if scenario == "BHCS":  # Bank's adverse — mild recession
        return dict(
            unemployment_rate_pct=     u0 + 0.55 * np.minimum(pq, 5) - 0.10 * np.maximum(pq - 5, 0),
            employment_growth_yoy_pct= 1.0 - 0.55 * np.minimum(pq, 4) + 0.50 * np.maximum(pq - 4, 0),
            hpi_yoy_pct=               hpi0 - 0.8 * np.minimum(pq, 5) + 0.7 * np.maximum(pq - 5, 0),
            cre_price_yoy_pct=         cre0 - 1.4 * np.minimum(pq, 5) + 1.4 * np.maximum(pq - 5, 0),
            gdp_qoq_annl_pct=          np.where(pq <= 3, 2.0 - 1.5 * pq, -2.5 + 0.6 * (pq - 3)),
            m2_billions=               m2_0 * (1.0 + 0.005 / 4) ** pq,
            oil_price_usd_bbl=         np.where(pq <= 4, oil0 - 6.0 * pq, oil0 - 24.0 + 2.0 * (pq - 4)),
            fed_funds_pct=             np.maximum(ff0 - 0.50 * pq, 1.50),
            ust_1y_pct=                np.maximum(u1y0 - 0.55 * pq, 1.40),
            ust_10y_pct=               np.maximum(u10y0 - 0.30 * pq, 2.50),
            bbb_spread_bps=            bbb0 + 25.0 * np.minimum(pq, 4) + 4.0 * np.maximum(pq - 4, 0),
        )

    if scenario == "FedB":  # Fed baseline — gentler than BHCB
        return dict(
            unemployment_rate_pct=     u0 + 0.040 * pq,
            employment_growth_yoy_pct= 1.4 - 0.06 * pq,
            hpi_yoy_pct=               hpi0 - 0.12 * pq,
            cre_price_yoy_pct=         cre0 + 0.18 * pq,
            gdp_qoq_annl_pct=          1.8 - 0.02 * pq,
            m2_billions=               m2_0 * (1.0 + 0.035 / 4) ** pq,
            oil_price_usd_bbl=         oil0 - 0.5 * pq,
            fed_funds_pct=             ff0 - 0.08 * pq,
            ust_1y_pct=                u1y0 - 0.08 * pq,
            ust_10y_pct=               u10y0 - 0.03 * pq,
            bbb_spread_bps=            bbb0 - 1.0 * pq,
        )

    # FedSA — Fed Severely Adverse
    return dict(
        unemployment_rate_pct=     u0 + 1.10 * np.minimum(pq, 5) - 0.20 * np.maximum(pq - 5, 0),
        employment_growth_yoy_pct= 1.0 - 1.0 * np.minimum(pq, 4) + 0.6 * np.maximum(pq - 4, 0),
        hpi_yoy_pct=               hpi0 - 3.0 * np.minimum(pq, 6) + 1.5 * np.maximum(pq - 6, 0),
        cre_price_yoy_pct=         cre0 - 4.5 * np.minimum(pq, 6) + 2.0 * np.maximum(pq - 6, 0),
        gdp_qoq_annl_pct=          np.where(pq <= 3, 2.0 - 3.0 * pq, -7.0 + 1.5 * (pq - 3)),
        m2_billions=               m2_0 * (1.0 - 0.015 / 4) ** pq,
        oil_price_usd_bbl=         np.where(pq <= 4, oil0 - 11.0 * pq, oil0 - 44.0 + 3.0 * (pq - 4)),
        fed_funds_pct=             np.maximum(ff0 - 1.20 * pq, 0.25),
        ust_1y_pct=                np.maximum(u1y0 - 1.20 * pq, 0.30),
        ust_10y_pct=               np.maximum(u10y0 - 0.50 * pq, 2.00),
        bbb_spread_bps=            bbb0 + 70.0 * np.minimum(pq, 4) + 10.0 * np.maximum(pq - 4, 0),
    )


def _gdp_level_path(gdp_growth_qoq_annl: np.ndarray, gdp_start: float) -> np.ndarray:
    """Convert q/q annualized growth into a level path so M2/GDP is meaningful.

    `g_qoq_annl` per quarter compounds each quarter at (1 + g/100)^(1/4)."""
    out = np.empty(len(gdp_growth_qoq_annl))
    out[0] = gdp_start
    for i in range(1, len(gdp_growth_qoq_annl)):
        out[i] = out[i - 1] * (1.0 + gdp_growth_qoq_annl[i] / 100.0) ** 0.25
    return out


def _period_label(start_year: int, start_q: int, pq: int) -> str:
    """E.g. (2024, 4, 0) -> '2024Q4'; (2024, 4, 1) -> '2025Q1'."""
    quarters_in = (start_q - 1) + pq          # 0-indexed q
    year = start_year + quarters_in // 4
    q = (quarters_in % 4) + 1
    return f"{year}Q{q}"


CYCLE_START = {
    "CCAR25": (2024, 4),
    "CCAR26": (2025, 4),
}
SCENARIOS = ["BHCB", "BHCS", "FedB", "FedSA"]
MACROS = [
    "unemployment_rate_pct",
    "employment_growth_yoy_pct",
    "hpi_yoy_pct",
    "cre_price_yoy_pct",
    "gdp_qoq_annl_pct",
    "m2_billions",
    "oil_price_usd_bbl",
    "fed_funds_pct",
    "ust_1y_pct",
    "ust_10y_pct",
    "bbb_spread_bps",
    "m2_to_gdp_ratio",
]


# Peak-summary table is for the Reporting tab. For each macro variable
# we report the WORST-CASE value during the 9-quarter horizon. "Worst"
# is direction-aware:
#   • unemployment + BBB spread → max  (peak stress = higher)
#   • everything else            → min  (peak stress = lower:
#                                        rate cuts, GDP trough, HPI/CRE
#                                        decline, oil drop, employment
#                                        contraction).
# M2 and 1-year UST are excluded per spec.
PEAK_DIRECTION = {
    "unemployment_rate_pct":     ("max", "Unemployment rate (%)"),
    "employment_growth_yoy_pct": ("min", "Employment growth (y/y, %)"),
    "hpi_yoy_pct":               ("min", "Home Price Appreciation (y/y, %)"),
    "cre_price_yoy_pct":         ("min", "CRE Price Appreciation (y/y, %)"),
    "gdp_qoq_annl_pct":          ("min", "Real GDP (q/q ann'l, %)"),
    "oil_price_usd_bbl":         ("min", "Oil price ($/bbl)"),
    "fed_funds_pct":             ("min", "Fed funds target (%)"),
    "ust_10y_pct":               ("min", "10-year UST (%)"),
    "bbb_spread_bps":            ("max", "BBB spread (bp)"),
}


def main():
    print(f"Generating CCAR scenario data in: {HERE}")
    rows: list[dict] = []
    # Stash the per-(cycle, scenario) trajectories so we can derive the
    # peak summary in a second pass without rebuilding them.
    traj_cache: dict[tuple[str, str], dict[str, np.ndarray]] = {}

    for cycle, (year, q) in CYCLE_START.items():
        for sc in SCENARIOS:
            traj = _trajectory(sc, cycle)
            gdp_level = _gdp_level_path(traj["gdp_qoq_annl_pct"], GDP_START_BILLIONS[cycle])
            traj["m2_to_gdp_ratio"] = traj["m2_billions"] / gdp_level
            traj_cache[(cycle, sc)] = traj

        for pq in range(N_PQ):
            row: dict = {
                "cycle":  cycle,
                "pq":     f"PQ{pq}",
                "period": _period_label(year, q, pq),
            }
            for sc in SCENARIOS:
                prefix = sc.lower()
                t = traj_cache[(cycle, sc)]
                for var in MACROS:
                    row[f"{prefix}_{var}"] = round(float(t[var][pq]), 4)
            rows.append(row)

    df = pd.DataFrame(rows)
    out_path = HERE / "ccar_scenarios.csv"
    df.to_csv(out_path, index=False)
    print(f"  [ok] {out_path.name}  ({len(df)} rows × {len(df.columns)} cols)")

    # ── Peak-summary table ─────────────────────────────────────────────
    # rows = macro variable, columns = bhcb_25 / bhcb_26 / bhcs_25 /
    # bhcs_26 (only the BHC pair per spec). Values = peak over PQ0..PQ9.
    summary_rows: list[dict] = []
    cycle_short = {"CCAR25": "25", "CCAR26": "26"}
    for var, (direction, display) in PEAK_DIRECTION.items():
        out: dict = {"macro": display}
        for sc in ("BHCB", "BHCS"):
            for cycle in ("CCAR25", "CCAR26"):
                t = traj_cache[(cycle, sc)]
                series = t[var]
                value = float(series.max() if direction == "max" else series.min())
                # bps stays an integer-y display; keep 2 dp otherwise
                col = f"{sc.lower()}_{cycle_short[cycle]}"
                out[col] = round(value, 1 if "bps" in var else 2)
        summary_rows.append(out)

    summary = pd.DataFrame(summary_rows, columns=["macro", "bhcb_25", "bhcb_26", "bhcs_25", "bhcs_26"])
    summary_path = HERE / "ccar_peak_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"  [ok] {summary_path.name}  ({len(summary)} rows × {len(summary.columns)} cols)")


if __name__ == "__main__":
    main()
