"""CMA Workbench - Capital Markets & Analytics self-service platform - FastAPI backend."""
# Load backend/.env into the process environment BEFORE any other imports so
# that downstream modules (cof.orchestrator, etc.) see OPENAI_API_KEY at import time.
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Domain-pack discovery ──────────────────────────────────────────────────
# Each `packs/<id>/pack.py` registers its skills, tools, datasets, and model
# attachments via the PackContext API. Run discovery BEFORE importing any
# router so the routers' module-level seeds can pull pack-registered tools
# from the registry.
import packs as _packs
_packs.discover_and_register()

from routers import (
    auth,
    functions,
    workspace,
    chat,
    datasources,
    datasets,
    skills,
    plots,
    tools,
    models_registry,
    scenarios,
    playbooks,
    analytics_defs,
    overview_layouts,
)

app = FastAPI(
    title="CMA Workbench API",
    description="Self-service analytics platform for Capital Markets & Finance analysts",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(functions.router, prefix="/api/functions", tags=["Business Functions"])
app.include_router(workspace.router, prefix="/api/workspace", tags=["Workspace"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(datasources.router, prefix="/api/datasources", tags=["Data Sources"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["Datasets"])
app.include_router(models_registry.router, prefix="/api/models", tags=["Models"])
app.include_router(scenarios.router, prefix="/api/analytics", tags=["Scenarios & Runs"])
app.include_router(playbooks.router, prefix="/api/playbooks", tags=["Playbooks"])
app.include_router(skills.router, prefix="/api/skills", tags=["Agent Skills"])
app.include_router(plots.router, prefix="/api/plots", tags=["Plot Builder"])
app.include_router(tools.router, prefix="/api/tools", tags=["Python Tools"])
app.include_router(analytics_defs.router, prefix="/api/analytics_defs", tags=["Analytics Definitions"])
app.include_router(overview_layouts.router, prefix="/api/overview_layouts", tags=["Overview Layouts"])


@app.on_event("startup")
async def _ingest_pack_assets():
    """After all routers and registries are wired, pull dataset, model,
    and plot attachments from each registered pack into the in-memory
    stores. Tools are ingested lazily inside `routers/tools.py:_seed()`."""
    try:
        datasets._ingest_pack_datasets()
    except Exception as e:
        print(f"[startup] dataset pack ingest failed: {e}")
    try:
        models_registry._ingest_pack_models()
    except Exception as e:
        print(f"[startup] model pack ingest failed: {e}")
    # Plots depend on dataset ingest — they reference dataset_ids by name.
    try:
        plots._ingest_pack_plots()
    except Exception as e:
        print(f"[startup] plot pack ingest failed: {e}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CMA Workbench API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
