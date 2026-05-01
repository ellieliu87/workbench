"""Sandboxed model-prediction runner.

Loads a user-uploaded model artifact (`.pkl`, `.joblib`, `.onnx`) inside a
short-lived **subprocess** and calls `predict` / `predict_proba`. The
subprocess gets the artifact path + input matrix via JSON files on disk
and writes its output the same way; nothing the model imports lands in
the FastAPI worker's address space, so a malicious or buggy pickle
crashes the subprocess and not the server.

Wall-clock timeout (default 30 s) bounds runaway models. The subprocess
also runs the optional pre-transform expression on the input frame so
the user can declare engineered features (lags, first differences, etc.)
without us evaling untrusted code in-process.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger("cma.model_runner")

# The script the subprocess actually runs. Kept inline so we don't ship a
# separate file the user could overwrite. Reads the input bundle, loads
# the artifact, runs the optional pre-transform on the dataframe, calls
# predict / predict_proba, and writes the output bundle.
_RUNNER_SCRIPT = r'''
import json, os, sys, traceback
import numpy as np

OUT_PATH = sys.argv[2]


def _fail(error, tb=""):
    with open(OUT_PATH, "w") as fh:
        json.dump({"ok": False, "error": str(error), "traceback": tb}, fh)
    sys.exit(0)


try:
    in_path = sys.argv[1]
    with open(in_path) as fh:
        bundle = json.load(fh)

    artifact_path = bundle["artifact_path"]
    file_format = bundle["file_format"]

    # Make sibling .py files (e.g. `_classes.py`) importable. Pickles often
    # reference a class by `<module>.<ClassName>`; if the module is shipped
    # alongside the artifact (common pattern for custom estimators), this
    # `sys.path.insert` lets `pickle.load` resolve it.
    artifact_dir = os.path.dirname(os.path.abspath(artifact_path))
    if artifact_dir and artifact_dir not in sys.path:
        sys.path.insert(0, artifact_dir)
    feature_columns = bundle.get("feature_columns") or []
    feature_mapping = bundle.get("feature_mapping") or {}  # {model_input: csv_column}
    df_records = bundle.get("df", [])
    pre_transform = bundle.get("pre_transform") or ""
    output_kind = bundle.get("output_kind") or "scalar"

    import pandas as pd
    df = pd.DataFrame(df_records)

    # ── Optional pre-transform — runs inside this subprocess on the
    #    ORIGINAL CSV column names so the user's expressions reference
    #    what they see in their dataset (e.g. df['ust_10y'].diff()).
    if pre_transform.strip():
        local_ns = {"df": df, "pd": pd, "np": np}
        try:
            exec(pre_transform, {"__builtins__": __builtins__}, local_ns)
            df = local_ns.get("df", df)
        except Exception as e:
            _fail(f"pre_transform failed: {e}", traceback.format_exc()[-1500:])

    # ── Apply feature mapping AFTER pre-transform so columns the user
    #    just engineered (e.g. delta_ust_10y, mortgage_30y_lag1) are
    #    visible to the rename. Mapping shape: {model_input: csv_column}
    #    — rename csv_column → model_input.
    if feature_mapping:
        existing_lower = {str(c).lower(): c for c in df.columns}
        rename_map = {}
        for model_name, csv_col in feature_mapping.items():
            if not csv_col or csv_col == model_name:
                continue
            actual = existing_lower.get(str(csv_col).lower())
            if actual is not None:
                rename_map[actual] = model_name
        if rename_map:
            df = df.rename(columns=rename_map)

    # ── Load the artifact FIRST so we can introspect its expected
    #    feature names when the user didn't declare them. Loading is what
    #    needs the artifact's directory on sys.path and the optional
    #    `_*.py` sidecar — pre-transform + mapping have already run on
    #    the dataframe by this point.
    if file_format in ("pkl", "pickle"):
        import pickle
        with open(artifact_path, "rb") as fh:
            model = pickle.load(fh)
    elif file_format == "joblib":
        import joblib
        model = joblib.load(artifact_path)
    elif file_format == "onnx":
        # ONNX path is handled below; for the pre-introspection branch
        # we leave `model` unset and fall through to the ONNX block.
        model = None
    else:
        _fail(f"Unsupported model format '{file_format}'")
        model = None  # unreachable; _fail exits

    # ── Introspect the model's expected feature names if the caller
    #    didn't declare any. Tries (in order):
    #      1. `model.feature_names`     — custom convention (our pack
    #                                     classes set this).
    #      2. `model.feature_names_in_` — sklearn estimators fitted with
    #                                     a column-named DataFrame.
    #    Falls through to all-numeric only when neither is present.
    if not feature_columns and model is not None:
        # Probe the artifact, the underlying instance for bound methods,
        # and finally __self__'s class for class-level declarations.
        probes = [model, getattr(model, "__self__", None)]
        guess = None
        for p in probes:
            if p is None:
                continue
            guess = getattr(p, "feature_names", None) or getattr(p, "feature_names_in_", None)
            if guess is not None:
                break
        if guess is not None:
            try:
                feature_columns = [str(x) for x in list(guess)]
            except Exception:
                feature_columns = []

    # ── Resolve feature columns case-insensitively against the (possibly
    #    transformed and renamed) dataframe.
    col_map = {str(c).lower(): c for c in df.columns}
    actual_cols = []
    missing = []
    for name in feature_columns:
        actual = col_map.get(str(name).lower())
        if actual is None:
            missing.append(name)
        else:
            actual_cols.append(actual)
    if missing:
        _fail(
            "Feature(s) not found in dataset: "
            f"{missing}. Available columns: {list(df.columns)}"
        )

    # No declared features and the model didn't expose names — last-ditch
    # fall back to all numeric columns. Errors out cleanly if there are none.
    if not actual_cols:
        actual_cols = [
            c for c in df.select_dtypes(include="number").columns if str(c).lower() != "month"
        ]
        if not actual_cols:
            _fail("No declared feature columns, model does not expose feature_names, "
                  "and the dataset has no numeric columns.")

    X = df[actual_cols].to_numpy(dtype=float)

    if file_format == "onnx":
        import onnxruntime as rt
        sess = rt.InferenceSession(artifact_path, providers=["CPUExecutionProvider"])
        # ONNX expects a dict {input_name: ndarray}; we send the first input.
        input_name = sess.get_inputs()[0].name
        out = sess.run(None, {input_name: X.astype(np.float32)})[0]
        with open(OUT_PATH, "w") as fh:
            json.dump({
                "ok": True,
                "predictions": out.tolist(),
                "feature_columns_used": actual_cols,
                "input_rows": int(X.shape[0]),
            }, fh)
        sys.exit(0)

    # ── Predict per output_kind (pkl / joblib path).
    # The artifact may be a sklearn-style class instance (.predict /
    # .predict_proba) OR a generic callable: a top-level function, a
    # bound method, or any object that's directly callable. The install-
    # from-Artifactory flow may pickle whichever shape the source library
    # exposes, so try `.predict[_proba]` first and fall back to invoking
    # the artifact itself.
    if output_kind == "probability_vector" and hasattr(model, "predict_proba"):
        out = model.predict_proba(X)
    elif hasattr(model, "predict") and callable(model.predict):
        out = model.predict(X)
    elif callable(model):
        out = model(X)
    else:
        _fail(
            f"Loaded artifact is not callable and has no `.predict` / "
            f"`.predict_proba` method. Got type: {type(model).__name__}"
        )
        out = None  # unreachable

    # Normalize ndarray → nested lists (json-safe).
    out = np.asarray(out).tolist()

    with open(OUT_PATH, "w") as fh:
        json.dump({
            "ok": True,
            "predictions": out,
            "feature_columns_used": actual_cols,
            "input_rows": int(X.shape[0]),
        }, fh)

except Exception as e:
    _fail(e, traceback.format_exc()[-1500:])
'''


def predict(
    *,
    artifact_path: str,
    file_format: str,
    df_records: list[dict[str, Any]],
    feature_columns: list[str],
    feature_mapping: dict[str, str] | None = None,
    pre_transform: str | None,
    output_kind: str,
    timeout_sec: int = 30,
) -> dict[str, Any]:
    """Run the artifact's `predict` (or `predict_proba`) on `df_records`.

    Returns a dict with either:
      - `ok: True, predictions: <list>, feature_columns_used: [...], input_rows: N`
      - `ok: False, error: str, traceback: str`

    Never raises; the caller decides how to surface failure (the orchestrator
    turns a failure into a failed `AnalyticsRun` so the workflow result still
    renders an error in the canvas)."""
    with tempfile.TemporaryDirectory(prefix="cma-modelrun-") as tmp:
        tmp_dir = Path(tmp)
        in_path = tmp_dir / "input.json"
        out_path = tmp_dir / "output.json"
        script_path = tmp_dir / "runner.py"

        in_path.write_text(json.dumps({
            "artifact_path": str(artifact_path),
            "file_format": file_format,
            "df": df_records,
            "feature_columns": feature_columns,
            "feature_mapping": feature_mapping or {},
            "pre_transform": pre_transform or "",
            "output_kind": output_kind,
        }), encoding="utf-8")
        script_path.write_text(_RUNNER_SCRIPT, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), str(in_path), str(out_path)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Model prediction timed out after {timeout_sec}s."}

        if not out_path.exists():
            # Subprocess died before writing output (segfault, OOM, syntax error).
            return {
                "ok": False,
                "error": "Model subprocess exited without producing output.",
                "stderr": (proc.stderr or "")[-1000:],
                "returncode": proc.returncode,
            }

        try:
            return json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Could not parse model output: {e}"}
