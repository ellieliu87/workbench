# CMA Workbench

Self-service analytics platform for analysts in **Capital Markets** and **Finance**
at Capital One. Inspired in design by the `oasia` portfolio workbench but built
as a **general-purpose** workbench: every analyst lands on a function-selection
panel, picks a domain, and gets a workspace of default views plus a domain-aware
AI chat agent. Data sources, agent skills, and plots are all user-configurable.

## Tech stack

- **Frontend**: React 18 · Vite · TypeScript · Tailwind CSS · Radix/shadcn
  primitives · Recharts · Zustand
- **Backend**: FastAPI · Uvicorn · Pydantic v2

## Project layout

```
cma/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── models/
│   │   └── schemas.py
│   ├── routers/
│   │   ├── auth.py            # mock login + bearer-token auth
│   │   ├── functions.py       # business-function catalog
│   │   ├── workspace.py       # default views per function
│   │   ├── chat.py            # function-aware mock agent
│   │   ├── datasources.py     # Snowflake / OneLake / file uploads / etc.
│   │   ├── skills.py          # agent-skill registry (toggle, upload, CRUD)
│   │   └── plots.py           # QuickSight-style plot builder
│   └── services/
│       └── workspace_data.py  # mock analytics for each function
└── frontend/
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── components/
        │   ├── layout/        # AppShell · Sidebar · Topbar
        │   ├── chat/          # ChatPanel (oasia-style markdown chat)
        │   └── charts/        # Recharts wrapper for line/bar/area/pie/scatter
        ├── pages/
        │   ├── Login/
        │   ├── Home/          # function-selection cards
        │   ├── Workspace/     # KPIs · charts · tables · insights
        │   └── Settings/      # data sources · skills · plot builder
        ├── store/             # Zustand: auth, chat
        ├── lib/               # axios + cn() helper
        └── types/
```

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
# Windows:  .\.venv\Scripts\activate
# *nix:     source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api/*` to
http://localhost:8000.

## Sign-in

Demo credentials (any of these usernames work):

| Username | Role                       | Department      |
|----------|----------------------------|-----------------|
| alice    | Capital Markets Analyst    | Capital Markets |
| bob      | Treasury Analyst           | Finance         |
| carol    | Senior Quant               | Capital Markets |
| david    | Risk Analyst               | Finance         |
| demo     | Capital Markets Analyst    | Capital Markets |

Password: **`capital1`**

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

Each function ships with default KPIs, charts, tables, and insights, plus an
agent that specializes its responses to that domain.

## Design notes — borrowed from oasia

- Slide-out chat panel anchored to the right, draggable to resize, with a quick-query
  ribbon and rich markdown rendering that highlights warnings, currency, and bps
  using accent colors.
- Sidebar of navigable functions with a brand block and user footer.
- Workspaces use a 4-up KPI strip, a 2-column chart grid, then tables and insights.
- KPI cards are buttons — clicking one asks the agent to explain that metric.

## Customization

Open **Settings** from the sidebar:

- **Data Sources**: Snowflake, OneLake, Postgres, REST APIs, S3, or direct file
  upload (CSV / Parquet / JSON / XLSX). Each source has a *Test* and a *Delete*
  button. Uploads are accepted but not persisted to disk in this demo.
- **Agent Skills**: enable or disable shipped skills (Explain Metric, Risk Limit
  Monitor, ALCO Report, Rate Shock, Text-to-SQL), upload a custom skill manifest,
  or compose a new skill in-app with category, description, system instructions,
  and tools list.
- **Plot Builder**: a QuickSight-style designer — pick a data source, chart
  type (line / bar / area / pie / scatter / stacked bar), X axis, multiple Y
  axes, and aggregation. Live preview on the right; saved plots become available
  to drop into any workspace.

## Notes

- All persistence is in-process memory: tokens, data sources, skills, and plots
  reset on backend restart.
- The chat agent is mock by default and uses keyword-based routing to pick the
  best response template. The wiring point for a real LLM is `routers/chat.py`
  inside `_generate_response()` — drop in your orchestrator there.
- No real credentials are ever transmitted; the data-source forms collect host
  and database name only.
