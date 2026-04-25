"""Mock data for each business function's default workspace views.

Numbers are illustrative placeholders meant to demonstrate the layout and chart
shapes; in a real deployment these would be wired through the data source layer.
"""
from models.schemas import ChartSpec, KpiCard, TableSpec, WorkspaceData


# ── Investment Portfolio ────────────────────────────────────────────────────
def _portfolio() -> WorkspaceData:
    nav_trend = [
        {"month": m, "nav": v}
        for m, v in zip(
            ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"],
            [3.62, 3.65, 3.68, 3.70, 3.71, 3.73, 3.74, 3.78],
        )
    ]
    sector_mix = [
        {"sector": "CC30", "weight": 40.9},
        {"sector": "CC15", "weight": 21.0},
        {"sector": "GN30", "weight": 21.8},
        {"sector": "Treasury", "weight": 5.9},
        {"sector": "Other", "weight": 10.4},
    ]
    return WorkspaceData(
        function_id="investment_portfolio",
        function_name="Investment Portfolio Analytics",
        kpis=[
            KpiCard(label="NAV",        value="$3.78B",  delta="+0.12%", delta_dir="up",   sublabel="vs prior month"),
            KpiCard(label="Book Yield", value="5.44%",   delta="+3 bps", delta_dir="up",   sublabel="weighted"),
            KpiCard(label="OAD",        value="4.25 yr", delta="-0.05",  delta_dir="down", sublabel="vs prior"),
            KpiCard(label="OAS",        value="44 bps",  delta="-2 bps", delta_dir="down", sublabel="weighted"),
        ],
        charts=[
            ChartSpec(
                id="nav_trend",
                title="NAV Trajectory ($B)",
                type="area",
                data=nav_trend,
                x_key="month",
                y_keys=["nav"],
                description="Net asset value over the trailing 8 months.",
            ),
            ChartSpec(
                id="sector_mix",
                title="Sector Allocation (%)",
                type="bar",
                data=sector_mix,
                x_key="sector",
                y_keys=["weight"],
                description="Portfolio allocation by MBS sector and treasuries.",
            ),
        ],
        tables=[
            TableSpec(
                title="Top Holdings",
                columns=["Pool", "Coupon", "MV ($MM)", "Weight", "OAS (bps)", "OAD (yr)"],
                rows=[
                    ["FNMA_CC30_6.0_A", "6.00%", "603", "16.1%", "42", "4.8"],
                    ["FNMA_CC30_5.5_B", "5.50%", "421", "11.3%", "47", "4.5"],
                    ["GNMA_GN30_5.5_C", "5.50%", "318", "8.5%",  "38", "4.2"],
                    ["FNMA_CC15_4.5_D", "4.50%", "287", "7.7%",  "44", "3.4"],
                    ["FHLB_CDBT_4.0_M", "4.00%", "212", "5.7%",  "21", "3.5"],
                ],
            ),
            TableSpec(
                title="Risk Limits",
                columns=["Metric", "Current", "Limit", "Status"],
                rows=[
                    ["EVE +200bp",        "-3.8%",  "-5.0%",  "OK"],
                    ["OAD",               "4.25yr", "5.5yr",  "OK"],
                    ["Largest Position",  "16.1%",  "20.0%",  "OK"],
                    ["CC30 Sector",       "40.9%",  "45.0%",  "WATCH"],
                ],
            ),
        ],
        insights=[
            "EVE +200bp at -3.8% — 120 bps cushion to mandate floor of -5.0%.",
            "CC30 sector exposure (40.9%) is approaching the 45% concentration cap.",
            "FNMA_CC30_6.5_G OAS widened 8 bps; cohort-relative cheap signal.",
        ],
    )


# ── Interest Rate Risk ──────────────────────────────────────────────────────
def _irr() -> WorkspaceData:
    eve_shock = [
        {"shock": "-200", "eve_pct":  8.2},
        {"shock": "-100", "eve_pct":  4.1},
        {"shock":    "0", "eve_pct":  0.0},
        {"shock": "+100", "eve_pct": -2.1},
        {"shock": "+200", "eve_pct": -3.8},
        {"shock": "+300", "eve_pct": -6.2},
    ]
    krd = [
        {"bucket": "1Y", "krd": 0.18},
        {"bucket": "2Y", "krd": 0.42},
        {"bucket": "3Y", "krd": 0.61},
        {"bucket": "5Y", "krd": 1.10},
        {"bucket": "7Y", "krd": 1.05},
        {"bucket": "10Y", "krd": 0.71},
        {"bucket": "30Y", "krd": 0.18},
    ]
    return WorkspaceData(
        function_id="interest_rate_risk",
        function_name="Interest Rate Risk Management",
        kpis=[
            KpiCard(label="EVE +200bp", value="-3.8%",  delta="120 bps cushion", delta_dir="up",   sublabel="limit -5.0%"),
            KpiCard(label="NII 12M",    value="$1.42B", delta="+1.8%",           delta_dir="up",   sublabel="vs base"),
            KpiCard(label="DV01",       value="$2.7MM", delta="-$0.1MM",         delta_dir="down", sublabel="portfolio"),
            KpiCard(label="Convexity",  value="-0.25",  delta="flat",            delta_dir="flat", sublabel="weighted"),
        ],
        charts=[
            ChartSpec(
                id="eve_shock",
                title="EVE % vs Parallel Rate Shock",
                type="bar",
                data=eve_shock,
                x_key="shock",
                y_keys=["eve_pct"],
                description="Economic Value of Equity sensitivity to instantaneous parallel rate shocks.",
            ),
            ChartSpec(
                id="krd",
                title="Key Rate Durations (years)",
                type="bar",
                data=krd,
                x_key="bucket",
                y_keys=["krd"],
                description="Contribution to portfolio duration by tenor bucket.",
            ),
        ],
        tables=[
            TableSpec(
                title="Hedge Ladder",
                columns=["Instrument", "Notional ($MM)", "Tenor", "DV01 ($K)", "Direction"],
                rows=[
                    ["UST 5Y Future", "850", "5Y",  "412",  "Short"],
                    ["UST 10Y Future", "620", "10Y", "590",  "Short"],
                    ["SOFR Swap",      "500", "7Y",  "350",  "Pay Fixed"],
                    ["Eurodollar",     "200", "2Y",  "40",   "Short"],
                ],
            ),
        ],
        insights=[
            "Largest KRD exposure is the 5Y bucket at 1.10 yr — primary driver of EVE +200bp loss.",
            "+300bp shock breaches mandate by 1.2pp; review hedge sizing if rates extend higher.",
            "Convexity of -0.25 amplifies losses in larger up-shocks; offset hedges in 7Y are appropriate.",
        ],
    )


# ── Liquidity ───────────────────────────────────────────────────────────────
def _liquidity() -> WorkspaceData:
    lcr_trend = [
        {"month": m, "lcr": v} for m, v in zip(
            ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"],
            [128, 131, 133, 130, 129, 132, 134, 136],
        )
    ]
    cash_ladder = [
        {"bucket": "0-7d",   "inflow": 18.4, "outflow": -16.2},
        {"bucket": "8-30d",  "inflow": 22.1, "outflow": -19.7},
        {"bucket": "31-90d", "inflow": 31.5, "outflow": -28.9},
        {"bucket": "91-180d","inflow": 41.2, "outflow": -38.4},
        {"bucket": "181-365d","inflow": 58.8,"outflow": -52.0},
    ]
    return WorkspaceData(
        function_id="liquidity_management",
        function_name="Liquidity & Funding",
        kpis=[
            KpiCard(label="HQLA",         value="$24.6B",  delta="+$0.4B",  delta_dir="up",   sublabel="Level 1+2"),
            KpiCard(label="LCR",          value="136%",    delta="+2 pp",   delta_dir="up",   sublabel="reg min 100%"),
            KpiCard(label="NSFR",         value="121%",    delta="flat",    delta_dir="flat", sublabel="reg min 100%"),
            KpiCard(label="Deposit Beta", value="0.42",    delta="+0.02",   delta_dir="up",   sublabel="cycle to date"),
        ],
        charts=[
            ChartSpec(
                id="lcr_trend",
                title="LCR Trend (%)",
                type="line",
                data=lcr_trend,
                x_key="month",
                y_keys=["lcr"],
                description="Liquidity Coverage Ratio over trailing 8 months.",
            ),
            ChartSpec(
                id="cash_ladder",
                title="Cash Ladder ($B, by tenor)",
                type="stacked_bar",
                data=cash_ladder,
                x_key="bucket",
                y_keys=["inflow", "outflow"],
                description="Projected gross inflows and outflows by maturity bucket.",
            ),
        ],
        tables=[
            TableSpec(
                title="Deposit Mix",
                columns=["Category", "Balance ($B)", "Rate", "Beta", "Stickiness"],
                rows=[
                    ["Retail Savings",   "82.4",  "3.85%", "0.38", "High"],
                    ["Retail Checking",  "31.2",  "0.20%", "0.05", "Very High"],
                    ["Commercial",       "44.7",  "4.65%", "0.71", "Medium"],
                    ["Brokered CD",      "12.1",  "5.15%", "0.94", "Low"],
                ],
            ),
        ],
        insights=[
            "LCR at 136% provides comfortable buffer above 100% regulatory minimum.",
            "Deposit beta uptick to 0.42 reflects ongoing repricing of rate-sensitive commercial deposits.",
            "Net cumulative outflow gap closes by 90d — funding profile is well-matched.",
        ],
    )


# ── Credit Risk ─────────────────────────────────────────────────────────────
def _credit() -> WorkspaceData:
    vintage = [
        {"vintage": "2021", "30dpd": 1.2, "60dpd": 0.4, "90dpd": 0.18},
        {"vintage": "2022", "30dpd": 1.8, "60dpd": 0.7, "90dpd": 0.32},
        {"vintage": "2023", "30dpd": 2.4, "60dpd": 1.0, "90dpd": 0.51},
        {"vintage": "2024", "30dpd": 2.9, "60dpd": 1.3, "90dpd": 0.68},
        {"vintage": "2025", "30dpd": 1.6, "60dpd": 0.5, "90dpd": 0.21},
    ]
    co_forecast = [
        {"month": m, "actual": a, "forecast": f}
        for m, a, f in [
            ("Sep", 4.42, None),  ("Oct", 4.55, None),  ("Nov", 4.61, None),
            ("Dec", 4.50, None),  ("Jan", 4.38, None),  ("Feb", 4.21, None),
            ("Mar", None, 4.12),  ("Apr", None, 4.04),  ("May", None, 3.95),
        ]
    ]
    return WorkspaceData(
        function_id="credit_risk",
        function_name="Credit Risk Analytics",
        kpis=[
            KpiCard(label="Charge-off Rate", value="4.21%", delta="-17 bps", delta_dir="down", sublabel="annualized"),
            KpiCard(label="PD (weighted)",   value="2.84%", delta="-12 bps", delta_dir="down", sublabel="next 12m"),
            KpiCard(label="LGD",             value="68.4%", delta="flat",    delta_dir="flat", sublabel="recovery 31.6%"),
            KpiCard(label="Allowance",       value="$3.2B", delta="+$45MM",  delta_dir="up",   sublabel="CECL"),
        ],
        charts=[
            ChartSpec(
                id="vintage",
                title="Vintage Delinquency Roll Rates (%)",
                type="bar",
                data=vintage,
                x_key="vintage",
                y_keys=["30dpd", "60dpd", "90dpd"],
                description="Delinquency rates by origination vintage.",
            ),
            ChartSpec(
                id="co_forecast",
                title="Charge-off Trajectory (%, actual vs forecast)",
                type="line",
                data=co_forecast,
                x_key="month",
                y_keys=["actual", "forecast"],
                description="Trailing 6 months of actual charge-offs and 3-month forward forecast.",
            ),
        ],
        tables=[
            TableSpec(
                title="CECL Allowance Walk ($MM)",
                columns=["Component", "Current Q", "Prior Q", "Change"],
                rows=[
                    ["Beginning Balance",  "3,155",  "3,098",  "+57"],
                    ["Provision",          "+285",   "+312",   "-27"],
                    ["Net Charge-offs",    "-238",   "-255",   "+17"],
                    ["Ending Balance",     "3,202",  "3,155",  "+47"],
                ],
            ),
        ],
        insights=[
            "2024 vintage 90+dpd at 0.68% is the high watermark — peak loss pull-forward expected in 2026 H2.",
            "Charge-off rate has rolled lower for 3 consecutive months, consistent with stable employment.",
            "Allowance build of $47MM driven by reserve for commercial CRE concentration.",
        ],
    )


# ── Treasury / FTP ──────────────────────────────────────────────────────────
def _treasury() -> WorkspaceData:
    ftp_curve = [
        {"tenor": "1M",  "rate": 4.32},
        {"tenor": "3M",  "rate": 4.45},
        {"tenor": "6M",  "rate": 4.55},
        {"tenor": "1Y",  "rate": 4.62},
        {"tenor": "2Y",  "rate": 4.55},
        {"tenor": "5Y",  "rate": 4.61},
        {"tenor": "7Y",  "rate": 4.74},
        {"tenor": "10Y", "rate": 4.84},
    ]
    nim_walk = [
        {"step": "Prior NIM",       "value": 6.42},
        {"step": "+ Asset Yield",   "value": 0.18},
        {"step": "- Funding Cost",  "value": -0.31},
        {"step": "+ Mix Shift",     "value": 0.04},
        {"step": "Current NIM",     "value": 6.33},
    ]
    return WorkspaceData(
        function_id="treasury",
        function_name="Treasury & Funds Transfer Pricing",
        kpis=[
            KpiCard(label="FTP 5Y",       value="4.61%",  delta="+8 bps",  delta_dir="up",   sublabel="vs prior week"),
            KpiCard(label="NIM",          value="6.33%",  delta="-9 bps",  delta_dir="down", sublabel="trailing quarter"),
            KpiCard(label="Funding Cost", value="3.41%",  delta="+12 bps", delta_dir="up",   sublabel="weighted"),
            KpiCard(label="Surplus",      value="$8.4B",  delta="+$0.6B",  delta_dir="up",   sublabel="deployable"),
        ],
        charts=[
            ChartSpec(
                id="ftp_curve",
                title="FTP Curve (%)",
                type="line",
                data=ftp_curve,
                x_key="tenor",
                y_keys=["rate"],
                description="Internal Funds Transfer Pricing curve by tenor (current snapshot).",
            ),
            ChartSpec(
                id="nim_walk",
                title="NIM Walk (%)",
                type="bar",
                data=nim_walk,
                x_key="step",
                y_keys=["value"],
                description="Drivers of net interest margin change vs prior period.",
            ),
        ],
        tables=[
            TableSpec(
                title="Funding Flows ($B, monthly)",
                columns=["Source", "Inflow", "Outflow", "Net"],
                rows=[
                    ["Retail Deposits",   "12.4", "8.1",  "+4.3"],
                    ["Wholesale Funding", "5.8",  "7.2",  "-1.4"],
                    ["FHLB Advances",     "2.1",  "0.9",  "+1.2"],
                    ["Commercial Paper",  "1.4",  "1.6",  "-0.2"],
                ],
            ),
        ],
        insights=[
            "FTP 5Y up 8 bps reflects belly-of-curve sell-off; review pricing on 5Y product offers.",
            "NIM compressed 9 bps as funding cost outpaced asset yield re-pricing.",
            "Surplus liquidity at $8.4B — consider lengthening duration in HQLA stack.",
        ],
    )


# ── Capital Planning ────────────────────────────────────────────────────────
def _capital() -> WorkspaceData:
    cet1_traj = [
        {"quarter": q, "cet1": v}
        for q, v in zip(
            ["Q3-24", "Q4-24", "Q1-25", "Q2-25", "Q3-25", "Q4-25", "Q1-26"],
            [12.6, 12.8, 13.0, 13.1, 13.0, 13.2, 13.4],
        )
    ]
    rwa = [
        {"category": "Credit Risk",  "rwa": 168.4},
        {"category": "Market Risk",  "rwa":  18.2},
        {"category": "Operational",  "rwa":  41.6},
        {"category": "CVA",          "rwa":   4.3},
    ]
    stress_ppnr = [
        {"quarter": "Q1", "base": 2.41, "adverse": 1.92, "severe": 1.18},
        {"quarter": "Q2", "base": 2.46, "adverse": 1.78, "severe": 0.85},
        {"quarter": "Q3", "base": 2.52, "adverse": 1.65, "severe": 0.62},
        {"quarter": "Q4", "base": 2.58, "adverse": 1.71, "severe": 0.71},
    ]
    return WorkspaceData(
        function_id="capital_planning",
        function_name="Capital Planning & CCAR",
        kpis=[
            KpiCard(label="CET1",       value="13.4%",   delta="+20 bps", delta_dir="up", sublabel="vs prior"),
            KpiCard(label="Tier 1",     value="14.6%",   delta="+18 bps", delta_dir="up", sublabel="vs prior"),
            KpiCard(label="RWA",        value="$232.5B", delta="+$2.1B",  delta_dir="up", sublabel="QoQ"),
            KpiCard(label="SCB",        value="2.5%",    delta="flat",    delta_dir="flat", sublabel="vs Fed"),
        ],
        charts=[
            ChartSpec(
                id="cet1_traj",
                title="CET1 Ratio Trajectory (%)",
                type="line",
                data=cet1_traj,
                x_key="quarter",
                y_keys=["cet1"],
                description="Common Equity Tier 1 ratio over trailing 7 quarters.",
            ),
            ChartSpec(
                id="rwa",
                title="RWA Composition ($B)",
                type="pie",
                data=rwa,
                x_key="category",
                y_keys=["rwa"],
                description="Risk-weighted assets by Basel III category.",
            ),
            ChartSpec(
                id="stress_ppnr",
                title="Stress PPNR by Scenario ($B)",
                type="bar",
                data=stress_ppnr,
                x_key="quarter",
                y_keys=["base", "adverse", "severe"],
                description="Pre-Provision Net Revenue under base, adverse, and severely-adverse scenarios.",
            ),
        ],
        tables=[
            TableSpec(
                title="Capital Actions (FY 2026 plan)",
                columns=["Action", "Amount ($B)", "Status"],
                rows=[
                    ["Common Dividend",        "1.20", "Approved"],
                    ["Share Buybacks",         "3.00", "In Flight"],
                    ["Preferred Issuance",     "0.50", "Planned"],
                    ["AT1 Redemption",         "0.75", "Planned"],
                ],
            ),
        ],
        insights=[
            "CET1 at 13.4% provides 290 bps cushion above the 10.5% minimum + SCB.",
            "Severe-adverse Q3 PPNR of $0.62B is the trough — implies $4.8B post-stress capital build.",
            "RWA up $2.1B QoQ driven by commercial loan growth; review optimization opportunities.",
        ],
    )


# ── Market Risk ─────────────────────────────────────────────────────────────
def _market_risk() -> WorkspaceData:
    var_by_desk = [
        {"desk": "Rates",        "var": 8.4,  "svar": 14.2},
        {"desk": "MBS",          "var": 12.1, "svar": 22.8},
        {"desk": "Credit",       "var": 6.8,  "svar": 11.9},
        {"desk": "FX",           "var": 2.1,  "svar":  3.7},
        {"desk": "Equity Hedge", "var": 1.9,  "svar":  3.2},
    ]
    svar_trend = [
        {"week": w, "svar": v}
        for w, v in zip(
            ["W-12", "W-10", "W-8", "W-6", "W-4", "W-2", "Today"],
            [49.2, 51.7, 54.1, 56.0, 55.8, 54.3, 55.8],
        )
    ]
    return WorkspaceData(
        function_id="market_risk",
        function_name="Market Risk & VaR",
        kpis=[
            KpiCard(label="1d 99% VaR", value="$31.3MM", delta="+$1.8MM", delta_dir="up",   sublabel="trading book"),
            KpiCard(label="SVaR",       value="$55.8MM", delta="+$1.5MM", delta_dir="up",   sublabel="stressed"),
            KpiCard(label="IRC",        value="$112MM",  delta="-$4MM",   delta_dir="down", sublabel="incremental risk"),
            KpiCard(label="BT Excpts",  value="2",       delta="vs 4 limit", delta_dir="flat", sublabel="trailing 250d"),
        ],
        charts=[
            ChartSpec(
                id="var_by_desk",
                title="VaR & SVaR by Desk ($MM)",
                type="bar",
                data=var_by_desk,
                x_key="desk",
                y_keys=["var", "svar"],
                description="1-day 99% VaR and Stressed VaR by trading desk.",
            ),
            ChartSpec(
                id="svar_trend",
                title="SVaR Trend ($MM, weekly)",
                type="line",
                data=svar_trend,
                x_key="week",
                y_keys=["svar"],
                description="Trailing 12 weeks of stressed VaR for the trading book.",
            ),
        ],
        tables=[
            TableSpec(
                title="FRTB Sensitivities ($MM)",
                columns=["Risk Class", "Delta", "Vega", "Curvature"],
                rows=[
                    ["GIRR (rates)",     "21.3", "4.8",  "1.2"],
                    ["CSR (credit)",     "8.1",  "1.2",  "0.4"],
                    ["FX",               "3.4",  "0.6",  "0.1"],
                    ["Equity",           "1.8",  "0.4",  "0.2"],
                    ["Commodity",        "0.0",  "0.0",  "0.0"],
                ],
            ),
        ],
        insights=[
            "MBS desk VaR at $12.1MM is the largest contributor — consider hedge rebalancing.",
            "2 back-test exceptions in trailing 250 days, well within the 4-exception green zone.",
            "SVaR has stabilized at $55.8MM after the late-Q1 spike on rate volatility.",
        ],
    )


# ── Financial Reporting ─────────────────────────────────────────────────────
def _fpa() -> WorkspaceData:
    revenue_trend = [
        {"month": m, "actual": a, "plan": p}
        for m, a, p in [
            ("Sep", 3.21, 3.15), ("Oct", 3.32, 3.20), ("Nov", 3.28, 3.25),
            ("Dec", 3.41, 3.30), ("Jan", 3.18, 3.22), ("Feb", 3.24, 3.28),
            ("Mar", 3.36, 3.33),
        ]
    ]
    expense_drivers = [
        {"category": "Compensation",   "actual": 1.42, "plan": 1.38},
        {"category": "Technology",     "actual": 0.61, "plan": 0.55},
        {"category": "Marketing",      "actual": 0.42, "plan": 0.40},
        {"category": "Occupancy",      "actual": 0.18, "plan": 0.18},
        {"category": "Other",          "actual": 0.34, "plan": 0.32},
    ]
    return WorkspaceData(
        function_id="financial_reporting",
        function_name="Financial Planning & Reporting",
        kpis=[
            KpiCard(label="Revenue (M)",  value="$3.36B", delta="+1.2% vs plan", delta_dir="up",   sublabel="month"),
            KpiCard(label="OpEx (M)",     value="$2.97B", delta="+2.4% vs plan", delta_dir="up",   sublabel="month"),
            KpiCard(label="PPNR (M)",     value="$0.39B", delta="-3.1% vs plan", delta_dir="down", sublabel="month"),
            KpiCard(label="YTD Variance", value="+$48MM", delta="vs plan",        delta_dir="up",   sublabel="net favorable"),
        ],
        charts=[
            ChartSpec(
                id="revenue_trend",
                title="Revenue: Actual vs Plan ($B)",
                type="line",
                data=revenue_trend,
                x_key="month",
                y_keys=["actual", "plan"],
                description="Monthly revenue actuals against plan over trailing 7 months.",
            ),
            ChartSpec(
                id="expense_drivers",
                title="Expense Drivers ($B)",
                type="bar",
                data=expense_drivers,
                x_key="category",
                y_keys=["actual", "plan"],
                description="Actual vs plan expense by major category.",
            ),
        ],
        tables=[
            TableSpec(
                title="Segment P&L Walk ($MM)",
                columns=["Segment", "Revenue", "OpEx", "PPNR", "vs Plan"],
                rows=[
                    ["Card",          "1,820",  "1,510", "310",  "+$8MM"],
                    ["Consumer Bank", "780",    "650",   "130",  "+$12MM"],
                    ["Commercial",    "560",    "440",   "120",  "-$4MM"],
                    ["Auto",          "200",    "170",   "30",   "+$2MM"],
                    ["Other",         "0",      "200",   "-200", "-$6MM"],
                ],
            ),
        ],
        insights=[
            "Revenue ahead of plan by $40MM, driven by stronger Card interchange and net interest income.",
            "Technology expense is $60MM over plan due to accelerated cloud migration spend.",
            "Commercial PPNR $4MM below plan — review impact of CRE provision build.",
        ],
    )


_BUILDERS = {
    "investment_portfolio":  _portfolio,
    "interest_rate_risk":    _irr,
    "liquidity_management":  _liquidity,
    "credit_risk":           _credit,
    "treasury":              _treasury,
    "capital_planning":      _capital,
    "market_risk":           _market_risk,
    "financial_reporting":   _fpa,
}


def get_workspace(function_id: str) -> WorkspaceData | None:
    builder = _BUILDERS.get(function_id)
    return builder() if builder else None
