# CMA Workbench

Self-serve analytics workbench for the **Capital Markets & Analytics**
department. The shape: an analyst lands on a function-selection home page,
opens a workspace for one of 8 business functions, and gets a 7-tab work
surface backed by a multi-agent system. Domain-specific data, models,
agents, and tools ship as **domain packs** so adding a new business area is
a directory drop, not a code-base rewrite.

## Tech stack

- **Frontend** — React 18 · Vite · TypeScript · Tailwind · Radix/shadcn ·
  Recharts · ReactFlow (xyflow) · Zustand · ReactMarkdown
- **Backend** — FastAPI · Uvicorn · Pydantic v2 · pandas · scikit-learn ·
  [openai-agents](https://github.com/openai/openai-agents-python) (the real
  orchestrator — there is no mock fallback)
- **LLM connection** — OpenAI direct (`OPENAI_API_KEY`) or Capital One COF
  endpoint (`COF_BASE_URL`). Chosen at startup; `chat_specialist` raises
  with a clear setup-required message if neither is configured.

## Architecture at a glance

```
cma/
├── backend/
│   ├── main.py                    ← .env → discover packs → mount routers
│   ├── agent/
│   │   ├── tools.py               ← 11 universal "introspection" tools
│   │   │                            (get_workspace, get_dataset_preview,
│   │   │                             validate_workflow, get_tile, …)
│   │   ├── skills/                ← 10 universal built-in skills (.md)
│   │   ├── skills_user/           ← analyst-uploaded skills
│   │   └── skill_loader.py        ← multi-source loader (builtin/user/pack)
│   │
│   ├── packs/                     ← DOMAIN PACKS — opt-in bundles
│   │   ├── __init__.py            ← Pack, PackContext, registry, group filter
│   │   └── portfolio/             ← first domain pack
│   │       ├── pack.py            ← register(ctx) — entry point
│   │       ├── skills/            ← 8 portfolio-planning agents (.md)
│   │       └── tools.py           ← 20 register_python_tool(...) calls
│   │
│   ├── cof/
│   │   ├── orchestrator.py        ← AsyncOrchestrator (streaming + traces)
│   │   └── base_agent.py          ← CofBaseAgent — wraps one skill via
│   │                                openai-agents SDK; emits per-step trace
│   │
│   ├── models/schemas.py          ← Pydantic v2 wire schemas
│   │
│   └── routers/
│       ├── auth.py                ← pqr557 / capital1, group-based access
│       ├── functions.py           ← 8 business functions catalog
│       ├── workspace.py           ← Overview tab default views
│       ├── chat.py                ← /api/chat/message (entity-aware routing)
│       ├── datasources.py         ← Snowflake / OneLake / S3 / file uploads
│       ├── datasets.py            ← per-function dataset registry
│       ├── models_registry.py     ← per-function model registry
│       ├── scenarios.py           ← scenarios + analytics runs
│       ├── playbooks.py           ← phased agent playbooks (gated runs)
│       ├── analytics_defs.py      ← self-serve analytic definitions
│       ├── plots.py               ← tile / chart builder
│       ├── tools.py               ← Python-tool registry (with /draft endpoint)
│       └── skills.py              ← agent-skill CRUD + tool catalog
│
├── frontend/src/
│   ├── pages/
│   │   ├── Login/                 ← single-account form
│   │   ├── Home/                  ← function picker
│   │   ├── Workspace/             ← 7-tab work surface (see below)
│   │   └── Settings/              ← Data Sources · Agent Skills · Python
│   │                                Tools · Plot Builder
│   ├── components/chat/           ← right-side chat panel
│   ├── store/                     ← Zustand: auth, chat
│   └── types/index.ts             ← API wire types
│
├── sample_data/portfolio/         ← bundled CSVs the portfolio pack stages
└── sample_models/portfolio/       ← bundled model .pkls the pack stages
```

### Workspace tabs (per function)

| Tab            | What it does                                                   |
|----------------|----------------------------------------------------------------|
| **Overview**   | KPI strip + default charts/tables/insights for the function    |
| **Data**       | Datasets, scenarios, source bindings; per-card explain agent   |
| **Models**     | Build OLS / logistic in-app, or upload `.pkl`/`.joblib`/`.onnx`/`.json` |
| **Workflow**   | Three views over the same graph — *Steps*, *Canvas* (ReactFlow), *Spec* (YAML). Run end-to-end with destinations |
| **Playbooks**  | Author phased agent workflows with gate-by-gate analyst review; trace streams live as the agent calls tools |
| **Analytics**  | Self-serve analytic definitions — *Aggregate*, *Compare*, *Custom Python* primitives + an agent that drafts specs from prose |
| **Reporting**  | Tile/chart catalog over your function's data; click a tile to have the tile-explainer agent narrate it |

### Agent system

Two layers, both real (no mock fallback):

- **Introspection tools** (`agent/tools.py`) — 11 functions the agent calls
  to read live workbench state: `get_workspace`, `get_dataset_preview`,
  `profile_dataset`, `get_model`, `get_model_metrics`, `validate_workflow`,
  `get_run`, `get_tile`, `get_tile_preview`, `apply_tile_filter`,
  `get_function_meta`. Always available, never user-modifiable.

- **Skills** — markdown files with YAML frontmatter (`name`, `description`,
  `model`, `tools`, `color`, `icon`). Loaded from three sources, in this
  override order: built-in → pack → user upload.

  Universal built-ins shipped today: `orchestrator`, `kpi-explainer`,
  `data-quality`, `model-explainer`, `workflow-validator`, `run-troubleshooter`,
  `tile-tuner`, `tile-explainer`, `macro-economist`, `troubleshooter`.

  Portfolio pack skills: `portfolio-gap-analyst`, `portfolio-risk-officer`,
  `new-volume-analyst`, `allocation-strategist`, `mbs-decomposition-specialist`,
  `universe-screener`, `pool-analytics-specialist`, `trade-advisor`.

The router (`routers/chat.py:_route`) maps the chat context (tab +
`entity_kind` + message intent) to a specialist; e.g. clicking *Explain* on
a scenario card routes to `macro-economist`, on a chart tile to
`tile-explainer`, on a model card to `model-explainer`.

The orchestrator (`cof/orchestrator.py:AsyncOrchestrator`) uses
`Runner.run_streamed()` and emits a step-by-step trace
(tool call → tool output → reasoning → final message) that the playbook UI
renders live during a run.

### Domain packs

A pack is a self-contained directory under `backend/packs/<id>/` with one
entry point: `pack.py:register(ctx)`. The registration writes into four
shared registries that the routers consume:

| Registry             | Populated by                                  | Consumer                       |
|----------------------|-----------------------------------------------|--------------------------------|
| Skill source dirs    | `ctx.register_skill_dir(path)`                | `agent/skill_loader.py`        |
| Python tool seeds    | `ctx.register_python_tool(...)`               | `routers/tools.py`             |
| Dataset attachments  | `ctx.attach_dataset(function_id=..., ...)`    | `routers/datasets.py` (startup hook) |
| Model attachments    | `ctx.attach_model(function_id=..., ...)`      | `routers/models_registry.py` (startup hook) |

Each registered artifact is stamped with `source="pack"` and `pack_id=<id>`
on its wire schema, plus a colored `Pack: <id>` badge in the UI. Packs
declare a `user_groups: list[str]` — `is_pack_visible(pack_id, user_groups)`
filters every list endpoint, so a user in `["irr_team"]` won't see the
`portfolio` pack's artifacts unless its `user_groups` includes that string
(or `"*"`).

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# *nix:    source .venv/bin/activate
pip install -r requirements.txt

# Configure the LLM connection (one of these)
cat > .env <<'EOF'
OPENAI_API_KEY=sk-...
# or, inside the company network:
# COF_BASE_URL=https://...
# COF_API_KEY=...
EOF

python -m uvicorn main:app --port 8001 --host 127.0.0.1
```

Backend serves on **http://127.0.0.1:8001** ; OpenAPI docs at `/docs`.

> **Windows + OneDrive note:** `--reload` is unreliable when the backend
> directory lives inside OneDrive — file-watcher events get dropped and
> orphaned multiprocessing children can hold port 8001 after a parent
> kill. Run without `--reload` and restart manually after edits, or move
> the checkout outside OneDrive.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves on **http://localhost:5173** if free, otherwise auto-bumps to
**5174**. The dev server proxies `/api/*` to `http://localhost:8001` (set
in `vite.config.ts`).

## Sign-in

| Field    | Value      |
|----------|------------|
| Username | `pqr557`   |
| Password | `capital1` |

Profile: **Quantitative Analyst** in the **Capital Markets & Analytics**
department, with `groups: ["*"]` (sees every pack). This is the only
account `routers/auth.py` accepts; any other combination returns 401.

## Business functions shipped out of the box

Capital Markets:

1. Investment Portfolio Analytics
2. Interest Rate Risk Management
3. Liquidity & Funding
4. Market Risk & VaR

Finance:

5. Credit Risk Analytics
6. Treasury & Funds Transfer Pricing
7. Capital Planning & CCAR
8. Financial Planning & Reporting

The portfolio pack auto-attaches its 2 datasets (macro history + forecast)
and the BGM term-structure model to **Investment Portfolio**, and a copy
of the same BGM model to **Interest Rate Risk**. Other functions start
empty until you build models, upload datasets, or attach a pack.

## Adding a new domain pack

The whole delta for a new domain (e.g. `interest_rate_risk`) is a new
directory. Zero edits to any router, schema, or loader.

```
backend/packs/interest_rate_risk/
├── pack.py            ← register(ctx)
├── skills/            ← any *.md skill files
└── tools.py           ← register_python_tools(ctx)
```

**`pack.py`** — declare metadata, then call ctx methods:

```python
from packs import Pack, PackContext
from packs.interest_rate_risk.tools import register_python_tools

def register(ctx: PackContext) -> None:
    ctx.pack = Pack(
        id="interest_rate_risk",
        label="Interest Rate Risk",
        description="ALM, EVE shock, BGM scenario work.",
        attach_to_functions=["interest_rate_risk"],
        user_groups=["irr_team"],   # empty = visible to everyone
        color="#0F766E",
        icon="trending-up",
    )

    ctx.register_skill_dir()         # default: <pack_dir>/skills
    register_python_tools(ctx)       # the tools.py module's helper

    ctx.attach_dataset(
        function_id="interest_rate_risk",
        dataset_id="ds-rate-history",
        name="Rate History",
        description="...",
        source_path=Path(__file__).parent / "data" / "rate_history.csv",
    )
    ctx.attach_model(
        function_id="interest_rate_risk",
        model_id="mdl-bgm-irr",
        name="BGM Term-Structure",
        description="...",
        source_path=Path(__file__).parent / "models" / "bgm.pkl",
        train_metrics={"calibration_rmse_bps": 4.2},
    )
```

**`tools.py`** — one `ctx.register_python_tool(...)` per tool:

```python
from packs import PackContext

def register_python_tools(ctx: PackContext) -> None:
    ctx.register_python_tool(
        name="compute_eve_shock",
        description="Apply a parallel rate shock and return EVE % change.",
        parameters=[
            {"name": "shock_bps", "type": "integer",
             "description": "Parallel shock in bps.", "required": True},
        ],
        python_source=(
            "def compute_eve_shock(shock_bps: int):\n"
            "    return {'shock_bps': shock_bps,\n"
            "            'eve_pct': round(-0.01 * shock_bps, 2)}\n"
        ),
    )
```

**Skill files** — drop any number of markdown skills into `skills/`. Use
the same frontmatter the universal built-ins use (`name`, `description`,
`model`, `max_tokens`, `tools`, `color`, `icon`). Tool names referenced in
`tools:` can come from `agent/tools.py` (introspection), the registered
Python tools (universal or any pack's), or be added later — the editor
flags any unknown ones inline.

Restart the backend; `packs.discover_and_register()` runs at startup and
the pack's artifacts appear automatically with their `Pack: <id>` badge.

## Customization (Settings)

The Settings page (sidebar) has four tabs:

- **Data Sources** — Snowflake, OneLake, Postgres, REST, S3 connections
  plus direct file upload (CSV / Parquet / XLSX / JSON). Used by datasets
  bound on the workspace's Data tab.
- **Agent Skills** — three sections: *User-Customized* (uploads / your
  edits), one section per *Domain Pack* (read-only here), and *Built-in*.
  Edit a skill to fork or wire its tool list. The tool picker uses chips
  for what's selected and a search-to-add input for the rest, so it scales
  past 30+ tools without becoming a wall of checkboxes.
- **Python Tools** — same three-section layout. `+ New Tool` opens a
  drafter where you describe the tool in plain English, the agent fills
  in the source / parameters / description, and the test runner executes
  it in a subprocess sandbox (5-second wall clock) before save.
- **Plot Builder** — tile/chart designer. Pick source (dataset or run
  output), chart type, X axis, multiple Y series, aggregation. Live
  preview, then pin to Reporting or Overview.

## Notes & known limitations

- **In-process persistence.** Tokens, datasets uploaded at runtime,
  models, scenarios, plots, playbook runs, and analytics-definition runs
  all live in dicts. They reset on backend restart. The pack-bundled
  datasets and models re-stage on startup from `sample_data/` and
  `sample_models/`, so those reappear automatically.
- **Auth is mock** — single account, in-memory bearer-token store. The
  `groups` column is honored by `is_pack_visible(...)`, but there's no
  flow for adding a second user yet.
- **Subprocess sandbox is process-isolation only.** Python tools run in
  a fresh `python` subprocess with a wall-clock timeout. There is no
  imports allowlist, no RLIMIT, no seccomp, no chroot. Don't deploy
  user-submitted Python tools without hardening this.
- **`--reload` flakiness on Windows + OneDrive** — see backend run note.
- **Frontend port** — Vite picks 5173 if free, 5174 otherwise. Either
  works; the proxy target is 8001 regardless.
