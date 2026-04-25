# Portfolio Sample Models

Four ready-to-upload model artifacts for the Investment Portfolio function.

| File | Family | Description |
|---|---|---|
| `prepayment_nn.pkl` | Neural Network | scikit-learn `MLPRegressor(16, 8)` predicting CPR from WAC, age, rate incentive, burnout, FICO, LTV, loan size. Trained on a synthetic agency MBS prepay panel. |
| `bgm_term_structure.pkl` | BGM (Brace-Gatarek-Musiela) | 3-factor forward-LIBOR model with mean reversion κ = 0.5, calibrated to a Q1 2026 USD swaption surface. Provides `simulate_paths(n_paths, horizon_years)`. |
| `mortgage_rate_ts.pkl` | Time-Series Regression | OLS for the 30Y primary mortgage rate using UST 10Y, MBS OAS, MOVE, lagged rate, and ΔUST as features. |
| `interest_income_calc.pkl` | Fixed-Income Calc | Cash-flow projector — monthly coupon income with scheduled and prepay-driven paydowns. `project(positions, horizon_months, cpr_overrides=None)`. |

## Upload them

In CMA Workbench: **Workspace → Investment Portfolio → Models → Upload Artifact**.
Browse to this folder and pick a `.pkl` file. The Workbench records metadata
and renders a model card. (For safety, uploaded artifacts are not loaded into
the API process; their structure is only described from the file metadata.)

## Regenerate

```bash
python generate.py
```

Outputs four `.pkl` files in this directory, deterministic seeds, no network
needed.
