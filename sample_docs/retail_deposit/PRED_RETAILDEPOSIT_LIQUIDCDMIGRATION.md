---
model_id: PRED_RETAILDEPOSIT_LIQUIDCDMIGRATION
model_component: Liquid-CD Migration (the internal connector)
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Internal flow — money moving between liquid and term within the bank
last_updated: 2026-03-30
---

# Liquid-CD Migration Model

The "two-way street" model. Calculates how much money **moves
internally** between liquid products (Savings / MMA / Checking) and
Certificates of Deposit each quarter — without leaving the bank.

This is the only model in the suite that *both* removes from one
product and adds to another. Every other model only adds or only
subtracts.

## Why it matters

When CD rates run materially above MMA / Savings rates, customers
notice. Historical data shows:

- A **100-bp CD-vs-Savings spread** widening triggers ~2.5% of
  Savings stock to migrate into CDs over the following 2 quarters.
- The migration is **asymmetric**: when CDs become *less* attractive
  (rates compress), only ~0.6% of CD stock migrates back per
  quarter — CDs are sticky on the way out by design.

Without this model, CD inflows during stress periods get
double-counted (once via CD New Originations, once via Liquid-Backbook
attrition).

## Methodology

```
MigrationOut(t) =  α₁ × max(0, CDRate(t) - LiquidRate(t) - Spread*) × Backbook(t-1)
                  - α₂ × max(0, LiquidRate(t) - CDRate(t) + Spread*)  × CDStock(t-1)
```

- `α₁` = 0.025 per quarter per 100 bp of incentive spread.
- `α₂` = 0.006 per quarter (the asymmetric reverse).
- `Spread*` is a customer-perceived "stickiness threshold" — about
  35 bps. Spreads below this don't trigger migration (transaction
  cost / inertia).

The output is the dollar amount removed from the Backbook
(`MigrationOut`) and added to CD `Net Inflow` for that quarter.

## Stress-scenario behavior

Under BHC Stress:
- Fed Funds cuts compress both Liquid and CD rates, but **CDs lag** —
  contract rates locked at PQ0 don't reset.
- Result: CD-vs-Liquid spread *widens* at the front of stress (PQ1-3),
  driving ~3-4% of Backbook into CDs.
- By PQ5+, new CD originations reprice to lower fed funds, the
  spread normalizes, and migration reverts to ~0.

## Suite linkages

The migration is the **±** term in the Grand Orchestration formula:

```
Total Balance = (Existing Backbook - Attrition) + New Originations ± Internal Migration
```

- **Inputs**: `Liquid Rate` model (our liquid rates) + `CD Rate`
  model (our CD rates) + Backbook stock + CD stock.
- **Outputs**:
  - Subtracts from `Backbook Balance` for the source product.
  - Adds to CD net inflow alongside `New Originations`.
- **Note**: Migration is independent of `Branch Balance` — branch
  customers historically do not migrate to CDs at scale.

## Caveats

- The model assumes migration happens *within the same portfolio*
  (Legacy_COF → Legacy_COF, DFS → DFS). Cross-portfolio migration
  (a Legacy customer opening a DFS CD) is captured in `New
  Originations` for the receiving portfolio.
- Calibrated on pre-2024 data; the post-DFS-integration spread
  behavior is being recalibrated in CCAR-27.
