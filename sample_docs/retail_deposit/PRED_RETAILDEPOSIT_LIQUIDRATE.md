---
model_id: PRED_RETAILDEPOSIT_LIQUIDRATE
model_component: Liquid Rate
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Pricing — rate paid on Savings / Checking / MMA, beta against Fed funds
last_updated: 2026-01-30
---

# Liquid Product Rate Paid Model

Models `Rate_Paid_APR` for liquid retail deposit products —
**Consumer_Savings**, **Consumer_Checking**, and **SBB** operating
accounts. The CD path is handled separately by
`PRED_RETAILDEPOSIT_CDRATE`.

## Methodology

For each product the rate-paid path is:

```
RatePaid(t) = AnchorRate + Beta * (FedFunds(t) - FedFunds(0))
              + ProductOverlay(t)
```

Calibrated betas:
- Consumer_Savings: **0.45**
- Consumer_Checking: **0.05**
- SBB: **0.55**

## 360 Savings Rate Paid Overlay

`Consumer_Savings` carries an explicit overlay: **the 360 Savings
Rate Paid Overlay**. This adds 25 bps of "competitive defense" pricing
during periods when the Fed Funds path is cutting more than 100 bps
cumulatively from PQ0. The overlay is **not modeled inside the rate
equation** — it is applied post-hoc as a deterministic adjustment.

**Why this matters for variance attribution**: when you compare
scenarios, the 360 overlay can show up as an unexplained 25 bp gap
in `Consumer_Savings` Rate Paid. This gap must be **explicitly
separated** from "modeled" rate movements when narrating the
variance walk — it is a **manual overlay**, not a model output.

## Limits

- Overlay activates per-scenario, not per-quarter. Once on, stays on
  through the horizon for that scenario.
- The overlay applies to Legacy COF only; DFS direct-bank pricing
  does not use it.
- Excluded from the model's predicted residual when calibrating beta.
