"""Generate four sample portfolio model files for the CMA Workbench Models tab.

Run once with `python generate.py`. Produces:
  - prepayment_nn.pkl       — neural network CPR predictor (sklearn MLP)
  - bgm_term_structure.pkl  — Brace-Gatarek-Musiela 0.5 forward-rate model
  - mortgage_rate_ts.pkl    — time-series regression for primary mortgage rate
  - interest_income_calc.pkl — fixed-income interest income calculator

Each file pickles a self-contained Python object with sensible defaults so it
loads cleanly with joblib / pickle.load. The classes are deliberately small but
realistic — they expose `.predict()` (or domain-specific methods) and a
`.metadata` dict that downstream code can introspect.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor


HERE = Path(__file__).resolve().parent


# ── 1. Prepayment NN ────────────────────────────────────────────────────────
class PrepaymentNN:
    """Neural-network CPR predictor.

    Inputs (in order): wac, age_months, rate_incentive_bps, burnout, fico, ltv, loan_size_k.
    Output: annualized CPR (Constant Prepayment Rate, % per year).

    Fitted on synthetic data calibrated to typical agency MBS prepay behavior:
      - Higher rate incentive (lower current vs WAC) → faster prepay
      - Burnout dampens response after sustained refi waves
      - Younger pools prepay slower than seasoned pools
    """

    def __init__(self):
        rng = np.random.default_rng(0)
        n = 4000
        wac = rng.uniform(3.0, 7.5, n)
        age = rng.uniform(0, 240, n)
        # rate_incentive: positive = WAC > current rate → strong refi incentive
        incentive = rng.normal(0, 80, n)
        burnout = rng.uniform(0, 1, n)
        fico = rng.normal(740, 30, n).clip(580, 820)
        ltv = rng.uniform(0.5, 0.95, n)
        loan_size_k = rng.uniform(150, 700, n)

        # Synthetic CPR with realistic non-linear shape
        s_curve = 12.0 / (1.0 + np.exp(-(incentive - 50) / 25))
        seasoning = np.minimum(age / 30, 1.0) * 4.0
        burnout_factor = (1.0 - 0.6 * burnout)
        size_premium = (loan_size_k - 200) / 250 * 1.5
        fico_premium = (fico - 700) / 50 * 0.8
        cpr = (s_curve + seasoning) * burnout_factor + size_premium + fico_premium
        cpr = np.clip(cpr + rng.normal(0, 1.2, n), 0.5, 60)

        X = np.column_stack([wac, age, incentive, burnout, fico, ltv, loan_size_k])
        y = cpr

        self.model = MLPRegressor(
            hidden_layer_sizes=(16, 8),
            activation="relu",
            solver="adam",
            max_iter=2000,
            random_state=0,
            early_stopping=True,
            validation_fraction=0.15,
        )
        self.model.fit(X, y)
        self.feature_names = [
            "wac", "age_months", "rate_incentive_bps", "burnout",
            "fico", "ltv", "loan_size_k",
        ]
        self.target_name = "cpr_annualized_pct"
        self.metadata = {
            "model_family": "neural_network",
            "framework": "scikit-learn",
            "architecture": "MLP(16, 8)",
            "trained_on": "synthetic agency MBS prepay panel (n=4000)",
            "train_score_r2": float(self.model.score(X, y)),
            "version": "1.0.0",
            "owner": "Capital Markets — Mortgage Analytics",
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def predict(self, X) -> np.ndarray:
        return self.model.predict(np.asarray(X, dtype=float))


# ── 2. BGM 0.5 Term Structure ──────────────────────────────────────────────
@dataclass
class BGM05TermStructure:
    """Brace-Gatarek-Musiela forward-LIBOR model with mean reversion 0.5.

    Calibrated to a typical post-2024 swaption surface. `simulate_paths()`
    returns Monte-Carlo forward-rate paths under the spot measure that can be
    fed into MBS pricing engines or NII simulations.
    """

    mean_reversion: float = 0.5
    n_factors: int = 3
    tenor_grid_yrs: tuple[float, ...] = (0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30)
    forward_rates_bps: tuple[float, ...] = (
        450, 455, 460, 455, 450, 461, 470, 484, 488, 480, 472,
    )
    instantaneous_volatility_bps: tuple[float, ...] = (
        92, 88, 86, 82, 78, 75, 72, 68, 60, 56, 52,
    )
    correlation_decay: float = 0.18
    factor_loadings: tuple[tuple[float, float, float], ...] = field(
        default_factory=lambda: (
            (0.92,  0.38, -0.05),  # 0.25y
            (0.93,  0.32, -0.08),
            (0.95,  0.18, -0.10),
            (0.96,  0.04, -0.12),
            (0.97, -0.10, -0.10),
            (0.96, -0.22, -0.04),
            (0.95, -0.28,  0.04),
            (0.93, -0.30,  0.14),
            (0.90, -0.28,  0.22),
            (0.87, -0.24,  0.28),
            (0.84, -0.18,  0.32),
        )
    )
    seed: int = 42

    def __post_init__(self):
        self.metadata = {
            "model_family": "term_structure",
            "model_type": "BGM (Brace-Gatarek-Musiela)",
            "mean_reversion_kappa": self.mean_reversion,
            "n_factors": self.n_factors,
            "tenor_grid_yrs": list(self.tenor_grid_yrs),
            "calibrated_to": "USD swaption surface, Q1 2026",
            "version": "0.5.1",
            "owner": "Capital Markets — Rates Quants",
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def correlation_matrix(self) -> np.ndarray:
        n = len(self.tenor_grid_yrs)
        T = np.array(self.tenor_grid_yrs)
        diff = np.abs(T[:, None] - T[None, :])
        return np.exp(-self.correlation_decay * diff)

    def simulate_paths(self, n_paths: int = 1000, horizon_years: float = 10.0,
                        dt: float = 1 / 12) -> dict[str, np.ndarray]:
        """Monte-Carlo forward-rate paths. Returns dict with 'time', 'paths' (n_steps, n_paths, n_tenors)."""
        rng = np.random.default_rng(self.seed)
        n_steps = int(horizon_years / dt)
        n_tenors = len(self.tenor_grid_yrs)

        f0 = np.array(self.forward_rates_bps) / 10000.0
        sigma = np.array(self.instantaneous_volatility_bps) / 10000.0
        corr = self.correlation_matrix()
        L = np.linalg.cholesky(corr + 1e-10 * np.eye(n_tenors))
        kappa = self.mean_reversion

        paths = np.zeros((n_steps + 1, n_paths, n_tenors))
        paths[0] = f0[None, :]
        for t in range(n_steps):
            z = rng.standard_normal((n_paths, n_tenors))
            shocks = z @ L.T
            mean_revert = kappa * (f0[None, :] - paths[t]) * dt
            diffusion = sigma[None, :] * np.sqrt(dt) * shocks
            paths[t + 1] = paths[t] + mean_revert + diffusion

        return {
            "time_years": np.linspace(0, horizon_years, n_steps + 1),
            "tenors": np.array(self.tenor_grid_yrs),
            "paths": paths,
        }


# ── 3. Mortgage Rate — Time Series Regression ─────────────────────────────
class MortgageRateTSModel:
    """Time-series regression for the 30-year primary mortgage rate.

    Linear model:
      mortgage_30y_t = a + b1·UST_10y_t + b2·MBS_OAS_t + b3·MOVE_t/1000
                          + b4·mortgage_30y_{t-1} + b5·d_UST_10y_t

    Fitted on synthetic 36-month history calibrated to typical primary-secondary
    spread dynamics.
    """

    def __init__(self):
        rng = np.random.default_rng(7)
        n = 36
        ust10 = 4.50 + rng.normal(0, 0.25, n).cumsum() / np.sqrt(n)
        mbs_oas_bps = 45 + rng.normal(0, 8, n)
        move = 110 + rng.normal(0, 15, n)
        d_ust10 = np.diff(ust10, prepend=ust10[0])
        # "True" relationship for synthetic generation
        m30_lag = 6.50 + rng.normal(0, 0.05, n)
        m30 = (
            0.20
            + 0.92 * ust10
            + 0.012 * mbs_oas_bps
            + 0.0015 * move
            + 0.05 * m30_lag
            + 0.30 * d_ust10
            + rng.normal(0, 0.04, n)
        )

        X = np.column_stack([ust10, mbs_oas_bps, move / 1000, m30_lag, d_ust10])
        y = m30

        self.model = LinearRegression()
        self.model.fit(X, y)
        self.feature_names = [
            "ust_10y_pct", "mbs_oas_bps", "move_index_scaled",
            "mortgage_30y_lag1_pct", "delta_ust_10y_pct",
        ]
        self.target_name = "mortgage_30y_primary_pct"
        self.metadata = {
            "model_family": "time_series_regression",
            "framework": "scikit-learn",
            "architecture": "OLS with engineered lag + first-difference features",
            "trained_on": "36 months of synthetic IHS macro feeds",
            "coefficients": {
                f: float(c) for f, c in zip(self.feature_names, self.model.coef_)
            },
            "intercept": float(self.model.intercept_),
            "train_score_r2": float(self.model.score(X, y)),
            "version": "2.3.0",
            "owner": "Capital Markets — Mortgage Strategy",
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def predict(self, X) -> np.ndarray:
        return self.model.predict(np.asarray(X, dtype=float))


# ── 4. Fixed-Income Interest Income Calculator ────────────────────────────
@dataclass
class InterestIncomeCalc:
    """Fixed-income interest income projection model.

    Computes month-by-month coupon income for an MBS / treasury portfolio,
    accounting for scheduled paydowns and (optional) prepayment-driven
    unscheduled paydowns.

    Usage:
        calc = InterestIncomeCalc()
        result = calc.project(positions_df, horizon_months=12, cpr_overrides={...})
    """

    accrual_basis: str = "act/360"
    pay_frequency: str = "monthly"
    scheduled_amort_method: str = "level_pay"
    default_cpr_pct: float = 8.5
    floor_balance_pct: float = 0.05  # treat <5% factor as fully paid

    def __post_init__(self):
        self.metadata = {
            "model_family": "fixed_income_calc",
            "model_type": "Cash-flow projection — coupon + paydown",
            "accrual_basis": self.accrual_basis,
            "amort_method": self.scheduled_amort_method,
            "version": "1.4.2",
            "owner": "Capital Markets — Income & FTP",
            "created_at": datetime.now().astimezone().isoformat(),
        }

    def _monthly_coupon(self, balance: float, coupon_pct: float) -> float:
        return balance * (coupon_pct / 100.0) / 12.0

    def _scheduled_paydown(self, balance: float, wam: int) -> float:
        if wam <= 0:
            return balance
        return balance * (1.0 / max(wam, 1))

    def _unscheduled_paydown(self, balance: float, cpr_pct: float) -> float:
        smm = 1 - (1 - cpr_pct / 100.0) ** (1 / 12)
        return balance * smm

    def project(
        self,
        positions: list[dict[str, Any]],
        horizon_months: int = 12,
        cpr_overrides: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Project monthly interest income for a list of position dicts."""
        cpr_overrides = cpr_overrides or {}
        rows: list[dict[str, Any]] = []
        for m in range(1, horizon_months + 1):
            month_income = 0.0
            month_paydown = 0.0
            for p in positions:
                cusip = p.get("cusip") or p.get("position_id", "")
                bal = float(p.get("balance", p.get("par_amount", 0.0)))
                coupon = float(p.get("coupon", 0.0))
                wam = int(p.get("wam", p.get("wam_months", 360)))
                cpr = float(cpr_overrides.get(cusip, p.get("cpr_pct", self.default_cpr_pct)))

                # Run prior months (replay since stateless)
                running = bal
                for _ in range(m - 1):
                    running -= self._scheduled_paydown(running, wam)
                    running -= self._unscheduled_paydown(running, cpr)
                    if running < bal * self.floor_balance_pct:
                        running = 0.0
                        break
                if running == 0.0:
                    continue

                income = self._monthly_coupon(running, coupon)
                sched = self._scheduled_paydown(running, wam)
                unsched = self._unscheduled_paydown(running, cpr)
                month_income += income
                month_paydown += sched + unsched

            rows.append({
                "month": m,
                "interest_income": round(month_income, 2),
                "paydown": round(month_paydown, 2),
            })
        total = sum(r["interest_income"] for r in rows)
        return {
            "schedule": rows,
            "total_interest_income": round(total, 2),
            "horizon_months": horizon_months,
            "n_positions": len(positions),
        }


# ── runner ──────────────────────────────────────────────────────────────────
def main():
    print(f"Generating sample portfolio models in: {HERE}")

    artifacts = [
        ("prepayment_nn.pkl", PrepaymentNN()),
        ("bgm_term_structure.pkl", BGM05TermStructure()),
        ("mortgage_rate_ts.pkl", MortgageRateTSModel()),
        ("interest_income_calc.pkl", InterestIncomeCalc()),
    ]

    for name, obj in artifacts:
        path = HERE / name
        with open(path, "wb") as f:
            pickle.dump(obj, f)
        size_kb = path.stat().st_size / 1024
        meta = getattr(obj, "metadata", {})
        print(f"  [ok] {name:30s}  {size_kb:6.1f} KB   "
              f"family={meta.get('model_family', '?'):20s} "
              f"v={meta.get('version', '?')}")

    print("\nReady to upload via Workspace > Investment Portfolio > Models > Upload Artifact.")


if __name__ == "__main__":
    main()
