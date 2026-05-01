"""Deposit-suite model classes for the CMA Workbench demo.

Three small Python classes mimic Capital One's real internal libraries:
  - RDMaaS    Retail Deposit Model-as-a-Service
  - CommMaaS  Commercial Deposit Model-as-a-Service
  - SBBMaaS   Small-Business Banking Deposit Model-as-a-Service

Each class:
  - Sets `feature_names` so the sandboxed runner picks the right columns
    out of the (intentionally wider) Data Harness output table.
  - Implements `predict(X)` returning a 2-D ndarray shaped (n_rows, 2)
    where columns are [end_balance_mm, interest_income_mm].

The math is intentionally lightweight — these are demo artifacts, not the
production CCAR/PPNR estimators. Same shape and contract as the real
libraries, so the canvas workflow + multi_target output_kind path
exercises the full pipeline end-to-end.
"""
from __future__ import annotations

import numpy as np


class RDMaaS:
    """Retail Deposit Model-as-a-Service.

    Drivers — the three families the user asked for:
      pricing strategy:    retail_promo_apy_pct, retail_standard_apy_pct
      competitive pricing: competitor_apy_avg_pct, apy_spread_vs_market_bps
      account information: active_accounts_k, avg_balance_per_acct_usd,
                           account_attrition_pct
    """

    feature_names = [
        "retail_promo_apy_pct",
        "retail_standard_apy_pct",
        "competitor_apy_avg_pct",
        "apy_spread_vs_market_bps",
        "active_accounts_k",
        "avg_balance_per_acct_usd",
        "account_attrition_pct",
    ]
    # Library-author-declared metadata. Read at install time by the
    # workbench so the analyst doesn't have to specify these in the
    # install dialog.
    output_kind = "multi_target"
    target_names = ["end_balance_mm", "interest_income_mm"]

    starting_balance_mm = 240_000.0  # ~$240B retail deposit base
    promo_weight = 0.30              # 30% of accounts on promo, 70% on standard

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 2), dtype=float)
        balance = self.starting_balance_mm
        for i, row in enumerate(X):
            promo, std, competitor, spread_bps, acct_k, avg_bal, attr_pct = row

            # Spread vs. market: every +25 bp of advantage → +0.40% net inflow.
            spread_effect = (spread_bps / 25.0) * 0.0040
            # Account-base growth/decline relative to a 50M baseline.
            account_effect = (acct_k / 50_000.0 - 1.0) * 0.010
            # Attrition reads as monthly % churn — direct drag on balance.
            attrition_drag = -(attr_pct / 100.0)
            # Avg-balance signal — proxy for primary-account share.
            balance_quality = (avg_bal / 8_000.0 - 1.0) * 0.003

            growth = spread_effect + account_effect + attrition_drag + balance_quality
            balance *= (1.0 + growth)

            blended_apy = self.promo_weight * promo + (1 - self.promo_weight) * std
            interest_income = balance * (blended_apy / 100.0) / 12.0

            out[i, 0] = balance
            out[i, 1] = interest_income
        return out


class CommMaaS:
    """Commercial Deposit Model-as-a-Service.

    Drivers: corporate treasury demand, line-of-credit utilization, and
    deposit beta against the policy rate.
    """

    feature_names = [
        "fed_funds_pct",
        "commercial_deposit_beta",
        "corp_treasury_demand_idx",
        "loc_utilization_pct",
    ]
    output_kind = "multi_target"
    target_names = ["end_balance_mm", "interest_income_mm"]

    starting_balance_mm = 180_000.0  # ~$180B commercial deposit base

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 2), dtype=float)
        balance = self.starting_balance_mm
        for i, row in enumerate(X):
            ff, beta, demand_idx, loc_util = row

            # Treasury-demand index, normalized around 100.
            demand_effect = (demand_idx - 100.0) / 100.0 * 0.020
            # LOC utilization above 50% signals corporates drawing down cash —
            # negative signal for the deposit balance.
            loc_drag = -(loc_util - 50.0) / 100.0 * 0.015
            growth = demand_effect + loc_drag
            balance *= (1.0 + growth)

            paid_apy = ff * beta
            interest_income = balance * (paid_apy / 100.0) / 12.0

            out[i, 0] = balance
            out[i, 1] = interest_income
        return out


class SBBMaaS:
    """Small-Business Banking Deposit Model-as-a-Service.

    Drivers: merchant-acquiring volume, new SB loan originations (which
    cycle into operating-account balances), and deposit beta.
    """

    feature_names = [
        "fed_funds_pct",
        "sb_deposit_beta",
        "merchant_volume_yoy_pct",
        "sb_loan_originations_mm",
    ]
    output_kind = "multi_target"
    target_names = ["end_balance_mm", "interest_income_mm"]

    starting_balance_mm = 45_000.0   # ~$45B small-business base

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 2), dtype=float)
        balance = self.starting_balance_mm
        for i, row in enumerate(X):
            ff, beta, mv_yoy, loans_mm = row

            # YoY merchant volume growth → swept deposits, divided by 12 to
            # get the monthly contribution.
            mv_effect = (mv_yoy / 100.0) / 12.0
            # ~30% of newly originated loan balances persist as deposits.
            loan_effect = (loans_mm / max(balance, 1.0)) * 0.30
            growth = mv_effect + loan_effect
            balance *= (1.0 + growth)

            paid_apy = ff * beta
            interest_income = balance * (paid_apy / 100.0) / 12.0

            out[i, 0] = balance
            out[i, 1] = interest_income
        return out
