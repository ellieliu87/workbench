"""Business functions router - lists the analytical domains analysts can choose from."""
from fastapi import APIRouter, Depends, HTTPException

from models.schemas import BusinessFunction
from routers.auth import get_current_user

router = APIRouter()


# Categories are inspired by Capital Markets & Analytics' real org topics
# (Capital Markets & Risks, Capital Resilience Analysis, Treasury Strategy &
# Execution, Balance Sheet Strategy) but compressed to three buckets so each
# bucket carries multiple related functions.
BUSINESS_FUNCTIONS: list[BusinessFunction] = [
    # ── Markets & Risk ─────────────────────────────────────────────────────
    BusinessFunction(
        id="investment_portfolio",
        name="Investment Portfolio Analytics",
        short_name="Portfolio",
        description="Monitor NAV, OAS, OAD, sector mix and unrealized P&L across the bank's investment book.",
        icon="briefcase",
        color="#004977",
        category="Markets & Risk",
        default_views=["Portfolio Snapshot", "Sector Allocation", "Top Holdings", "Risk Limits"],
        sample_metrics=["NAV", "OAS", "OAD", "Book Yield"],
    ),
    BusinessFunction(
        id="market_risk",
        name="Market Risk & VaR",
        short_name="Market Risk",
        description="VaR / SVaR, IRC, FRTB sensitivities, P&L attribution and back-testing exceptions across desks.",
        icon="activity",
        color="#FF5C5C",
        category="Markets & Risk",
        default_views=["VaR by Desk", "SVaR Trend", "FRTB Sensitivities", "Back-test Exceptions"],
        sample_metrics=["1d VaR", "SVaR", "IRC", "BT Exceptions"],
    ),
    BusinessFunction(
        id="credit_risk",
        name="Credit Risk Analytics",
        short_name="Credit",
        description="Portfolio PD/LGD, vintage roll-rates, charge-off forecasts, and CECL allowance walk.",
        icon="shield-alert",
        color="#DC2626",
        category="Markets & Risk",
        default_views=["Vintage Roll Rates", "PD Distribution", "Charge-off Forecast", "CECL Walk"],
        sample_metrics=["PD", "LGD", "Charge-off Rate", "Allowance"],
    ),

    # ── Treasury & Balance Sheet ───────────────────────────────────────────
    BusinessFunction(
        id="interest_rate_risk",
        name="Interest Rate Risk Management",
        short_name="IRR",
        description="EVE and NII sensitivities to parallel shocks, twists, and curve steepeners. ALCO-ready views.",
        icon="line-chart",
        color="#0891B2",
        category="Treasury & Balance Sheet",
        default_views=["EVE Shock Profile", "NII Sensitivity", "Key Rate Durations", "Hedge Ladder"],
        sample_metrics=["EVE +200bp", "NII 12M", "DV01", "Hedge Notional"],
    ),
    BusinessFunction(
        id="treasury",
        name="Treasury & Funds Transfer Pricing",
        short_name="Treasury",
        description="FTP curves by tenor & product, NIM attribution, intercompany funding flows, surplus deployment.",
        icon="banknote",
        color="#7C3AED",
        category="Treasury & Balance Sheet",
        default_views=["FTP Curve", "NIM Walk", "Funding Flows", "Surplus Deployment"],
        sample_metrics=["FTP 5Y", "NIM", "Funding Cost", "Surplus"],
    ),
    BusinessFunction(
        id="liquidity_management",
        name="Liquidity & Funding",
        short_name="Liquidity",
        description="HQLA stack, LCR/NSFR, deposit beta, and projected cash ladders for the bank's funding profile.",
        icon="droplet",
        color="#059669",
        category="Treasury & Balance Sheet",
        default_views=["HQLA Stack", "LCR Trend", "Deposit Mix", "Cash Ladder"],
        sample_metrics=["HQLA", "LCR", "NSFR", "Deposit Beta"],
    ),

    # ── Capital & Performance ──────────────────────────────────────────────
    BusinessFunction(
        id="capital_planning",
        name="Capital Planning & CCAR",
        short_name="Capital",
        description="CET1, RWA, stress scenario PPNR, and capital actions tracking against CCAR submissions.",
        icon="building-2",
        color="#D97706",
        category="Capital & Performance",
        default_views=["CET1 Trajectory", "RWA Composition", "Stress PPNR", "Capital Actions"],
        sample_metrics=["CET1", "RWA", "Tier 1", "SCB"],
    ),
    BusinessFunction(
        id="financial_reporting",
        name="Financial Planning & Reporting",
        short_name="FP&A",
        description="Revenue/expense forecasts, variance vs plan, segment P&L, and management reporting packages.",
        icon="file-spreadsheet",
        color="#00B8D9",
        category="Capital & Performance",
        default_views=["P&L vs Plan", "Segment Walk", "Expense Drivers", "Forecast Path"],
        sample_metrics=["Revenue", "OpEx", "PPNR", "Variance"],
    ),
]


# Display order for the home page (matches the buckets above)
CATEGORY_ORDER = [
    "Markets & Risk",
    "Treasury & Balance Sheet",
    "Capital & Performance",
]


@router.get("", response_model=list[BusinessFunction])
async def list_functions(_: str = Depends(get_current_user)):
    return BUSINESS_FUNCTIONS


@router.get("/categories")
async def list_categories(_: str = Depends(get_current_user)):
    return {"categories": CATEGORY_ORDER}


@router.get("/{function_id}", response_model=BusinessFunction)
async def get_function(function_id: str, _: str = Depends(get_current_user)):
    for f in BUSINESS_FUNCTIONS:
        if f.id == function_id:
            return f
    raise HTTPException(status_code=404, detail="Function not found")
