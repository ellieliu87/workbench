"""Knowledge Base router — uploaded documents the `rag_search` tool queries.

Files land under `CMA_DOCS_ROOT/uploads/` (default
`<repo>/sample_docs/uploads/`) and become searchable by the universal
`rag_search` built-in. Supported formats: `.md .txt .pdf .docx .pptx
.py .csv .xlsx .xls .json`. Optional `scope` puts the file in a
sub-folder so analysts can group whitepapers by domain
(`retail_deposit`, `portfolio`, etc.).

Storage is on the local filesystem and **non-versioned** — production
deployments should swap this for an S3 / OneLake-backed store.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from routers.auth import get_current_user

router = APIRouter()


ALLOWED_EXTENSIONS = {
    ".md", ".txt", ".pdf", ".docx", ".pptx",
    ".py", ".csv", ".xlsx", ".xls", ".json",
}


def _docs_root() -> Path:
    """Resolve the on-disk root for uploaded knowledge-base documents.

    Honors `CMA_DOCS_ROOT` if set; otherwise defaults to
    `<repo>/sample_docs/uploads/`. The same `sample_docs/` parent
    contains the bundled retail-deposit / portfolio whitepapers, so
    `rag_search` (which walks recursively from `sample_docs/`)
    automatically picks up uploads alongside the curated corpus.
    """
    env = os.environ.get("CMA_DOCS_ROOT", "").strip()
    base = Path(env) if env else Path(__file__).resolve().parent.parent.parent / "sample_docs"
    return base / "uploads"


class DocumentInfo(BaseModel):
    id: str             # path relative to docs root, forward-slash separated
    name: str           # base filename
    size_bytes: int
    extension: str      # lowercase, includes leading dot
    scope: str | None = None  # subfolder path, or None for root
    uploaded_at: str    # ISO-8601 UTC


def _scan_docs() -> list[DocumentInfo]:
    root = _docs_root()
    if not root.exists():
        return []
    out: list[DocumentInfo] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        try:
            stat = p.stat()
        except OSError:
            continue
        rel = p.relative_to(root)
        scope_parts = rel.parts[:-1]
        scope = "/".join(scope_parts) if scope_parts else None
        out.append(DocumentInfo(
            id=str(rel).replace("\\", "/"),
            name=p.name,
            size_bytes=stat.st_size,
            extension=ext,
            scope=scope,
            uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        ))
    return out


def _resolve_within_root(rel_id: str) -> Path:
    """Resolve `rel_id` relative to docs root and reject traversal attempts."""
    root = _docs_root().resolve()
    target = (root / rel_id).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="path escapes docs root")
    return target


@router.get("", response_model=list[DocumentInfo])
async def list_documents(_: str = Depends(get_current_user)):
    """List all uploaded documents under the knowledge-base root."""
    return _scan_docs()


@router.get("/root")
async def get_docs_root(_: str = Depends(get_current_user)):
    """Return the configured on-disk root + supported extensions.

    Surfacing this lets the frontend show analysts where uploads land
    so they can drop additional files via the host filesystem if they
    prefer (useful for batch transfers and corporate scan tools)."""
    root = _docs_root()
    return {
        "root":        str(root),
        "exists":      root.exists(),
        "extensions":  sorted(ALLOWED_EXTENSIONS),
        "env_var":     "CMA_DOCS_ROOT",
        "env_value":   os.environ.get("CMA_DOCS_ROOT", "") or None,
    }


@router.post("/upload", response_model=DocumentInfo)
async def upload_document(
    file: UploadFile = File(...),
    scope: str | None = Form(None),
    _: str = Depends(get_current_user),
):
    """Upload a single document.

    `scope` is an optional sub-folder name (e.g. `retail_deposit`) so
    analysts can keep related whitepapers together. The agent reads the
    same physical folder via `rag_search`, so the scope is also a
    natural pre-filter the analyst can pass to the tool.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="file has no filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {ext!r}. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    root = _docs_root()
    # Sanitize the scope to a single-level safe folder name.
    safe_scope = None
    if scope:
        safe_scope = scope.strip().strip("/").replace("\\", "/")
        # Drop any traversal attempts; keep only [a-zA-Z0-9_-/]+.
        if any(seg in {"", ".", ".."} for seg in safe_scope.split("/")):
            raise HTTPException(status_code=400, detail="invalid scope")
    target_dir = (root / safe_scope) if safe_scope else root
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name  # strip any path components from upload
    target_path = target_dir / safe_name
    if target_path.exists():
        # Avoid overwrite — append a short uuid suffix.
        target_path = target_dir / f"{target_path.stem}-{uuid.uuid4().hex[:8]}{ext}"

    contents = await file.read()
    target_path.write_bytes(contents)

    rel = target_path.relative_to(root)
    return DocumentInfo(
        id=str(rel).replace("\\", "/"),
        name=target_path.name,
        size_bytes=len(contents),
        extension=ext,
        scope=safe_scope,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )


@router.delete("/{doc_id:path}")
async def delete_document(doc_id: str, _: str = Depends(get_current_user)):
    """Delete an uploaded document by its id (= relative path)."""
    target = _resolve_within_root(doc_id)
    if not target.exists():
        raise HTTPException(status_code=404, detail="document not found")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="not a file")
    target.unlink()
    return {"ok": True, "id": doc_id}
