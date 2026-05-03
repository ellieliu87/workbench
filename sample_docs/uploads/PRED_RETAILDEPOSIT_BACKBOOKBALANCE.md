---
model_id: PRED_RETAILDEPOSIT_BACKBOOKBALANCE
model_component: Backbook Balance (retention)
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Volume — retention of existing liquid balances
last_updated: 2026-02-04
---

# Backbook Balance Model

Projects how much of the **already-on-book** liquid balance — Savings,
Checking, MMA — remains in each projection quarter. The companion to
the New Originations model: New Originations adds inflow, this model
estimates retention of the stock.

## Methodology

Customer-cohort retention curve with rate sensitivity. For each
liquid product:

```
Backbook(t) = Backbook(0) × Π[1 - AttritionRate(s)] for s = 1..t

AttritionRate(t) = BaseChurn + Beta × max(0, CompetitorRate(t) - OurRate(t))
                  + StressOverlay(t)
```

Calibrated parameters:

| Product           | BaseChurn (q/q) | Rate Beta |
|-------------------|-----------------|-----------|
| Consumer_Savings  | 1.4%            | 0.020     |
| Consumer_Checking | 0.8%            | 0.005     |
| MMA               | 1.6%            | 0.025     |

`Beta` is the marginal attrition per 1 bp of competitor rate
advantage above our offer.

## Stress overlay

Under BHC Stress / Fed SA, an additional +0.5 pp / quarter
churn rate applies to Savings and MMA — captures the
"flight-to-yield" behavior when Fed cuts compress our offer below the
Big 6 average.

## Suite linkages (Grand Orchestration)

- **Inputs**: `Liquid Rate` model output (our rate per product) +
  `CD Rate` model (used as the competing internal yield, see Liquid-CD
  Migration).
- **Outputs feed**: `Total_Balance = Backbook - Attrition + New
  Originations ± Internal Migration`. Backbook is the largest term
  on the right-hand side (~70-80% of liquid stock at horizon end).
- **Special interactions**:
  - Outflows from Backbook are net of `Liquid-CD Migration` — when CDs
    look attractive, balances move internally rather than leaving the bank.
  - `Branch Balance` (sticky physical-branch accounts) is modeled
    separately to avoid the digital-channel rate sensitivity blowing
    up branch attrition.

## Caveats

- Calibrated on Legacy COF historical data; DFS direct-bank cohort
  attrition is steeper and modeled separately (see
  `PRED_RETAILDEPOSIT_FRONTBOOKBALANCE`).
- The `BaseChurn` term does not include account closures driven by
  fraud/operational events — those are excluded as one-off shocks.
