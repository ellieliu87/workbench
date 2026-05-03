---
model_id: PRED_RETAILDEPOSIT_CDRATE
model_component: CD Rate
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Pricing — sets the rate paid on Certificates of Deposit
last_updated: 2026-03-15
---

# CD Rate Paid Model

Models the average rate paid on Consumer CD balances under each
scenario. Drives `Interest_Expense` for `Product_L1 = "Consumer_CD"`.

## Methodology

The CD rate-paid path is benchmarked against an **external peer index**
plus an internal beta. For each projection quarter PQ:

```
RatePaid_CD(t) = BenchmarkIndex(t) − CompetitiveSpread + ProductMixAdj(t)
```

Where:
- `BenchmarkIndex` is an average rate paid across a defined set of
  peer banks publishing CD curves.
- `CompetitiveSpread` is COF's deliberate offer relative to the index
  (typically 5-25 bps below).
- `ProductMixAdj` reflects the term mix shift (1Y / 2Y / 5Y CDs).

## 2026 cycle update — Big 8 → Big 6 benchmark

Effective CCAR-26, the benchmark index was reconstituted from the
**Big 8** to the **Big 6** peer set. The change reflects the
**Discover Financial Services (DFS) integration**: with Discover now
inside Capital One, the previous "Big 8" peer set double-counted
Discover and Capital One. The "Big 6" set drops both legacy entries
and adds two regional peers with comparable CD product breadth.

Practical impact:
- The Big 6 publishes 12-18 bps **higher** average CD rates than the
  Big 8 across the projection horizon.
- All else equal, this raises projected `Rate_Paid_APR` for
  `Consumer_CD` by ~10-15 bps in CCAR-26 vs CCAR-25.
- This is a **structural pricing shift**, not a scenario-driven move.

## Discover-specific overlay

For `Portfolio = "Discover_DFS"`, an additional **+10 bps DFS
benchmark uplift** is applied on top of the Big 6 anchor — DFS's
direct-bank model historically pays a higher rate than Capital One's
branch-anchored CD book. This overlay is implemented in code as a
literal `+0.10` after the legacy rate path computation.

## Caveats

- The model does not yet reflect any post-integration repricing
  toward a unified COF-DFS CD ladder; that's a 2027 cycle update.
- Early-withdrawal behavior (`PRED_RETAILDEPOSIT_CDEARLYWITHDRAWAL`)
  is a separate model — interactions are linear, not coupled.
