"""End-to-end check: each sample model in `cma/sample_models/portfolio/`
actually consumes the matching sample data file and produces a real result.

Run after `generate.py`. Expected output: four checks all passing with real
numbers - predicted CPRs, projected mortgage rates, monthly interest income,
simulated forward-rate paths.
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
MODEL_DIR = DATA_DIR.parent.parent / "sample_models" / "portfolio"

# Make the model classes importable (they were dumped from a __main__ script).
# We use the same trick as the workbench: import generate.py as a module so the
# classes are findable by name.
import importlib.util


def _load_model(filename: str):
    """Load a pickle that may reference classes from `sample_models/portfolio/generate.py`."""
    gen_path = MODEL_DIR / "generate.py"
    spec = importlib.util.spec_from_file_location("cma_sample_generate", gen_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cma_sample_generate"] = mod
    spec.loader.exec_module(mod)

    # Map __main__.X -> cma_sample_generate.X during unpickle
    class _ResilientUnpickler(pickle.Unpickler):
        def find_class(self, module: str, name: str):
            if module == "__main__" and hasattr(mod, name):
                return getattr(mod, name)
            return super().find_class(module, name)

    with open(MODEL_DIR / filename, "rb") as f:
        return _ResilientUnpickler(f).load()


def _section(title: str) -> None:
    print(f"\n{'-' * 72}\n  {title}\n{'-' * 72}")


# -- 1. PrepaymentNN on eMBS deal info ---------------------------------
def check_prepayment_on_embs() -> None:
    _section("PrepaymentNN  <-  embs_deal_info.csv")
    model = _load_model("prepayment_nn.pkl")
    df = pd.read_csv(DATA_DIR / "embs_deal_info.csv")

    # The CSV columns already match the model's feature names exactly.
    X = df[model.feature_names].to_numpy(dtype=float)
    cprs = model.predict(X)

    df["predicted_cpr_pct"] = cprs.round(2)
    print(f"Pools scored: {len(df)}")
    print(f"Predicted CPR - min {cprs.min():.2f}%   median {np.median(cprs):.2f}%   max {cprs.max():.2f}%")
    print("Top 5 fastest pools:")
    head = df.nlargest(5, "predicted_cpr_pct")[
        ["pool_id", "agency", "wac", "age_months", "rate_incentive_bps", "fico", "predicted_cpr_pct"]
    ]
    print(head.to_string(index=False))


# -- 2. MortgageRateTSModel on macro_history ---------------------------
def check_mortgage_rate_on_macro() -> None:
    _section("MortgageRateTSModel  <-  macro_history.csv")
    model = _load_model("mortgage_rate_ts.pkl")
    df = pd.read_csv(DATA_DIR / "macro_history.csv")

    # Build the engineered feature set the model expects:
    #   [ust_10y_pct, mbs_oas_bps, move_index_scaled, mortgage_30y_lag1_pct, delta_ust_10y_pct]
    feats = pd.DataFrame({
        "ust_10y_pct":            df["ust_10y"],
        "mbs_oas_bps":            df["mbs_oas_bps"],
        "move_index_scaled":      df["move_index"] / 1000,
        "mortgage_30y_lag1_pct":  df["mortgage_30y_primary"].shift(1).fillna(df["mortgage_30y_primary"].iloc[0]),
        "delta_ust_10y_pct":      df["ust_10y"].diff().fillna(0.0),
    })
    preds = model.predict(feats.to_numpy(dtype=float))
    actual = df["mortgage_30y_primary"].to_numpy()
    err = preds - actual

    print(f"Months scored: {len(df)}")
    print(f"Predicted vs actual mortgage 30Y primary:")
    print(f"  predicted - mean {preds.mean():.3f}%   range [{preds.min():.3f}%, {preds.max():.3f}%]")
    print(f"  actual    - mean {actual.mean():.3f}%   range [{actual.min():.3f}%, {actual.max():.3f}%]")
    print(f"  residual  - MAE {np.mean(np.abs(err)):.4f} pp   max |err| {np.max(np.abs(err)):.4f} pp")


# -- 3. InterestIncomeCalc on positions --------------------------------
def check_interest_income_on_positions() -> None:
    _section("InterestIncomeCalc  <-  mbs_positions.csv")
    model = _load_model("interest_income_calc.pkl")
    df = pd.read_csv(DATA_DIR / "mbs_positions.csv")

    # Convert position rows -> list of dicts for InterestIncomeCalc.project()
    positions = [
        {
            "cusip": r["cusip"],
            "balance": r["par_amount"] * r["factor"],
            "coupon": r["coupon"],
            "wam": int(r["wam_months"]),
            "cpr_pct": r["cpr_pct"],
        }
        for _, r in df.iterrows()
    ]
    result = model.project(positions, horizon_months=12)
    schedule = pd.DataFrame(result["schedule"])
    print(f"Positions: {len(positions)}   horizon: 12 months")
    print(f"Total projected interest income: ${result['total_interest_income']:,.0f}")
    print("Monthly schedule:")
    print(schedule.to_string(index=False))


# -- 4. BGM term structure simulator ------------------------------------
def check_bgm_simulation() -> None:
    _section("BGM05TermStructure  ->  forward-rate Monte-Carlo paths")
    model = _load_model("bgm_term_structure.pkl")
    out = model.simulate_paths(n_paths=500, horizon_years=2.0, dt=1 / 12)
    paths = out["paths"]  # (n_steps+1, n_paths, n_tenors)
    times = out["time_years"]
    tenors = out["tenors"]
    print(f"n_paths: {paths.shape[1]:,}   n_steps: {paths.shape[0]}   n_tenors: {paths.shape[2]}")
    print(f"Mean reversion kappa: {model.mean_reversion}")
    print(f"Tenor grid: {list(tenors)}")
    print("Mean simulated forward rates by tenor (terminal):")
    terminal_mean = paths[-1].mean(axis=0)
    for t, r in zip(tenors, terminal_mean):
        print(f"  t={t:>5} yr   mean = {r * 10000:.1f} bps   std = {paths[-1, :, list(tenors).index(t)].std() * 10000:.1f} bps")


def main() -> None:
    print(f"Sample data dir : {DATA_DIR}")
    print(f"Sample model dir: {MODEL_DIR}")
    check_prepayment_on_embs()
    check_mortgage_rate_on_macro()
    check_interest_income_on_positions()
    check_bgm_simulation()
    print(f"\n{'-' * 72}\n  All 4 model-data integrations passed.\n{'-' * 72}")


if __name__ == "__main__":
    main()
