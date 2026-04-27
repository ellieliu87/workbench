"""Portfolio pack — Python tools.

Each tool is a self-contained Python function (no shared workflow state)
that takes JSON-friendly args and returns a JSON-friendly result. They are
ports of the oasia portfolio-planning workflow tools, adapted so they run
inside the cma sandbox subprocess.
"""
from __future__ import annotations

from packs import PackContext


def register_python_tools(ctx: PackContext) -> None:
    """Called from the pack's `register(ctx)`. One ctx call per tool."""

    ctx.register_python_tool(
        name="assess_portfolio_risk",
        description=(
            "Aggregate a portfolio's duration, liquidity, concentration and "
            "OAS risk profile, and emit a constraints envelope plus warning flags."
        ),
        parameters=[
            {"name": "by_product_type", "type": "object",
             "description": "Mapping product_type -> stats dict with keys total_balance_mm, avg_duration, avg_liquidity_score, avg_oas_bps.",
             "required": True},
        ],
        python_source=(
            'def assess_portfolio_risk(by_product_type: dict):\n'
            '    """Compute weighted portfolio-level risk metrics + constraint envelope.\n'
            '    Returns {"current_portfolio", "risk_constraints", "flags"}."""\n'
            '    if not by_product_type:\n'
            '        return {"error": "by_product_type is empty"}\n'
            '    durations, balances, liqs = [], [], []\n'
            '    for pt, stats in by_product_type.items():\n'
            '        b = float(stats.get("total_balance_mm", 0.0))\n'
            '        balances.append(b)\n'
            '        durations.append(float(stats.get("avg_duration", 5.0)))\n'
            '        liqs.append(float(stats.get("avg_liquidity_score", 7.0)))\n'
            '    total = sum(balances) or 1.0\n'
            '    def wavg(xs, ws):\n'
            '        s = sum(w for w in ws)\n'
            '        return sum(x * w for x, w in zip(xs, ws)) / s if s else 0.0\n'
            '    dur = wavg(durations, balances)\n'
            '    liq = wavg(liqs, balances)\n'
            '    conc = {pt: round(stats.get("total_balance_mm", 0) / total * 100, 1) for pt, stats in by_product_type.items()}\n'
            '    oas = {pt: float(stats.get("avg_oas_bps", 0.0)) for pt, stats in by_product_type.items()}\n'
            '    flags = []\n'
            '    if dur > 6.0: flags.append("Warning: Duration > 6.0 - elevated rate risk")\n'
            '    if dur < 3.5: flags.append("Warning: Duration < 3.5 - reinvestment risk")\n'
            '    if conc.get("CMBS", 0) > 30: flags.append("Warning: CMBS concentration > 30%")\n'
            '    if liq < 6.5: flags.append("Warning: Liquidity score below 6.5")\n'
            '    if conc.get("MBS", 0) < 40: flags.append("Info: MBS below 40% - consider increasing exposure")\n'
            '    return {\n'
            '        "current_portfolio": {\n'
            '            "total_balance_mm": total,\n'
            '            "duration_years": round(dur, 3),\n'
            '            "liquidity_score": round(liq, 2),\n'
            '            "concentration_pct": conc,\n'
            '            "avg_oas_by_type_bps": oas,\n'
            '        },\n'
            '        "risk_constraints": {\n'
            '            "duration_min": round(max(3.0, dur - 1.5), 2),\n'
            '            "duration_max": round(min(8.0, dur + 1.5), 2),\n'
            '            "liquidity_score_min": 6.0,\n'
            '            "max_cmbs_pct": 30.0,\n'
            '            "max_arm_pct": 20.0,\n'
            '        },\n'
            '        "flags": flags,\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="estimate_duration_impact",
        description="Estimate blended portfolio duration & liquidity after a proposed MBS / CMBS / Treasury allocation of new volume.",
        parameters=[
            {"name": "mbs_pct", "type": "number", "description": "MBS share of new volume (0-100).", "required": True},
            {"name": "cmbs_pct", "type": "number", "description": "CMBS share of new volume (0-100).", "required": True},
            {"name": "treasury_pct", "type": "number", "description": "Treasury share of new volume (0-100).", "required": True},
            {"name": "new_volume_mm", "type": "number", "description": "Total new purchase volume in $MM.", "required": True},
            {"name": "current_duration", "type": "number", "description": "Current portfolio duration in years.", "required": False},
            {"name": "current_balance_mm", "type": "number", "description": "Current portfolio balance in $MM.", "required": False},
            {"name": "current_liquidity_score", "type": "number", "description": "Current portfolio liquidity score (0-10).", "required": False},
        ],
        python_source=(
            'def estimate_duration_impact(mbs_pct, cmbs_pct, treasury_pct, new_volume_mm,\n'
            '                              current_duration=5.0, current_balance_mm=9000.0,\n'
            '                              current_liquidity_score=8.0):\n'
            '    """Mid-point asset-class durations: MBS=5.2, CMBS=5.8, TSY=6.0;\n'
            '    liquidity: MBS=8.8, CMBS=6.0, TSY=10.0."""\n'
            '    total = mbs_pct + cmbs_pct + treasury_pct\n'
            '    if abs(total - 100) > 0.5:\n'
            '        return {"error": f"Allocations must sum to 100, got {total}"}\n'
            '    new_dur = 5.2 * mbs_pct/100 + 5.8 * cmbs_pct/100 + 6.0 * treasury_pct/100\n'
            '    new_liq = 8.8 * mbs_pct/100 + 6.0 * cmbs_pct/100 + 10.0 * treasury_pct/100\n'
            '    blended_dur = (current_duration * current_balance_mm + new_dur * new_volume_mm)\\\n'
            '                  / (current_balance_mm + new_volume_mm)\n'
            '    blended_liq = (current_liquidity_score * current_balance_mm + new_liq * new_volume_mm)\\\n'
            '                  / (current_balance_mm + new_volume_mm)\n'
            '    return {\n'
            '        "new_purchase_duration": round(new_dur, 3),\n'
            '        "projected_portfolio_duration": round(blended_dur, 3),\n'
            '        "projected_liquidity_score": round(blended_liq, 2),\n'
            '        "duration_delta_years": round(blended_dur - current_duration, 3),\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="compute_new_volume_schedule",
        description="From monthly target and predicted-existing balances, compute new-volume needed each month, plus 12-month and 10-year totals.",
        parameters=[
            {"name": "monthly", "type": "array",
             "description": "List of {date, target_total_balance_mm, predicted_existing_balance_mm}.",
             "required": True},
        ],
        python_source=(
            'def compute_new_volume_schedule(monthly: list):\n'
            '    """Returns {next_12m_new_volume_mm, total_10yr_new_volume_mm, annual_totals_mm, schedule}."""\n'
            '    if not monthly:\n'
            '        return {"error": "monthly is empty"}\n'
            '    enriched = []\n'
            '    for row in monthly:\n'
            '        target = float(row.get("target_total_balance_mm", 0))\n'
            '        existing = float(row.get("predicted_existing_balance_mm", 0))\n'
            '        nv = max(0.0, target - existing)\n'
            '        enriched.append({\n'
            '            "date": row.get("date"),\n'
            '            "target_mm": round(target, 2),\n'
            '            "predicted_existing_mm": round(existing, 2),\n'
            '            "new_volume_mm": round(nv, 2),\n'
            '        })\n'
            '    next12 = sum(r["new_volume_mm"] for r in enriched[:12])\n'
            '    total = sum(r["new_volume_mm"] for r in enriched)\n'
            '    annual = {}\n'
            '    for i, r in enumerate(enriched):\n'
            '        y = f"Year {i//12 + 1}"\n'
            '        annual[y] = round(annual.get(y, 0) + r["new_volume_mm"], 2)\n'
            '    return {\n'
            '        "next_12m_new_volume_mm": round(next12, 2),\n'
            '        "total_10yr_new_volume_mm": round(total, 2),\n'
            '        "annual_totals_mm": annual,\n'
            '        "schedule": enriched,\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="generate_allocation_scenarios",
        description="Produce three allocation scenarios (conservative / moderate / aggressive) over MBS, CMBS, Treasury, with projected duration, liquidity, and yield pickup.",
        parameters=[],
        python_source=(
            'def generate_allocation_scenarios():\n'
            '    """Three named allocation templates with rationale."""\n'
            '    base_yield = 5.15\n'
            '    return [\n'
            '        {\n'
            '            "name": "Conservative",\n'
            '            "mbs_pct": 45.0, "cmbs_pct": 15.0, "treasury_pct": 40.0,\n'
            '            "duration": 5.0, "liquidity_score": 9.0,\n'
            '            "blended_yield_pct": round(base_yield - 0.30, 2),\n'
            '            "rationale": "Maximises Treasuries + high-grade agency MBS for IR-risk control + liquidity. Use when duration must stay near lower bound or when vol is elevated.",\n'
            '        },\n'
            '        {\n'
            '            "name": "Moderate",\n'
            '            "mbs_pct": 60.0, "cmbs_pct": 22.0, "treasury_pct": 18.0,\n'
            '            "duration": 5.3, "liquidity_score": 8.2,\n'
            '            "blended_yield_pct": round(base_yield, 2),\n'
            '            "rationale": "Balanced - solid yield pickup over Treasuries via agency MBS + IG CMBS, liquidity & duration in comfortable bounds.",\n'
            '        },\n'
            '        {\n'
            '            "name": "Aggressive",\n'
            '            "mbs_pct": 65.0, "cmbs_pct": 28.0, "treasury_pct": 7.0,\n'
            '            "duration": 5.7, "liquidity_score": 7.2,\n'
            '            "blended_yield_pct": round(base_yield + 0.35, 2),\n'
            '            "rationale": "Tilts toward higher-spread MBS + CMBS to maximise yield. Duration approaches upper bound. Use when curve is steep + credit is strong.",\n'
            '        },\n'
            '    ]\n'
        ),
    )

    ctx.register_python_tool(
        name="decompose_mbs_allocation",
        description="Split a chosen MBS allocation $MM into sub-buckets (CC30, GN30, CC15, ARM) with default weights, returning per-bucket purchase amounts.",
        parameters=[
            {"name": "mbs_volume_mm", "type": "number", "description": "Total MBS dollars to deploy in $MM.", "required": True},
            {"name": "weights", "type": "object", "description": "Optional override mapping bucket -> weight (sums to 1).", "required": False},
        ],
        python_source=(
            'def decompose_mbs_allocation(mbs_volume_mm: float, weights: dict | None = None):\n'
            '    """Default sub-bucket weights: CC30=0.55, GN30=0.20, CC15=0.15, ARM=0.10."""\n'
            '    default = {"CC30": 0.55, "GN30": 0.20, "CC15": 0.15, "ARM": 0.10}\n'
            '    w = weights or default\n'
            '    s = sum(w.values()) or 1.0\n'
            '    breakdown = []\n'
            '    for k, v in w.items():\n'
            '        share = v / s\n'
            '        breakdown.append({\n'
            '            "bucket": k,\n'
            '            "weight": round(share, 4),\n'
            '            "amount_mm": round(mbs_volume_mm * share, 2),\n'
            '        })\n'
            '    return {"mbs_volume_mm": round(mbs_volume_mm, 2), "breakdown": breakdown}\n'
        ),
    )

    ctx.register_python_tool(
        name="build_purchase_schedule",
        description="Spread an MBS sub-bucket allocation across a purchase horizon (e.g. 12 months) with even, front-loaded, or back-loaded pacing.",
        parameters=[
            {"name": "breakdown", "type": "array",
             "description": "List of {bucket, amount_mm} from decompose_mbs_allocation.",
             "required": True},
            {"name": "months", "type": "integer", "description": "Number of months to spread across.", "required": False},
            {"name": "pacing", "type": "string", "description": "even | front | back", "required": False},
        ],
        python_source=(
            'def build_purchase_schedule(breakdown: list, months: int = 12, pacing: str = "even"):\n'
            '    """Returns a flat schedule [{month, bucket, amount_mm}, ...]."""\n'
            '    if months <= 0:\n'
            '        return {"error": "months must be > 0"}\n'
            '    weights = []\n'
            '    if pacing == "front":\n'
            '        weights = [(months - i) for i in range(months)]\n'
            '    elif pacing == "back":\n'
            '        weights = [(i + 1) for i in range(months)]\n'
            '    else:\n'
            '        weights = [1.0] * months\n'
            '    total_w = sum(weights)\n'
            '    out = []\n'
            '    for b in breakdown:\n'
            '        amt = float(b.get("amount_mm", 0))\n'
            '        for m, w in enumerate(weights, start=1):\n'
            '            out.append({\n'
            '                "month": m,\n'
            '                "bucket": b.get("bucket"),\n'
            '                "amount_mm": round(amt * w / total_w, 3),\n'
            '            })\n'
            '    return {"pacing": pacing, "horizon_months": months, "schedule": out}\n'
        ),
    )

    ctx.register_python_tool(
        name="screen_universe_tool",
        description="Filter a pool universe by coupon, WALA, OAS, and CPR thresholds, then rank by a relative-value score.",
        parameters=[
            {"name": "universe", "type": "array",
             "description": "List of pool dicts with at least {pool_id, coupon, wala, oas_bps, cpr_3m}.",
             "required": True},
            {"name": "min_oas_bps", "type": "number", "description": "Minimum OAS in bps.", "required": False},
            {"name": "max_cpr", "type": "number", "description": "Maximum 3-month CPR (e.g. 12.0).", "required": False},
            {"name": "limit", "type": "integer", "description": "Top N to return.", "required": False},
        ],
        python_source=(
            'def screen_universe_tool(universe: list, min_oas_bps: float = 30.0,\n'
            '                     max_cpr: float = 15.0, limit: int = 25):\n'
            '    """Score = OAS - 5 * CPR_excess (CPR over 8 penalised). Higher is better."""\n'
            '    survivors = []\n'
            '    for p in universe:\n'
            '        oas = float(p.get("oas_bps", 0))\n'
            '        cpr = float(p.get("cpr_3m", 0))\n'
            '        if oas < min_oas_bps: continue\n'
            '        if cpr > max_cpr: continue\n'
            '        score = oas - 5 * max(0.0, cpr - 8.0)\n'
            '        survivors.append({**p, "rv_score": round(score, 2)})\n'
            '    survivors.sort(key=lambda x: x["rv_score"], reverse=True)\n'
            '    return {\n'
            '        "n_screened": len(universe),\n'
            '        "n_passed": len(survivors),\n'
            '        "top": survivors[:limit],\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="compute_pool_analytics_tool",
        description="Run a small Monte-Carlo-style approximation of cumulative cash flows for a pool under a parallel rate shock.",
        parameters=[
            {"name": "balance_mm", "type": "number", "description": "Pool balance in $MM.", "required": True},
            {"name": "coupon", "type": "number", "description": "Coupon rate (e.g. 5.5).", "required": True},
            {"name": "wala", "type": "integer", "description": "Weighted average loan age (months).", "required": True},
            {"name": "shock_bps", "type": "integer", "description": "Parallel rate shock in bps (e.g. -100, 0, +200).", "required": False},
            {"name": "horizon_months", "type": "integer", "description": "Cash-flow horizon.", "required": False},
        ],
        python_source=(
            'def compute_pool_analytics_tool(balance_mm: float, coupon: float, wala: int,\n'
            '                            shock_bps: int = 0, horizon_months: int = 60):\n'
            '    """Toy model — illustrative, not a real prepay engine."""\n'
            '    base_smm = 0.005 + max(0, (coupon - 5.5)) * 0.001\n'
            '    incentive = max(0, (-shock_bps) / 100) * 0.002\n'
            '    smm = max(0.001, base_smm + incentive)\n'
            '    bal = balance_mm\n'
            '    interest_total = 0.0\n'
            '    principal_total = 0.0\n'
            '    schedule = []\n'
            '    for m in range(1, horizon_months + 1):\n'
            '        scheduled = bal / max(1, 360 - wala - m + 1)\n'
            '        prepay = (bal - scheduled) * smm\n'
            '        interest = bal * (coupon / 100) / 12\n'
            '        bal = max(0.0, bal - scheduled - prepay)\n'
            '        interest_total += interest\n'
            '        principal_total += scheduled + prepay\n'
            '        if m % 6 == 0 or m == 1:\n'
            '            schedule.append({"month": m, "balance_mm": round(bal, 3),\n'
            '                              "interest_mm": round(interest, 3),\n'
            '                              "principal_mm": round(scheduled + prepay, 3)})\n'
            '    return {\n'
            '        "horizon_months": horizon_months,\n'
            '        "shock_bps": shock_bps,\n'
            '        "ending_balance_mm": round(bal, 3),\n'
            '        "total_interest_mm": round(interest_total, 3),\n'
            '        "total_principal_mm": round(principal_total, 3),\n'
            '        "wal_estimate_years": round(horizon_months / 24.0, 2),\n'
            '        "snapshot": schedule,\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="select_allocation_scenario",
        description="Pick one allocation scenario (conservative/moderate/aggressive) by id from a generated list and confirm the choice.",
        parameters=[
            {"name": "scenarios", "type": "array",
             "description": "Output of generate_allocation_scenarios — list of scenario dicts.",
             "required": True},
            {"name": "scenario_id", "type": "string",
             "description": "One of 'Conservative' | 'Moderate' | 'Aggressive' (case-insensitive).",
             "required": True},
        ],
        python_source=(
            'def select_allocation_scenario(scenarios: list, scenario_id: str):\n'
            '    """Returns the picked scenario dict, or {"error": ...} if not found."""\n'
            '    sid = (scenario_id or "").strip().lower()\n'
            '    for s in scenarios:\n'
            '        if str(s.get("name", "")).lower() == sid:\n'
            '            return {"status": "selected", "scenario": s}\n'
            '    return {"error": f"Scenario {scenario_id!r} not found", "available": [s.get("name") for s in scenarios]}\n'
        ),
    )

    ctx.register_python_tool(
        name="get_portfolio_summary_tool",
        description="Aggregate portfolio metrics: NAV, balance-weighted OAS, OAD, convexity, book yield, and per-product breakdown.",
        parameters=[
            {"name": "positions", "type": "array",
             "description": "List of {product_type, balance_mm, oas_bps, duration, convexity, book_yield} dicts.",
             "required": True},
        ],
        python_source=(
            'def get_portfolio_summary_tool(positions: list):\n'
            '    """Returns NAV-weighted aggregates + by_product_type stats."""\n'
            '    if not positions: return {"error": "no positions"}\n'
            '    def w(field):\n'
            '        num = sum(float(p.get(field, 0)) * float(p.get("balance_mm", 0)) for p in positions)\n'
            '        den = sum(float(p.get("balance_mm", 0)) for p in positions) or 1.0\n'
            '        return num / den\n'
            '    nav = sum(float(p.get("balance_mm", 0)) for p in positions)\n'
            '    by_type = {}\n'
            '    for p in positions:\n'
            '        t = p.get("product_type", "UNKNOWN")\n'
            '        b = float(p.get("balance_mm", 0))\n'
            '        d = by_type.setdefault(t, {"total_balance_mm": 0.0, "_oas_w": 0.0, "_dur_w": 0.0})\n'
            '        d["total_balance_mm"] += b\n'
            '        d["_oas_w"] += float(p.get("oas_bps", 0)) * b\n'
            '        d["_dur_w"] += float(p.get("duration", 0)) * b\n'
            '    for t, d in by_type.items():\n'
            '        b = d["total_balance_mm"] or 1.0\n'
            '        d["avg_oas_bps"] = round(d.pop("_oas_w") / b, 2)\n'
            '        d["avg_duration"] = round(d.pop("_dur_w") / b, 3)\n'
            '        d["total_balance_mm"] = round(d["total_balance_mm"], 2)\n'
            '    return {\n'
            '        "nav_mm": round(nav, 2),\n'
            '        "weighted_oas_bps": round(w("oas_bps"), 2),\n'
            '        "weighted_oad": round(w("duration"), 3),\n'
            '        "weighted_convexity": round(w("convexity"), 3),\n'
            '        "weighted_book_yield_pct": round(w("book_yield"), 3),\n'
            '        "by_product_type": by_type,\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="get_portfolio_positions_tool",
        description="Return all portfolio positions with per-pool detail (cusip, pool_id, balance, OAS, duration, convexity, book yield).",
        parameters=[
            {"name": "positions", "type": "array", "description": "Raw positions list — passed through with light normalization.", "required": True},
            {"name": "limit", "type": "integer", "description": "Max rows to return (default 200).", "required": False},
        ],
        python_source=(
            'def get_portfolio_positions_tool(positions: list, limit: int = 200):\n'
            '    """Pass-through with sort by balance_mm desc + truncation."""\n'
            '    sorted_p = sorted(positions, key=lambda p: float(p.get("balance_mm", 0)), reverse=True)\n'
            '    return {"n_positions": len(sorted_p), "positions": sorted_p[:limit]}\n'
        ),
    )

    ctx.register_python_tool(
        name="get_universe_summary_tool",
        description="Summary of the pool universe — count by product type, OAS distribution, coupon range, average WALA.",
        parameters=[
            {"name": "universe", "type": "array",
             "description": "List of pool dicts with at least {product_type, coupon, oas_bps, wala}.",
             "required": True},
        ],
        python_source=(
            'def get_universe_summary_tool(universe: list):\n'
            '    """Aggregate stats by product_type and overall."""\n'
            '    if not universe: return {"error": "empty universe"}\n'
            '    by_type = {}\n'
            '    for p in universe:\n'
            '        t = p.get("product_type", "UNKNOWN")\n'
            '        d = by_type.setdefault(t, {"count": 0, "_coupon": [], "_oas": [], "_wala": []})\n'
            '        d["count"] += 1\n'
            '        d["_coupon"].append(float(p.get("coupon", 0)))\n'
            '        d["_oas"].append(float(p.get("oas_bps", 0)))\n'
            '        d["_wala"].append(float(p.get("wala", 0)))\n'
            '    out = {}\n'
            '    for t, d in by_type.items():\n'
            '        cs = d.pop("_coupon"); os = d.pop("_oas"); ws = d.pop("_wala")\n'
            '        out[t] = {\n'
            '            "count": d["count"],\n'
            '            "coupon_min": round(min(cs), 3), "coupon_max": round(max(cs), 3),\n'
            '            "avg_coupon": round(sum(cs) / len(cs), 3),\n'
            '            "avg_oas_bps": round(sum(os) / len(os), 2),\n'
            '            "avg_wala_months": round(sum(ws) / len(ws), 1),\n'
            '        }\n'
            '    return {"universe_size": len(universe), "by_product_type": out}\n'
        ),
    )

    ctx.register_python_tool(
        name="summarise_pool_universe",
        description="Concise stats for a pool universe — count, coupon range, average OAS, WALA. Lighter alternative to get_universe_summary_tool.",
        parameters=[
            {"name": "universe", "type": "array", "description": "List of pool dicts.", "required": True},
        ],
        python_source=(
            'def summarise_pool_universe(universe: list):\n'
            '    """Single-row summary (no by-type)."""\n'
            '    if not universe: return {"error": "empty universe"}\n'
            '    cs = [float(p.get("coupon", 0)) for p in universe]\n'
            '    os = [float(p.get("oas_bps", 0)) for p in universe]\n'
            '    ws = [float(p.get("wala", 0)) for p in universe]\n'
            '    return {\n'
            '        "count": len(universe),\n'
            '        "coupon_min": round(min(cs), 3), "coupon_max": round(max(cs), 3),\n'
            '        "avg_coupon": round(sum(cs)/len(cs), 3),\n'
            '        "avg_oas_bps": round(sum(os)/len(os), 2),\n'
            '        "avg_wala_months": round(sum(ws)/len(ws), 1),\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="compute_volume_timing_analysis",
        description="Bucket new-volume schedule into periods (default 0-12, 13-24, 25-36 months) with totals and monthly averages.",
        parameters=[
            {"name": "schedule", "type": "array",
             "description": "Output of compute_new_volume_schedule.schedule — list of {date, new_volume_mm}.",
             "required": True},
            {"name": "horizon_months", "type": "integer", "description": "How far forward to analyse.", "required": False},
        ],
        python_source=(
            'def compute_volume_timing_analysis(schedule: list, horizon_months: int = 36):\n'
            '    """Returns {horizon_months, buckets: {label: {total_mm, avg_monthly_mm, months}}}."""\n'
            '    if not schedule: return {"error": "schedule empty"}\n'
            '    horizon_months = min(horizon_months, len(schedule))\n'
            '    buckets = {}\n'
            '    for i, v in enumerate(schedule[:horizon_months]):\n'
            '        label = f"Months {(i//12)*12 + 1}-{(i//12 + 1)*12}"\n'
            '        b = buckets.setdefault(label, {"total_mm": 0.0, "months": []})\n'
            '        b["total_mm"] = round(b["total_mm"] + float(v.get("new_volume_mm", 0)), 2)\n'
            '        b["months"].append({"date": v.get("date"), "new_volume_mm": v.get("new_volume_mm")})\n'
            '    for b in buckets.values():\n'
            '        n = len(b["months"]) or 1\n'
            '        b["avg_monthly_mm"] = round(b["total_mm"] / n, 2)\n'
            '    return {"horizon_months": horizon_months, "buckets": buckets}\n'
        ),
    )

    ctx.register_python_tool(
        name="forecast_pool_prepayment_tool",
        description="Forecast lifetime CPR for a pool across rate shocks (-200, -100, 0, +100, +200 bps).",
        parameters=[
            {"name": "coupon", "type": "number", "description": "Pool coupon (e.g. 5.5).", "required": True},
            {"name": "wala", "type": "integer", "description": "Weighted average loan age in months.", "required": True},
            {"name": "current_mortgage_rate", "type": "number", "description": "Current 30Y mortgage rate (e.g. 6.8).", "required": False},
        ],
        python_source=(
            'def forecast_pool_prepayment_tool(coupon: float, wala: int, current_mortgage_rate: float = 6.8):\n'
            '    """Toy CPR model — sensitive to refi incentive (current_rate - coupon)."""\n'
            '    out = {}\n'
            '    for shock in (-200, -100, 0, 100, 200):\n'
            '        new_rate = current_mortgage_rate + shock / 100.0\n'
            '        incentive = max(0.0, coupon - new_rate)\n'
            '        burnout = max(0.5, 1.0 - wala / 360.0)\n'
            '        cpr = round(min(45.0, 4.0 + 6.0 * incentive * burnout), 2)\n'
            '        out[f"shock_{shock:+d}bps"] = {"new_30y_rate": round(new_rate, 3), "lifetime_cpr_pct": cpr}\n'
            '    return out\n'
        ),
    )

    ctx.register_python_tool(
        name="run_pool_scenario_tool",
        description="Run a single rate shock on a pool — returns price, OAS, duration, convexity, projected CPR after the shock.",
        parameters=[
            {"name": "coupon", "type": "number", "description": "Pool coupon.", "required": True},
            {"name": "wala", "type": "integer", "description": "WALA (months).", "required": True},
            {"name": "shock_bps", "type": "integer", "description": "Parallel rate shock in bps.", "required": True},
            {"name": "base_oas_bps", "type": "number", "description": "Base OAS for the pool.", "required": False},
        ],
        python_source=(
            'def run_pool_scenario_tool(coupon: float, wala: int, shock_bps: int, base_oas_bps: float = 35.0):\n'
            '    """Toy single-shock evaluator."""\n'
            '    dur = max(1.5, 5.5 - 0.0006 * shock_bps)\n'
            '    cvx = round(0.6 - 0.0002 * abs(shock_bps), 3)\n'
            '    px = round(100.0 - dur * (shock_bps / 100.0) + 0.5 * cvx * (shock_bps / 100.0) ** 2, 3)\n'
            '    new_oas = round(base_oas_bps + 0.05 * shock_bps, 2)\n'
            '    incentive = max(0.0, coupon - (6.8 + shock_bps / 100.0))\n'
            '    cpr = round(min(45.0, 4.0 + 6.0 * incentive * max(0.5, 1.0 - wala / 360.0)), 2)\n'
            '    return {\n'
            '        "shock_bps": shock_bps,\n'
            '        "price_pct": px,\n'
            '        "duration": round(dur, 3),\n'
            '        "convexity": cvx,\n'
            '        "oas_bps": new_oas,\n'
            '        "projected_cpr_pct": cpr,\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="compute_portfolio_impact_tool",
        description="Simulate adding new pools to a portfolio — returns blended OAS, OAD, convexity, NAV before/after, and key deltas.",
        parameters=[
            {"name": "current_summary", "type": "object",
             "description": "Output of get_portfolio_summary_tool — must include nav_mm, weighted_oas_bps, weighted_oad, weighted_convexity.",
             "required": True},
            {"name": "additions", "type": "array",
             "description": "List of {balance_mm, oas_bps, duration, convexity} for the pools to add.",
             "required": True},
        ],
        python_source=(
            'def compute_portfolio_impact_tool(current_summary: dict, additions: list):\n'
            '    """Blend the additions into the existing portfolio + report deltas."""\n'
            '    if not additions: return {"error": "no additions"}\n'
            '    nav0 = float(current_summary.get("nav_mm", 0))\n'
            '    add_nav = sum(float(a.get("balance_mm", 0)) for a in additions)\n'
            '    nav1 = nav0 + add_nav\n'
            '    def blend(field, current_key):\n'
            '        c = float(current_summary.get(current_key, 0))\n'
            '        num = c * nav0 + sum(float(a.get(field, 0)) * float(a.get("balance_mm", 0)) for a in additions)\n'
            '        return num / nav1 if nav1 else 0\n'
            '    return {\n'
            '        "nav_before_mm": round(nav0, 2),\n'
            '        "nav_after_mm": round(nav1, 2),\n'
            '        "additions_mm": round(add_nav, 2),\n'
            '        "oas_before_bps": round(float(current_summary.get("weighted_oas_bps", 0)), 2),\n'
            '        "oas_after_bps": round(blend("oas_bps", "weighted_oas_bps"), 2),\n'
            '        "oad_before": round(float(current_summary.get("weighted_oad", 0)), 3),\n'
            '        "oad_after": round(blend("duration", "weighted_oad"), 3),\n'
            '        "convexity_before": round(float(current_summary.get("weighted_convexity", 0)), 3),\n'
            '        "convexity_after": round(blend("convexity", "weighted_convexity"), 3),\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="get_risk_constraints_summary",
        description="Return the constraints envelope previously computed by assess_portfolio_risk (duration min/max, liquidity floor, max CMBS / ARM).",
        parameters=[
            {"name": "risk_assessment", "type": "object", "description": "Output of assess_portfolio_risk.", "required": True},
        ],
        python_source=(
            'def get_risk_constraints_summary(risk_assessment: dict):\n'
            '    """Pulls risk_constraints + flags + headline duration/liquidity."""\n'
            '    rc = risk_assessment.get("risk_constraints") or {}\n'
            '    cp = risk_assessment.get("current_portfolio") or {}\n'
            '    return {\n'
            '        "duration_min": rc.get("duration_min"),\n'
            '        "duration_max": rc.get("duration_max"),\n'
            '        "current_duration": cp.get("duration_years"),\n'
            '        "liquidity_score_min": rc.get("liquidity_score_min"),\n'
            '        "current_liquidity_score": cp.get("liquidity_score"),\n'
            '        "max_cmbs_pct": rc.get("max_cmbs_pct"),\n'
            '        "max_arm_pct": rc.get("max_arm_pct"),\n'
            '        "flags": risk_assessment.get("flags", []),\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="get_market_data_tool",
        description="Return current market snapshot — SOFR curve, Treasury curve, mortgage current-coupon, cohort OAS levels.",
        parameters=[],
        python_source=(
            'def get_market_data_tool():\n'
            '    """Canned snapshot — replace with a real market data feed."""\n'
            '    return {\n'
            '        "as_of": "EOD prior business day",\n'
            '        "sofr_curve": {"1M": 4.30, "3M": 4.32, "6M": 4.28, "1Y": 4.10, "2Y": 3.95, "5Y": 3.85, "10Y": 4.05},\n'
            '        "ust_curve":  {"3M": 4.50, "2Y": 4.10, "5Y": 4.05, "10Y": 4.20, "30Y": 4.45},\n'
            '        "mortgage_current_coupon_pct": 6.80,\n'
            '        "cohort_oas_bps": {\n'
            '            "FNMA_30Y_5.5": 38, "FNMA_30Y_6.0": 32, "FNMA_30Y_6.5": 28,\n'
            '            "GNMA_30Y_5.5": 30, "GNMA_30Y_6.0": 26,\n'
            '            "FNMA_15Y_5.0": 22, "FNMA_15Y_5.5": 20,\n'
            '            "CMBS_AAA_10Y": 95, "CMBS_AA_10Y": 145,\n'
            '        },\n'
            '    }\n'
        ),
    )

    ctx.register_python_tool(
        name="get_cohort_oas_tool",
        description="Look up the cohort OAS benchmark for a specific (product_type, coupon_bucket).",
        parameters=[
            {"name": "product_type", "type": "string",
             "description": "FNMA_30Y | GNMA_30Y | FNMA_15Y | CMBS_AAA | CMBS_AA | …", "required": True},
            {"name": "coupon_bucket", "type": "string", "description": "e.g. '5.5', '6.0', '10Y'.", "required": True},
        ],
        python_source=(
            'def get_cohort_oas_tool(product_type: str, coupon_bucket: str):\n'
            '    """Returns {"cohort": str, "oas_bps": int} or {"error": ...}."""\n'
            '    table = {\n'
            '        "FNMA_30Y_5.5": 38, "FNMA_30Y_6.0": 32, "FNMA_30Y_6.5": 28,\n'
            '        "GNMA_30Y_5.5": 30, "GNMA_30Y_6.0": 26,\n'
            '        "FNMA_15Y_5.0": 22, "FNMA_15Y_5.5": 20,\n'
            '        "CMBS_AAA_10Y": 95, "CMBS_AA_10Y": 145,\n'
            '    }\n'
            '    key = f"{product_type}_{coupon_bucket}"\n'
            '    if key not in table:\n'
            '        return {"error": f"No cohort OAS for {key!r}", "available": sorted(table.keys())}\n'
            '    return {"cohort": key, "oas_bps": table[key]}\n'
        ),
    )
