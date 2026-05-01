"""Generate four sample portfolio model files for the CMA Workbench Models tab.

Run with `python generate.py` from inside `sample_models/portfolio/`. Produces:
  - prepayment_nn.pkl       — neural network CPR predictor (sklearn MLP)
  - bgm_term_structure.pkl  — Brace-Gatarek-Musiela 0.5 forward-rate model
  - mortgage_rate_ts.pkl    — time-series regression for primary mortgage rate
  - interest_income_calc.pkl — fixed-income interest income calculator

The class definitions live in `_classes.py` so the pickled instances record
a stable, importable module path (`_classes.MortgageRateTSModel` rather than
`__main__.MortgageRateTSModel`). The sandboxed model runner adds the
artifact's directory to `sys.path` before unpickling, so `import _classes`
resolves cleanly inside the subprocess.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Ensure `_classes` resolves whether you launch this script from the repo
# root or from inside the directory.
sys.path.insert(0, str(HERE))

from _classes import (  # noqa: E402  — sys.path tweak above is intentional
    PrepaymentNN,
    BGM05TermStructure,
    MortgageRateTSModel,
    InterestIncomeCalc,
)


def main():
    print(f"Generating sample portfolio models in: {HERE}")

    artifacts = [
        ("prepayment_nn.pkl", PrepaymentNN()),
        ("bgm_term_structure.pkl", BGM05TermStructure()),
        ("mortgage_rate_ts.pkl", MortgageRateTSModel()),
        ("interest_income_calc.pkl", InterestIncomeCalc()),
    ]

    for name, obj in artifacts:
        path = HERE / name
        with open(path, "wb") as f:
            pickle.dump(obj, f)
        size_kb = path.stat().st_size / 1024
        meta = getattr(obj, "metadata", {})
        print(f"  [ok] {name:30s}  {size_kb:6.1f} KB   "
              f"family={meta.get('model_family', '?'):20s} "
              f"v={meta.get('version', '?')}")

    print("\nReady to upload via Workspace > Investment Portfolio > Models > Upload Artifact.")


if __name__ == "__main__":
    main()
