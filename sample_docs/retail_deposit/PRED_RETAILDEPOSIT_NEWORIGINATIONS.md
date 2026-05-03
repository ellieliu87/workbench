---
model_id: PRED_RETAILDEPOSIT_NEWORIGINATIONS
model_component: New Originations
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Volume — top-of-funnel inflow from outside the bank
last_updated: 2026-02-22
---

# New Originations / New Money Allocator

Models the share of incoming deposit dollars allocated across
products (Savings, CD, Checking, SBB) for each PQ.

## Methodology

A two-stage choice model:

1. **Inflow estimation** — total new deposit dollars per quarter from
   marketing op-ex, branch traffic, digital signups, and
   merchant-volume-derived SBB inflows.
2. **Allocation** — multinomial logistic over (Savings, CD, Checking,
   SBB) using as drivers:
   - Promo APY spread vs. competitor average.
   - 1YR Treasury rate (term incentive for CDs).
   - Unemployment rate (precautionary saving).
   - Consumer confidence index.

## 2026 cycle update — Discover frontbook onboarding

Following the DFS integration, **CCAR-26 introduces a separate
Discover frontbook allocator** for the new-money flowing into
`Portfolio = "Discover_DFS"`. The DFS allocator differs from Legacy
COF in two ways:

- **Higher CD share under stress**: when Fed Funds drops > 100 bps,
  DFS shifts ~12 pp of new money into CDs (vs ~6 pp at Legacy COF) —
  DFS's direct-bank customers chase yield more aggressively.
- **Lower checking share**: DFS has minimal branch presence so
  checking captures a smaller slice of new money (~5% vs ~18% at
  Legacy COF).

The DFS-specific allocator is documented as
`PRED_RETAILDEPOSIT_FRONTBOOKBALANCE_2026`.

## Marketing op-ex sensitivity

Reduced marketing spend in CCAR-26 BHC Stress lowers total inflow
~15% relative to base. This is the **smaller of the two main NII
drivers** (the larger is the Fed funds rate path itself flowing
through `RatePaid` and `FTP`).
