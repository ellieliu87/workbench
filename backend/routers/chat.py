"""Chat router - function-aware mock agent that returns markdown insights.

The architecture mirrors oasia: a list of agent personas, mock responses keyed
by user-intent keywords, plus a per-function specialization layer so the same
chat panel feels native inside each business function workspace.
"""
from datetime import date
from fastapi import APIRouter, Depends

from models.schemas import AgentInfo, ChatMessage, ChatResponse
from routers.auth import get_current_user

router = APIRouter()


AGENTS: list[AgentInfo] = [
    AgentInfo(
        id="orchestrator",
        name="CMA Orchestrator",
        description="Routes queries to the right specialist agent and synthesizes results.",
        icon="cpu",
        color="#004977",
    ),
    AgentInfo(
        id="data_explainer",
        name="Data Explainer",
        description="Explains where a metric came from and how it is computed.",
        icon="database",
        color="#0891B2",
    ),
    AgentInfo(
        id="risk_monitor",
        name="Risk Monitor",
        description="Surfaces breaches, near-breaches, and concentration alerts.",
        icon="shield-alert",
        color="#DC2626",
    ),
    AgentInfo(
        id="report_writer",
        name="Report Writer",
        description="Drafts ALCO-ready summaries and management reporting packages.",
        icon="file-text",
        color="#7C3AED",
    ),
    AgentInfo(
        id="scenario_analyst",
        name="Scenario Analyst",
        description="Runs what-if rate, deposit beta, and credit stress scenarios.",
        icon="flask",
        color="#D97706",
    ),
    AgentInfo(
        id="sql_assistant",
        name="SQL Assistant",
        description="Translates analyst questions into SQL against configured data sources.",
        icon="code",
        color="#059669",
    ),
]


# ── Function-specific deep dives ────────────────────────────────────────────
_FUNCTION_BRIEFS: dict[str, str] = {
    "investment_portfolio": """## Investment Portfolio — Snapshot

**NAV**: $3.78B (+0.12% MoM)  •  **Book Yield**: 5.44%  •  **OAD**: 4.25 yr  •  **OAS**: 44 bps

**Risk Flags**
- EVE +200bp at -3.8% (mandate floor -5.0%, cushion 120 bps)
- CC30 sector at 40.9% — approaching 45% concentration cap
- Largest position FNMA_CC30_6.0_A at 16.1% of NAV

**Today's Watchlist**
- FNMA_CC30_6.5_G OAS widened 8 bps; cohort-relative cheap signal
- 3 new pools from dealer desk (52-58 bps OAS) pending review""",
    "interest_rate_risk": """## Interest Rate Risk — Snapshot

**EVE +200bp**: -3.8%  •  **NII 12M**: $1.42B  •  **DV01**: $2.7MM  •  **Convexity**: -0.25

**Shock Profile**
| Shock | EVE % |
|-------|-------|
| -200  | +8.2% |
| -100  | +4.1% |
| +100  | -2.1% |
| +200  | -3.8% (cushion 120 bps to limit) |
| +300  | -6.2% (breach by 1.2 pp) |

**Top KRD bucket**: 5Y at 1.10 yr — primary driver of EVE +200bp loss.""",
    "liquidity_management": """## Liquidity & Funding — Snapshot

**HQLA**: $24.6B  •  **LCR**: 136%  •  **NSFR**: 121%  •  **Deposit Beta**: 0.42

**Deposit mix**: Retail Savings $82.4B (β 0.38) drives 47% of base funding. Brokered CD $12.1B carries the highest beta (0.94) but only 7% of mix.

**Cash ladder**: net cumulative outflow gap closes by 90 days — funding profile is well-matched.""",
    "credit_risk": """## Credit Risk — Snapshot

**Charge-off Rate**: 4.21% (-17 bps)  •  **PD (12m)**: 2.84%  •  **LGD**: 68.4%  •  **Allowance**: $3.2B

**Vintage signal**: 2024 vintage 90+dpd at 0.68% is the high watermark. Peak loss pull-forward expected in 2026 H2.

**CECL walk**: $47MM build this quarter, driven by reserve for commercial CRE concentration.""",
    "treasury": """## Treasury / FTP — Snapshot

**FTP 5Y**: 4.61% (+8 bps)  •  **NIM**: 6.33% (-9 bps)  •  **Funding Cost**: 3.41%  •  **Surplus**: $8.4B

**NIM walk**: asset yield repricing (+18 bps) was outweighed by funding cost (-31 bps) and a small positive mix shift (+4 bps).

**Action**: review pricing on 5Y product offers given the belly-of-curve sell-off; consider lengthening duration in HQLA stack with surplus.""",
    "capital_planning": """## Capital Planning — Snapshot

**CET1**: 13.4% (+20 bps)  •  **Tier 1**: 14.6%  •  **RWA**: $232.5B (+$2.1B QoQ)  •  **SCB**: 2.5%

**Stress posture**: severe-adverse trough is Q3 PPNR $0.62B; implies $4.8B post-stress capital build over the 9-quarter horizon.

**Capital actions in flight**: $3.0B share buybacks; $1.2B dividends approved.""",
    "market_risk": """## Market Risk — Snapshot

**1d 99% VaR**: $31.3MM  •  **SVaR**: $55.8MM  •  **IRC**: $112MM  •  **Back-test exceptions**: 2 / 250d (green zone)

**Top risk concentration**: MBS desk VaR $12.1MM — consider hedge rebalancing.

**FRTB GIRR delta**: $21.3MM is the dominant FRTB sensitivity; rate shock vega is $4.8MM.""",
    "financial_reporting": """## FP&A — Snapshot

**Revenue**: $3.36B (+1.2% vs plan)  •  **OpEx**: $2.97B (+2.4% vs plan)  •  **PPNR**: $0.39B (-3.1% vs plan)  •  **YTD Variance**: +$48MM net favorable

**Drivers**
- Revenue beat by $40MM on stronger Card interchange and NII
- Technology expense $60MM over plan from accelerated cloud migration
- Commercial PPNR $4MM below plan due to CRE provision build""",
}


_FUNCTION_FOLLOWUPS: dict[str, str] = {
    "investment_portfolio": "Try: 'Why did OAS tighten?', 'Show me cheap pools', 'Run +200bp shock'.",
    "interest_rate_risk":   "Try: 'Explain the +300bp breach', 'Resize 7Y hedge', 'NII at +100bp'.",
    "liquidity_management": "Try: 'Stress LCR under 30% deposit run-off', 'Decompose deposit beta'.",
    "credit_risk":          "Try: 'CECL allowance walk', 'Forecast charge-offs by segment', 'Vintage detail'.",
    "treasury":             "Try: 'NIM walk by segment', 'Reprice 5Y product', 'Where to deploy surplus'.",
    "capital_planning":     "Try: 'Severe-adverse PPNR drivers', 'RWA optimization ideas', 'Action ladder'.",
    "market_risk":          "Try: 'BT exception detail', 'FRTB curvature charge', 'Hedge MBS VaR'.",
    "financial_reporting":  "Try: 'Walk me through segment variance', 'Forecast Q2 PPNR', 'Top expense overruns'.",
}


# ── Generic agent intents (work across all functions) ──────────────────────
_INTENT_RESPONSES: dict[str, str] = {
    "explain": """## Data Lineage

The metric you're looking at is composed of:

1. **Source**: pulled from the configured data source (default: `cma_warehouse.fact_*`)
2. **Aggregation**: weighted by market value or balance, depending on the metric
3. **As-of**: end-of-day snapshot from prior business day

Open **Settings → Data Sources** to change the underlying connection or sync schedule.""",
    "risk":   """## Risk Posture

Across the function you are viewing, the agent is monitoring:
- Hard mandate limits (EVE, OAD, concentration)
- Soft warnings (sector caps, single-name exposure)
- Trend breaches (3-period rolling drift past tolerance)

No critical alerts at this time. The most-watched metric is in the snapshot above.""",
    "report": """## Draft Report

I can compose a one-page memo using the visible KPIs, top-line insights, and any
flagged risks. Click **Export** in the top-right of the workspace to render this
as HTML, or ask me to "tailor for ALCO" / "tailor for board".""",
    "what if": """## Scenario Analysis

Tell me which lever you want to flex:
- Rates: parallel shocks, twists, key-rate moves
- Credit: PD/LGD multipliers, vintage-level overlays
- Liquidity: deposit run-off, asset haircut
- FX: parallel currency moves

I'll re-run the page metrics under the scenario and narrate the deltas.""",
    "sql":    """## SQL Assistant

Tell me what you want and I'll draft a query against your active data source.
Example:
```sql
SELECT product_type, SUM(market_value) AS mv
FROM cma_warehouse.positions
WHERE as_of_date = CURRENT_DATE - 1
GROUP BY product_type
ORDER BY mv DESC;
```
Open **Settings → Data Sources** to switch which warehouse the query runs against.""",
}


def _generate_response(message: str, function_id: str | None) -> str:
    msg = message.lower()

    # Function-specific brief queries
    if function_id and any(k in msg for k in ("brief", "snapshot", "summary", "morning")):
        return _FUNCTION_BRIEFS.get(function_id, _FUNCTION_BRIEFS["investment_portfolio"])

    # Generic intents
    if "what if" in msg or "scenario" in msg or "shock" in msg:
        return _INTENT_RESPONSES["what if"]
    if "sql" in msg or "query" in msg or "select" in msg:
        return _INTENT_RESPONSES["sql"]
    if "report" in msg or "draft" in msg or "memo" in msg or "alco" in msg:
        return _INTENT_RESPONSES["report"]
    if "risk" in msg or "limit" in msg or "alert" in msg or "breach" in msg:
        return _INTENT_RESPONSES["risk"]
    if "explain" in msg or "where" in msg or "how is" in msg or "lineage" in msg:
        return _INTENT_RESPONSES["explain"]

    # Default: brief for the current function, plus suggestions
    base = _FUNCTION_BRIEFS.get(function_id or "", "")
    follow = _FUNCTION_FOLLOWUPS.get(function_id or "", "")
    if base:
        return f"{base}\n\n---\n_{follow}_"

    return f"""## CMA Workbench Agent

Hi! I'm a self-serve analytical assistant. Pick a business function from the home
panel and I'll specialize. I can:

- Explain underlying data and methodology behind any KPI or chart
- Surface risk breaches and concentration alerts
- Draft management reports (ALCO, board, regulator)
- Run what-if scenarios on rates, credit, and liquidity
- Translate plain-English questions into SQL against your data sources

Today is {date.today().strftime("%B %d, %Y")}."""


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(_: str = Depends(get_current_user)):
    return AGENTS


@router.post("/message", response_model=ChatResponse)
async def send_message(req: ChatMessage, _: str = Depends(get_current_user)):
    response = _generate_response(req.message, req.function_id)
    agent_name = next((a.name for a in AGENTS if a.id == req.agent_id), "CMA Orchestrator")
    return ChatResponse(response=response, agent_id=req.agent_id, agent_name=agent_name)
