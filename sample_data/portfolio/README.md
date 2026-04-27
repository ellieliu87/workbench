# Portfolio Sample Data

Realistic data files for the Investment Portfolio function. Every file is
shaped to be consumed directly by one of the sample models in
`cma/sample_models/portfolio/`.

| File | Rows × Cols | Consumed by | What it represents |
|---|---|---|---|
| `mbs_positions.csv` | 30 × 24 | `interest_income_calc.pkl` | SimCorp-style position book (CUSIPs, par, coupon, WAM, factor, OAD, OAS, sector, trader). |
| `embs_deal_info.csv` | 40 × 23 | `prepayment_nn.pkl` | eMBS pool-level data with the exact column names PrepaymentNN expects (`wac`, `age_months`, `rate_incentive_bps`, `burnout`, `fico`, `ltv`, `loan_size_k`). |
| `macro_history.csv` | 36 × 15 | `mortgage_rate_ts.pkl` | 36 months of UST curve, SOFR, MBS OAS, MOVE/VIX, mortgage primary/secondary, plus unemployment / GDP / HPI / CPI year-over-year. |
| `macro_forecast.csv` | 48 × 11 | (any forward-looking workflow) | 12-month forward paths under four CCAR-style scenarios (Base / Adverse / Severely Adverse / Outlook). Same shape as the workbench's built-in scenarios; upload it as a Dataset and bind it as a Scenario in the Data tab. |

## Try it end-to-end

```bash
cd cma/sample_data/portfolio
python generate.py        # write the four CSVs (deterministic seeds)
python verify.py          # load each CSV + run the matching model
```

`verify.py` proves the integration is real: it predicts CPRs on every pool,
back-tests the mortgage-rate regression against actual primary rates,
projects 12 months of interest income off the position book, and runs a 500-path
BGM Monte-Carlo simulation.

## Use them in the workbench

1. **Workspace → Investment Portfolio → Data → Upload File** — drop each CSV
   to bind it as a Dataset.
2. **Workspace → Investment Portfolio → Models → Upload Artifact** — drop each
   `.pkl` from `cma/sample_models/portfolio/`.
3. **Workspace → Investment Portfolio → Workflow** — drag a dataset and a model
   onto the canvas, wire them up, hit Run. Send results to a Snowflake / OneLake
   / S3 / CSV destination.
4. **Workspace → Investment Portfolio → Analytics** — build plots and tables
   from any dataset, workflow output, or ad-hoc upload.

## Column-name conventions

`embs_deal_info.csv` uses **exactly** the feature names PrepaymentNN was trained
on, so no renaming is needed. Other models need a small feature-engineering
step before scoring (lag, first-difference, scaling) — see `verify.py` for the
canonical recipes.

## Regenerate

`python generate.py` rewrites all four files with deterministic seeds. Edit
the `_gen_*` helpers in that script to add columns, change ranges, or scale up
row counts.
