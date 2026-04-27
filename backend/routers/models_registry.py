"""Models router - function-scoped model registry.

Three creation paths:
1. Upload: bytes from disk (.pkl / .joblib / .onnx). We store the artifact and
   record metadata; we do NOT load arbitrary pickles for safety.
2. Build regression: train an OLS or logistic model in-app via scikit-learn on
   a bound dataset. Coefficients, intercept, and standard train metrics are
   captured and stored alongside the model.
3. From URI: register a pointer to an artifact in the company's model
   artifactory. We only persist the URI and metadata; we don't fetch.

Monitoring metrics are seeded with synthetic-but-plausible time series so the
UI looks alive. In production these would be appended each time a run scores
fresh data against the model.
"""
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from models.schemas import (
    FromUriRequest,
    ModelMetric,
    RegressionRequest,
    TrainedModel,
)
from packs import is_pack_visible
from routers.auth import get_current_user, get_current_user_groups
from routers.datasets import _DATASETS, _read_dataframe, _resolve_path

router = APIRouter()

ARTIFACT_ROOT = Path(__file__).resolve().parent.parent / "data" / "models"
ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_MODEL_FORMATS = {"pkl", "pickle", "joblib", "onnx", "json"}

_MODELS: dict[str, TrainedModel] = {}


# ── pack-registered seed ingest ────────────────────────────────────────────
def _ingest_pack_models() -> None:
    """Pull model attachments registered by domain packs into `_MODELS`.

    Called once at startup after `packs.discover_and_register()`. Idempotent."""
    from packs import model_attachments

    try:
        from agent.model_introspect import introspect_artifact
    except Exception:
        introspect_artifact = None  # type: ignore[assignment]

    now = datetime.utcnow().isoformat() + "Z"
    for s in model_attachments():
        if s["model_id"] in _MODELS:
            continue
        try:
            src: Path = s["source_path"]
            if not src.exists():
                continue
            ext = src.suffix.lstrip(".")
            func_dir = ARTIFACT_ROOT / s["function_id"]
            func_dir.mkdir(parents=True, exist_ok=True)
            rel = f"{s['function_id']}/{s['model_id']}.{ext}"
            dest = ARTIFACT_ROOT / rel
            if not dest.exists():
                dest.write_bytes(src.read_bytes())
            introspection = None
            if introspect_artifact is not None:
                try:
                    introspection = introspect_artifact(dest, ext)
                except Exception:
                    introspection = None
            m = TrainedModel(
                id=s["model_id"],
                function_id=s["function_id"],
                name=s["name"],
                description=s["description"],
                source_kind="upload",
                model_type="uploaded",
                artifact_path=rel,
                file_format=ext,
                size_bytes=dest.stat().st_size,
                introspection=introspection,
                train_metrics=s.get("train_metrics", {}) or {},
                monitoring_metrics=_seed_monitoring("uploaded", 0.92),
                created_at=now,
                pack_id=s.get("pack_id"),
            )
            _MODELS[m.id] = m
        except Exception:
            continue


# ── helpers ─────────────────────────────────────────────────────────────────
def _seed_monitoring(model_type: str, train_value: float) -> list[ModelMetric]:
    """Generate a 12-week monitoring trace decaying around the train metric."""
    rng = random.Random(hash(model_type) & 0xFFFFFFFF)
    metrics: list[ModelMetric] = []
    base_metric = "auc" if model_type == "logistic" else "r2"
    for i in range(12):
        d = (datetime.utcnow() - timedelta(weeks=11 - i)).strftime("%Y-%m-%d")
        # Slight degradation + noise
        drift = 0.01 * (i / 11)
        val = max(0.0, train_value - drift + rng.uniform(-0.02, 0.02))
        metrics.append(ModelMetric(name=base_metric, value=round(val, 4), asof=d))
        psi = 0.02 + (i / 11) * 0.08 + rng.uniform(-0.015, 0.015)
        metrics.append(ModelMetric(name="psi", value=round(max(0.0, psi), 4), asof=d))
    return metrics


def _frame_for_dataset(dataset_id: str) -> pd.DataFrame:
    d = _DATASETS.get(dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    if d.source_kind == "upload" and d.file_path and d.file_format:
        try:
            return _read_dataframe(_resolve_path(d), d.file_format)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed reading dataset: {e}")
    # sql_table — synthesize a small training frame from the column dtypes
    n = 250
    rng = np.random.default_rng(42)
    cols: dict[str, np.ndarray] = {}
    for c in d.columns:
        if c.dtype.startswith("float"):
            cols[c.name] = rng.normal(0, 1, n)
        elif c.dtype.startswith("int"):
            cols[c.name] = rng.integers(0, 100, n).astype(float)
        elif c.dtype == "bool":
            cols[c.name] = rng.integers(0, 2, n).astype(int)
        elif c.dtype.startswith("datetime"):
            cols[c.name] = pd.date_range("2024-01-01", periods=n, freq="D")
        else:
            cols[c.name] = rng.choice(["A", "B", "C", "D"], size=n)
    df = pd.DataFrame(cols)
    # If we generated nothing numeric, still need numeric for regression demo
    return df


def _train_regression(
    df: pd.DataFrame,
    target: str,
    features: list[str],
    model_type: str,
) -> dict[str, Any]:
    if target not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target}' not in dataset")
    missing = [f for f in features if f not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Feature columns not in dataset: {missing}")
    if not features:
        raise HTTPException(status_code=400, detail="At least one feature column is required")

    work = df[[target] + features].dropna()
    if len(work) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 rows after dropping NaNs")

    # Coerce features to numeric (one-hot for object cols)
    feat_df = pd.get_dummies(work[features], drop_first=True)
    feat_df = feat_df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").fillna(0)
    expanded_features = list(feat_df.columns)
    X = feat_df.to_numpy(dtype=float)
    y_raw = work[target]

    if model_type == "logistic":
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, roc_auc_score

        # Coerce target to binary
        y_num = pd.to_numeric(y_raw, errors="coerce")
        if y_num.notna().sum() == len(y_raw):
            y_arr = (y_num > y_num.median()).astype(int).to_numpy()
        else:
            uniq = list(pd.Series(y_raw).astype(str).unique())[:2]
            y_arr = pd.Series(y_raw).astype(str).map(lambda v: 1 if v == uniq[0] else 0).to_numpy()
        if len(set(y_arr)) < 2:
            raise HTTPException(status_code=400, detail="Target must have at least 2 classes for logistic regression")

        model = LogisticRegression(max_iter=200, solver="lbfgs")
        model.fit(X, y_arr)
        pred = model.predict(X)
        proba = model.predict_proba(X)[:, 1]
        train_metrics = {
            "accuracy": round(float(accuracy_score(y_arr, pred)), 4),
            "auc": round(float(roc_auc_score(y_arr, proba)), 4),
            "n_train": int(len(work)),
        }
        coefs = {f: round(float(c), 6) for f, c in zip(expanded_features, model.coef_[0].tolist())}
        intercept = float(model.intercept_[0])
        seed_metric = train_metrics["auc"]
    else:  # ols
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import mean_absolute_error, r2_score

        y_num = pd.to_numeric(y_raw, errors="coerce")
        if y_num.isna().any():
            raise HTTPException(status_code=400, detail="OLS target must be numeric")
        y_arr = y_num.to_numpy()
        model = LinearRegression()
        model.fit(X, y_arr)
        pred = model.predict(X)
        train_metrics = {
            "r2": round(float(r2_score(y_arr, pred)), 4),
            "mae": round(float(mean_absolute_error(y_arr, pred)), 4),
            "n_train": int(len(work)),
        }
        coefs = {f: round(float(c), 6) for f, c in zip(expanded_features, model.coef_.tolist())}
        intercept = float(model.intercept_)
        seed_metric = max(0.0, train_metrics["r2"])

    return {
        "coefficients": coefs,
        "intercept": round(intercept, 6),
        "feature_columns": expanded_features,
        "train_metrics": train_metrics,
        "seed_metric": seed_metric,
    }


# Seed bundled sample models (no-op if registry already has entries).
# Pack-registered models are ingested by the startup hook in main.py.


# ── routes ─────────────────────────────────────────────────────────────────
@router.get("", response_model=list[TrainedModel])
async def list_models(
    function_id: str | None = Query(default=None),
    groups: list[str] = Depends(get_current_user_groups),
):
    items = [m for m in _MODELS.values() if is_pack_visible(m.pack_id, groups)]
    if function_id:
        items = [m for m in items if m.function_id == function_id]
    items.sort(key=lambda m: m.created_at, reverse=True)
    return items


@router.get("/{model_id}", response_model=TrainedModel)
async def get_model(model_id: str, _: str = Depends(get_current_user)):
    m = _MODELS.get(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    return m


@router.delete("/{model_id}", status_code=204)
async def delete_model(model_id: str, _: str = Depends(get_current_user)):
    m = _MODELS.pop(model_id, None)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    if m.artifact_path:
        try:
            (ARTIFACT_ROOT / m.artifact_path).unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/build-regression", response_model=TrainedModel, status_code=201)
async def build_regression(req: RegressionRequest, _: str = Depends(get_current_user)):
    df = _frame_for_dataset(req.dataset_id)
    fit = _train_regression(df, req.target_column, req.feature_columns, req.model_type)

    mid = f"mdl-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat() + "Z"
    m = TrainedModel(
        id=mid,
        function_id=req.function_id,
        name=req.name,
        description=req.description,
        source_kind="regression",
        model_type=req.model_type,
        target_column=req.target_column,
        feature_columns=fit["feature_columns"],
        coefficients=fit["coefficients"],
        intercept=fit["intercept"],
        train_metrics=fit["train_metrics"],
        monitoring_metrics=_seed_monitoring(req.model_type, fit["seed_metric"]),
        dataset_id=req.dataset_id,
        created_at=now,
        last_run=now,
    )
    _MODELS[mid] = m
    return m


@router.post("/upload", response_model=TrainedModel, status_code=201)
async def upload_model(
    function_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    _: str = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_MODEL_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model format '.{ext}'. Supported: {sorted(SUPPORTED_MODEL_FORMATS)}",
        )
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Model too large ({len(contents):,} bytes)")

    mid = f"mdl-{uuid.uuid4().hex[:10]}"
    func_dir = ARTIFACT_ROOT / function_id
    func_dir.mkdir(parents=True, exist_ok=True)
    rel = f"{function_id}/{mid}.{ext}"
    abs_path = ARTIFACT_ROOT / rel
    abs_path.write_bytes(contents)

    # Best-effort introspection of the uploaded artifact
    from agent.model_introspect import introspect_artifact
    introspection = introspect_artifact(abs_path, ext)

    now = datetime.utcnow().isoformat() + "Z"
    m = TrainedModel(
        id=mid,
        function_id=function_id,
        name=name or file.filename.rsplit(".", 1)[0],
        description=description,
        source_kind="upload",
        model_type="uploaded",
        artifact_path=rel,
        file_format=ext,
        size_bytes=len(contents),
        introspection=introspection,
        train_metrics={"uploaded": 1.0, "size_bytes": float(len(contents))},
        monitoring_metrics=_seed_monitoring("uploaded", 0.85),
        created_at=now,
    )
    _MODELS[mid] = m
    return m


@router.post("/{model_id}/reintrospect", response_model=TrainedModel)
async def reintrospect_model(model_id: str, _: str = Depends(get_current_user)):
    """Re-run introspection on a previously uploaded artifact.

    Useful if you've added the model's class definitions to the Python path
    after upload, or if you've re-uploaded the file to disk manually.
    """
    m = _MODELS.get(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    if m.source_kind != "upload" or not m.artifact_path or not m.file_format:
        raise HTTPException(status_code=400, detail="Only uploaded artifacts can be re-introspected")
    abs_path = ARTIFACT_ROOT / m.artifact_path
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file is missing on disk")
    from agent.model_introspect import introspect_artifact
    m.introspection = introspect_artifact(abs_path, m.file_format)
    return m


@router.post("/from-uri", response_model=TrainedModel, status_code=201)
async def register_from_uri(req: FromUriRequest, _: str = Depends(get_current_user)):
    mid = f"mdl-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat() + "Z"
    m = TrainedModel(
        id=mid,
        function_id=req.function_id,
        name=req.name,
        description=req.description,
        source_kind="uri",
        model_type=req.model_type,
        artifactory_uri=req.artifactory_uri,
        train_metrics={"reference": 1.0},
        monitoring_metrics=_seed_monitoring("external", 0.78),
        created_at=now,
    )
    _MODELS[mid] = m
    return m


@router.get("/{model_id}/metrics")
async def get_metrics(model_id: str, _: str = Depends(get_current_user)):
    m = _MODELS.get(model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Model not found")
    # Group by metric name into series
    series: dict[str, list[dict[str, Any]]] = {}
    for entry in m.monitoring_metrics:
        series.setdefault(entry.name, []).append({"asof": entry.asof, "value": entry.value})
    return {"model_id": model_id, "series": series, "train_metrics": m.train_metrics}
