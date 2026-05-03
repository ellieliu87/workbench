---
model_id: PRED_RETAILDEPOSIT_CDATTRITION
model_component: CD Attrition (early withdrawal + non-renewal)
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Volume — exit logic for term deposits
last_updated: 2026-03-22
---

# CD Attrition Model

Models the two ways CD balances leave the bank:

1. **Early Withdrawal** — customer breaks the CD before maturity,
   accepts the early-withdrawal penalty, redirects the funds.
2. **Non-Renewal** — at maturity, the customer takes the cash out
   instead of rolling into a new CD.

Both paths feed the orchestration's `Attrition` term for CDs.

## Methodology

### Early Withdrawal

A logistic function of the **rate-spread incentive**:

```
P(EarlyWithdrawal | qtr) = 1 / (1 + exp(-z))
z = α + β × (CompetitorCDRate - OurContractRate - PenaltyAdjustedSpread)
```

Where `PenaltyAdjustedSpread` discounts the breakeven for the
remaining-tenor early-withdrawal penalty (typically 90 days of
interest for short CDs, 180 days for >2y).

Default calibration: `α = -3.5`, `β = 0.6` per percentage point.

### Non-Renewal

A simple choice probability at maturity:

```
P(Renew | maturity) = base_renewal_rate × ChoiceMultiplier
```

`base_renewal_rate` = 62% (legacy COF historical). `ChoiceMultiplier`
adjusts for:
- Market CD rate vs our offered renewal rate (positive → more likely
  to renew).
- 1y Treasury rate level (high rates → some customers prefer T-bills).

## Stress-scenario behavior

Stress paths typically **reduce** CD attrition:

- Lower competitor rates → less incentive to break early or shop
  elsewhere at maturity.
- Stressed depositors prefer the higher CD rate over uncertain Savings
  rates → renewal probability rises ~5 pp.

This is the primary reason CDs *grow* under stress in the
orchestration, even as Savings/Checking attrites.

## Suite linkages

- **Input**: `CD Rate` model (our offered rates) + macro inputs
  (1y Treasury, BBB Spread).
- **Output**: feeds the `Attrition` term in the Grand Orchestration's
  `Total Balance = (Backbook − Attrition) + New Originations ±
  Migration` formula, but only for the CD slice.
- **Interaction**: `Liquid-CD Migration` adds inflows on top of
  what New Originations contributes — so the CD net flow in any
  quarter is `Migration_in + NewOriginations - EarlyWithdrawal -
  NonRenewal`.

## Caveats

- The model treats CD tenors > 5y as a single bucket; pre-2024 vintages
  may have idiosyncratic behavior the suite does not capture.
- Non-renewal probability is set at maturity, not over the quarter —
  if a CD matures mid-quarter, the full balance is decisioned in that
  quarter.
