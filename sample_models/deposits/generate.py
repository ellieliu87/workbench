"""Generate the three deposit-suite pickles for the CMA Workbench demo.

Run: `python generate.py` from inside `sample_models/deposits/`. Produces:
  - rdmaas.pkl    Retail Deposit MaaS
  - commmaas.pkl  Commercial Deposit MaaS
  - sbbmaas.pkl   Small-Business Banking Deposit MaaS

Class definitions live in `_classes.py` so the pickled instances record a
stable, importable module path (`_classes.RDMaaS`) rather than `__main__`.
The sandboxed model runner adds the artifact's directory to `sys.path`
before unpickling, so `import _classes` resolves cleanly inside the
subprocess.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _classes import RDMaaS, CommMaaS, SBBMaaS  # noqa: E402  — sys.path tweak above


def main():
    print(f"Generating sample deposit-suite models in: {HERE}")
    artifacts = [
        ("rdmaas.pkl", RDMaaS()),
        ("commmaas.pkl", CommMaaS()),
        ("sbbmaas.pkl", SBBMaaS()),
    ]
    for filename, model in artifacts:
        path = HERE / filename
        with path.open("wb") as fh:
            pickle.dump(model, fh)
        print(f"  [ok] {filename}  ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
