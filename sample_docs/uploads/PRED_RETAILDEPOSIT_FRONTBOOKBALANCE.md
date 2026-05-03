---
model_id: PRED_RETAILDEPOSIT_FRONTBOOKBALANCE
model_component: Frontbook Balance
portfolio_scope: Legacy_COF, Discover_DFS
suite_role: Volume — behavior of newly acquired accounts over the horizon
last_updated: 2026-04-08
---

# Frontbook Balance Model

Projects the balance trajectory of **newly originated** accounts —
the dollars `New Originations` brings into the bank — across the
9-quarter horizon. New Originations is the *inflow* model; Frontbook
is the *aging* model that takes those new dollars and projects how
they behave for the rest of the cycle.

Conceptually, a quarter's New Originations cohort enters the front of
the book. From PQ+1 onward those balances are governed by this
Frontbook model — *not* Backbook. After ~6 quarters new-cohort
behavior converges to the legacy Backbook curve and the cohort is
folded in for accounting purposes; the model still tracks them as
distinct paths in the run output.

## Methodology (canonical)

```
Frontbook(t, cohort_q) = Originated(cohort_q) × Π[1 - FrontChurn(s)]
                         for s = (cohort_q+1)..t

FrontChurn(t) = BaseChurn + Beta × max(0, CompetitorRate - OurRate)
              + DirectBankPremium  (Discover only)
```

`BaseChurn` for new cohorts is roughly 2× the Backbook BaseChurn for
the same product — fresh customers haven't yet built relationship
inertia.

## Why a separate model

Pre-integration, all DFS balances were modeled with a single
**PSAV-type** (price-sensitive amortizing volume) decay curve
calibrated to legacy Discover behavior. Two issues with that:

1. **Direct-bank churn signature**: DFS direct-bank customers
   re-shop more aggressively than COF's branch customers — a 25-bp
   competitor advantage triggers ~3× the outflow rate seen in COF
   data.
2. **MMA / liquid product divergence**: post-integration, MMA and
   high-yield savings show **balance attrition consistent with PSAV**
   under stress — a distinctive curve that legacy COF MMA does not
   exhibit.

CCAR-26 splits the DFS book into:

- **Frontbook** (this model): post-integration originations. Modeled
  with a freshly calibrated PSAV including the direct-bank churn
  signature.
- **Backbook**: inherited Discover deposits at integration close.
  Modeled with a slowly decaying legacy curve.

## Stress-scenario behavior

Under `CCAR_26_BHC_Stress`:

- **DFS Consumer Savings frontbook** decays ~80 bps/quarter faster
  than Legacy COF Savings — driven by the direct-bank churn term
  the legacy model lacked.
- **DFS Consumer CD frontbook** *grows* 1.0%/qtr (vs Legacy CD's
  0.5%/qtr stress inflow) because the DFS customer base is more rate-
  sensitive and shifts harder into CDs as Fed Funds cuts.
- **DFS Checking** stays small: starting at ~$4B and tracking flat
  with light attrition.

## Practical implication for PPNR variance

The **starting-point variance** between CCAR-25 and CCAR-26 includes
the entire DFS portfolio appearing for the first time — this isn't a
"scenario" effect, it's a **portfolio addition** effect. Variance
attribution must call this out explicitly so analysts don't read it
as a stress signal.

```
Starting-point variance contribution from DFS onboarding:
  Consumer_Savings: +$37.5B
  Consumer_CD:      +$12.9B
  Consumer_Checking: +$4.1B
  SBB:               +$0.6B
```
