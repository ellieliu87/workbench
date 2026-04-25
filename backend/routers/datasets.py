"""Datasets router - function-scoped datasets bound from data sources or uploads.

A Dataset is the unit each function's Models / Analytics / Reports tabs operate
on. It points either to a table inside a registered Data Source ("sql_table"),
or to a file the analyst uploaded ("upload"). For uploads we read the file with
pandas to infer schema and offer sample-row previews.

In a real deployment, sql_table previews would issue a `SELECT … LIMIT n` against
the underlying source. Here we synthesize sample rows from the declared column
types so the UI looks alive without requiring a real warehouse connection.
"""
import json
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from models.schemas import (
    Dataset,
    DatasetColumn,
    DatasetCreateFromTable,
    DatasetPreview,
)
from routers.auth import get_current_user
from routers.datasources import SAMPLE_TABLES, _DATA_SOURCES

router = APIRouter()

# Files land in backend/data/datasets/{function_id}/{dataset_id}.{ext}
DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "datasets"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
SUPPORTED_FORMATS = {"csv", "parquet", "xlsx", "xls", "json"}

_DATASETS: dict[str, Dataset] = {}


# ── helpers ─────────────────────────────────────────────────────────────────
def _infer_format(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Supported: {sorted(SUPPORTED_FORMATS)}",
        )
    return ext


def _read_dataframe(path: Path, fmt: str) -> pd.DataFrame:
    if fmt == "csv":
        return pd.read_csv(path)
    if fmt in ("xlsx", "xls"):
        return pd.read_excel(path)
    if fmt == "parquet":
        return pd.read_parquet(path)
    if fmt == "json":
        return pd.read_json(path)
    raise HTTPException(status_code=400, detail=f"Unsupported format {fmt}")


def _columns_from_df(df: pd.DataFrame) -> list[DatasetColumn]:
    return [
        DatasetColumn(
            name=str(col),
            dtype=str(df[col].dtype),
            nullable=bool(df[col].isnull().any()),
        )
        for col in df.columns
    ]


def _df_to_records(df: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    """Convert a DataFrame slice to JSON-safe records (ISO dates, NaN→None)."""
    sample = df.head(n).copy()
    for col in sample.columns:
        if pd.api.types.is_datetime64_any_dtype(sample[col]):
            sample[col] = sample[col].astype(str)
    # Replace NaN with None so json serializes correctly
    return json.loads(sample.to_json(orient="records", date_format="iso"))


def _seed_sample_row(col_name: str, dtype: str, i: int) -> Any:
    """Build a fake value for a sql_table preview based on column dtype + name."""
    name = col_name.lower()
    if "date" in name or dtype.startswith("datetime"):
        return (datetime(2026, 1, 1) + timedelta(days=i * 7)).strftime("%Y-%m-%d")
    if dtype.startswith("int"):
        if "month" in name or "horizon" in name:
            return i + 1
        return random.randint(100, 999)
    if dtype.startswith("float"):
        if "rate" in name or "yield" in name or "beta" in name:
            return round(random.uniform(0.5, 6.5), 2)
        if "bps" in name:
            return round(random.uniform(20, 80), 1)
        if "value" in name or "balance" in name or "market" in name:
            return round(random.uniform(50000, 5_000_000), 2)
        if "year" in name:
            return round(random.uniform(2.0, 7.5), 2)
        return round(random.uniform(1, 100), 2)
    if dtype == "bool":
        return random.choice([True, False])
    # string / object
    if "id" in name:
        return f"ID-{1000 + i}"
    if "scenario" in name:
        return random.choice(["Base", "Adverse", "Severely Adverse", "Outlook"])
    if "variable" in name:
        return random.choice(["10Y_UST", "2Y_UST", "Unemployment", "GDP", "CPI"])
    if "product" in name or "type" in name:
        return random.choice(["CC30", "CC15", "GN30", "Treasury"])
    if "category" in name:
        return random.choice(["Compensation", "Technology", "Marketing", "Other"])
    return f"sample_{i}"


def _synthesize_sample(columns: list[DatasetColumn], n: int = 10) -> list[dict[str, Any]]:
    rng = random.Random(42)  # deterministic per request
    random.seed(42)
    rows = []
    for i in range(n):
        rows.append({c.name: _seed_sample_row(c.name, c.dtype, i) for c in columns})
    return rows


def _resolve_path(d: Dataset) -> Path:
    if not d.file_path:
        raise HTTPException(status_code=400, detail="Dataset has no underlying file")
    return DATA_ROOT / d.file_path


# ── routes ──────────────────────────────────────────────────────────────────
@router.get("", response_model=list[Dataset])
async def list_datasets(
    function_id: str | None = Query(default=None),
    _: str = Depends(get_current_user),
):
    items = list(_DATASETS.values())
    if function_id:
        items = [d for d in items if d.function_id == function_id]
    items.sort(key=lambda d: d.created_at, reverse=True)
    return items


@router.get("/{dataset_id}", response_model=Dataset)
async def get_dataset(dataset_id: str, _: str = Depends(get_current_user)):
    d = _DATASETS.get(dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return d


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(dataset_id: str, _: str = Depends(get_current_user)):
    d = _DATASETS.pop(dataset_id, None)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if d.file_path:
        p = DATA_ROOT / d.file_path
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/upload", response_model=Dataset, status_code=201)
async def upload_dataset(
    function_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    _: str = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")
    fmt = _infer_format(file.filename)
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents):,} bytes). Cap is {MAX_UPLOAD_BYTES:,}.",
        )

    dataset_id = f"ds-{uuid.uuid4().hex[:10]}"
    func_dir = DATA_ROOT / function_id
    func_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"{function_id}/{dataset_id}.{fmt}"
    abs_path = DATA_ROOT / rel_path
    abs_path.write_bytes(contents)

    try:
        df = _read_dataframe(abs_path, fmt)
    except Exception as e:
        abs_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")

    columns = _columns_from_df(df)
    final_name = name or file.filename.rsplit(".", 1)[0]
    now = datetime.utcnow().isoformat() + "Z"
    ds = Dataset(
        id=dataset_id,
        function_id=function_id,
        name=final_name,
        description=description,
        source_kind="upload",
        file_path=rel_path,
        file_format=fmt,  # type: ignore[arg-type]
        columns=columns,
        row_count=int(len(df)),
        size_bytes=len(contents),
        created_at=now,
        last_synced=now,
    )
    _DATASETS[dataset_id] = ds
    return ds


@router.post("/from-table", response_model=Dataset, status_code=201)
async def bind_from_table(req: DatasetCreateFromTable, _: str = Depends(get_current_user)):
    if req.data_source_id not in _DATA_SOURCES:
        raise HTTPException(status_code=404, detail="Data source not found")
    src_tables = SAMPLE_TABLES.get(req.data_source_id, {})
    if req.table_ref not in src_tables:
        raise HTTPException(status_code=404, detail=f"Table '{req.table_ref}' not in source")

    columns = [DatasetColumn(name=n, dtype=d) for n, d in src_tables[req.table_ref]]
    dataset_id = f"ds-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat() + "Z"
    ds = Dataset(
        id=dataset_id,
        function_id=req.function_id,
        name=req.name,
        description=req.description,
        source_kind="sql_table",
        data_source_id=req.data_source_id,
        table_ref=req.table_ref,
        columns=columns,
        row_count=None,  # unknown until queried
        created_at=now,
        last_synced=now,
    )
    _DATASETS[dataset_id] = ds
    return ds


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(
    dataset_id: str,
    n: int = 10,
    _: str = Depends(get_current_user),
):
    d = _DATASETS.get(dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    n = max(1, min(n, 200))

    if d.source_kind == "upload" and d.file_path and d.file_format:
        try:
            df = _read_dataframe(_resolve_path(d), d.file_format)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not read file: {e}")
        return DatasetPreview(
            dataset_id=d.id,
            columns=_columns_from_df(df),
            sample_rows=_df_to_records(df, n),
            total_rows=int(len(df)),
            truncated=len(df) > n,
        )

    # sql_table — synthesize a sample
    return DatasetPreview(
        dataset_id=d.id,
        columns=d.columns,
        sample_rows=_synthesize_sample(d.columns, n),
        total_rows=None,
        truncated=False,
    )
