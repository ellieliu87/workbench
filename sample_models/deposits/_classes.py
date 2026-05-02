"""Deposit-suite model classes for the CMA Workbench demo.

Four small Python classes mimic Capital One's real internal libraries:

  - RDMaaS         Retail   Deposit Model-as-a-Service
  - CommMaaS       Commercial Deposit Model-as-a-Service
  - SBBMaaS        Small-Business Banking Deposit Model-as-a-Service
  - NIICalculator  Aggregates the three MaaS outputs into per-segment
                   monthly Net Interest Income (NII).

Contract:

  Each MaaS predict(X) returns (n_rows, 2) — *(rate_pct, balance_mm)*
  per month, with column names prefixed by the segment so three model
  outputs merge cleanly when wired in parallel into NII Calculator:
      RDMaaS    → rdmaas_rate_pct,    rdmaas_balance_mm
      CommMaaS  → commmaas_rate_pct,  commmaas_balance_mm
      SBBMaaS   → sbbmaas_rate_pct,   sbbmaas_balance_mm

  NIICalculator predict(X) returns (n_rows, 3) — *(nii per segment, mm)*
  per month: nii_rdmaas_mm, nii_commmaas_mm, nii_sbbmaas_mm. The
  formula per row is `balance × rate% / 100 / 12`.

The math is intentionally lightweight — these are demo artifacts, not
the production CCAR/PPNR estimators. Same shape and contract as the
real libraries, so the canvas workflow + multi_target output_kind path
exercises the full pipeline end-to-end.
"""
from __future__ import annotations

import numpy as np


class RDMaaS:
    """Retail Deposit Model-as-a-Service.

    Drivers (three families):
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
    output_kind = "multi_target"
    target_names = ["rdmaas_rate_pct", "rdmaas_balance_mm"]

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

            # column 0 → rate_pct, column 1 → balance_mm
            out[i, 0] = blended_apy
            out[i, 1] = balance
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
    target_names = ["commmaas_rate_pct", "commmaas_balance_mm"]

    starting_balance_mm = 180_000.0  # ~$180B commercial deposit base

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 2), dtype=float)
        balance = self.starting_balance_mm
        for i, row in enumerate(X):
            ff, beta, demand_idx, loc_util = row

            demand_effect = (demand_idx - 100.0) / 100.0 * 0.020
            loc_drag = -(loc_util - 50.0) / 100.0 * 0.015
            growth = demand_effect + loc_drag
            balance *= (1.0 + growth)

            paid_apy = ff * beta

            out[i, 0] = paid_apy
            out[i, 1] = balance
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
    target_names = ["sbbmaas_rate_pct", "sbbmaas_balance_mm"]

    starting_balance_mm = 45_000.0   # ~$45B small-business base

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 2), dtype=float)
        balance = self.starting_balance_mm
        for i, row in enumerate(X):
            ff, beta, mv_yoy, loans_mm = row

            mv_effect = (mv_yoy / 100.0) / 12.0
            loan_effect = (loans_mm / max(balance, 1.0)) * 0.30
            growth = mv_effect + loan_effect
            balance *= (1.0 + growth)

            paid_apy = ff * beta

            out[i, 0] = paid_apy
            out[i, 1] = balance
        return out


class NIICalculator:
    """Net Interest Income calculator.

    Reads the three MaaS outputs (rate + balance per segment per month)
    and returns the monthly NII contribution of each deposit product
    over the next 9 quarters.

      NII per segment (in $MM) = balance_mm × rate_pct / 100 / 12

    The orchestrator merges the three upstream model frames on `month`
    so by the time predict(X) runs, X carries all six columns. Three
    NII columns are emitted (one per segment) so a downstream
    destination — or a Reporting tile — can pivot per segment or sum to
    the total.
    """

    feature_names = [
        "rdmaas_rate_pct",   "rdmaas_balance_mm",
        "commmaas_rate_pct", "commmaas_balance_mm",
        "sbbmaas_rate_pct",  "sbbmaas_balance_mm",
    ]
    output_kind = "multi_target"
    target_names = ["nii_rdmaas_mm", "nii_commmaas_mm", "nii_sbbmaas_mm"]

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros((len(X), 3), dtype=float)
        for i, row in enumerate(X):
            rd_rate, rd_bal, cm_rate, cm_bal, sb_rate, sb_bal = row
            out[i, 0] = rd_bal * (rd_rate / 100.0) / 12.0
            out[i, 1] = cm_bal * (cm_rate / 100.0) / 12.0
            out[i, 2] = sb_bal * (sb_rate / 100.0) / 12.0
        return out
