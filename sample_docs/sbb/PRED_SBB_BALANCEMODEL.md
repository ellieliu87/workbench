---
model_id: PRED_SBB_BALANCEMODEL
model_component: SBB Balance Model Suite
portfolio_scope: Legacy_COF, Discover_DFS
last_updated: 2026-04-19
---

# Small Business Banking (SBB) Balance Model Suite

Replaces the legacy single-equation SBB balance projection with a
**suite of five sub-models**. Introduced as part of CCAR-26.

## Sub-models in the suite

| Sub-model            | Drivers                                            |
|----------------------|----------------------------------------------------|
| SBB_Checking         | Merchant-acquiring volume, payroll-cycle indicator |
| SBB_Saving           | Excess cash above payroll buffer, fed funds        |
| SBB_NOW              | NOW-account thresholds, regulator-set tier rates   |
| SBB_LoanLinked       | Loan origination volume × historical sweep ratio   |
| SBB_DormantOverlay   | Decay rate for accounts with < 1 transaction / qtr |

The suite-level output `SBB_Average_Balance_mm` is the sum of the
five sub-model outputs — the orchestrator does not need to manage
this aggregation; the suite emits the total in the existing
`Average_Balance_mm` row of the PPNR output table for
`Product_L1 = "SBB"`.

## Why the change

The single-equation predecessor:
- **Conflated** merchant-volume-driven inflow with loan-linked sweep
  inflow. Under stress, merchant volume contracts but loan-linked
  sweep behaves differently (loans paid down → sweep evaporates).
  The single equation couldn't separate these signals.
- **Ignored dormant attrition**: ~3% of SBB Checking accounts go
  dormant per quarter, with steeper decay in stress. The new
  `SBB_DormantOverlay` sub-model captures this explicitly.

## DFS / Discover scope

Discover historically had a minimal SBB book (the $0.6B starting
balance in the integration is materially smaller than COF's $9.4B).
The full suite is **calibrated on Legacy COF data only**; DFS SBB
balances are scaled by a fixed 0.064 ratio and otherwise share the
same dynamics.

## Variance attribution caveat

When CCAR-26 SBB balances move materially vs CCAR-25, the
attribution must distinguish between:

- **Methodology change** (single equation → 5-sub-model suite)
  vs. **Scenario change** (rate path, unemployment, merchant volume).

A meaningful share of the observed CCAR-25 → CCAR-26 SBB delta is
the **methodology change itself**. Communicate this explicitly in the
variance walk so it doesn't read as a forecast revision.
