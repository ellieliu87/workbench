---
model_id: PRED_RETAILDEPOSIT_BRANCHBALANCE
model_component: Branch Balance
portfolio_scope: Legacy_COF
suite_role: Volume — physical-branch account stickiness
last_updated: 2026-02-18
---

# Branch Balance Model

Isolates **physical-branch accounts** from the digital book. Branch
customers are demographically older, hold relationships across
products, and exhibit a fundamentally different attrition curve than
direct-bank customers — a single liquid-balance equation would dilute
both signals.

## Why a separate model

In legacy data, branch checking balances exhibit:

- **5x lower rate sensitivity** than digital savings — branch
  customers rarely move money for a 25-bp competitor advantage.
- **Stickier under stress** — branch attrition rises only ~0.2 pp/qtr
  under stress, vs ~0.5 pp/qtr for digital savings.
- **Spending-driven churn** — outflows correlate with consumer
  spending (negative for the bank), not with rates. Unemployment ↑ →
  precautionary spend ↓ → branch checking balance ↑.

Combining branch + digital into one equation produced biased betas
in both — branch artificially raised the digital beta, and digital
artificially lowered the branch beta.

## Methodology

```
BranchBalance(t) = BranchBalance(0) × Π[1 - BranchChurn(s)]

BranchChurn(t) = 0.4%/q (base)
                + 0.10 × max(0, Unemployment(t) - 4.0)   # spend driver
                + 0.05 × Beta × max(0, CompetitorRate - OurRate)
```

The rate term carries `Beta = 0.05` — five times below the digital
liquid-rate beta of 0.25.

## Suite linkages

- **Input**: 1y Treasury, Unemployment Rate from the macro path; our
  branch checking rate from `Liquid Rate` (with branch overlay).
- **Output feeds**: subtracted from Backbook for the branch slice in
  the `Total Balance` orchestration.
- **Excluded**: Branch accounts do **not** participate in `Liquid-CD
  Migration` — branch customers historically don't open CDs from a
  branch checking sweep at scale.

## DFS scope

Discover has no branch network. This model applies to Legacy COF
only — DFS branch_balance contribution is zero by construction.

## Caveats

- The branch-attrition rate floor is **not** zero — even in a
  zero-stress baseline, ~0.4%/q of branch checking attrites due to
  natural account closures (death, relocation, switching for
  unrelated reasons). Variance attribution should not narrate this
  as a stress signal.
- The model holds branch share of liquid book at ~14% by assumption;
  the actual share varies slowly with branch closures (handled
  outside this model).
