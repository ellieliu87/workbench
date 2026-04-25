"""CMA Workbench - Capital Markets & Analytics self-service platform - FastAPI backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
app.include_router(skills.router, prefix="/api/skills", tags=["Agent Skills"])
app.include_router(plots.router, prefix="/api/plots", tags=["Plot Builder"])
app.include_router(tools.router, prefix="/api/tools", tags=["Python Tools"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CMA Workbench API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
