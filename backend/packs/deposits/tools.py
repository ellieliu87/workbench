"""Deposit pack — Python tools for the CCAR variance-attribution playbook
plus the chat-panel deposit-expert / model-challenger flow.

  - compute_variance_walk         — variance-analyst: Pandas
                                    Rate / Volume / Mix decomposition
                                    over the CCAR retail PPNR CSV.
  - verify_numbers_in_narrative   — accuracy-reviewer: extracts dollar
                                    figures from prose, confirms each
                                    ties to a row in the variance JSON.
  - audit_logic_rules             — model-challenger: runs a registered
                                    set of SR 11-7-style red-flag
                                    patterns against a claim/narrative.
  - get_model_assumptions         — methodology-researcher /
                                    model-challenger: returns the
                                    documented per-product assumption
                                    block (PSAV beta, CD attrition
                                    floor, recapture rate, marketing
                                    pullback path).
  - compute_sensitivity_walk      — variance-analyst (sensitivity
                                    branch): perturbs a parameter and
                                    recomputes Interest_Expense_mm.

The methodology-researcher uses the universal built-in `rag_search`
against `sample_docs/retail_deposit/`.

Each tool is a self-contained Python source string registered through
`PackContext.register_python_tool` so it lands in the universal tool
registry with `source='pack'` + `pack_id='deposits'`.
"""
from __future__ import annotations

from packs import PackContext


def register_python_tools(ctx: PackContext) -> None:
    # ── Agent 1 — variance walk ──────────────────────────────────────────
    ctx.register_python_tool(
        name="compute_variance_walk",
        description=(
            "Decompose the dollar variance between two scenarios on a "
            "given metric (e.g. Interest_Expense_mm) into Rate / Volume / "
            "Mix components, summed across all (Portfolio, Product_L1) "
            "pairs and broken down per pair."
        ),
        parameters=[
            {"name": "current_scenario",   "type": "string",
             "description": "Scenario name to evaluate (e.g. 'CCAR_26_BHC_Stress').",
             "required": True},
            {"name": "benchmark_scenario", "type": "string",
             "description": "Scenario to compare against (e.g. 'CCAR_25_BHC_Stress').",
             "required": True},
            {"name": "metric",             "type": "string",
             "description": "Metric to attribute (default: 'Interest_Expense_mm').",
             "required": False},
            {"name": "playbook_id",        "type": "string",
             "description": (
                 "Playbook id (read from `[Context]`, line `playbook_id: …`). "
                 "When supplied, the tool auto-discovers the variance CSV by "
                 "scanning the analyst-uploaded files for this playbook and "
                 "picking the one whose schema + scenarios match. "
                 "**Preferred** way to point the tool at uploaded data — no "
                 "manual path construction needed."
             ),
             "required": False},
            {"name": "csv_path",           "type": "string",
             "description": (
                 "Explicit path to a CSV with columns (Scenario, Quarter_ID, "
                 "Portfolio, Product_L1, Metric, Value). Use this only when "
                 "the analyst named a file outside the playbook uploads. "
                 "Falls back to the function's bundled retail PPNR sample "
                 "when both `playbook_id` and `csv_path` are omitted."
             ),
             "required": False},
        ],
        python_source=(
            'def compute_variance_walk(current_scenario, benchmark_scenario,\n'
            '                           metric="Interest_Expense_mm",\n'
            '                           playbook_id=None, csv_path=None):\n'
            '    """Rate/Volume/Mix decomposition of a metric between two scenarios."""\n'
            '    import os, json, glob\n'
            '    import pandas as pd\n'
            '\n'
            '    def _find_repo_root():\n'
            '        """Walk up from cwd looking for the `sample_data` folder. Avoids\n'
            '        relying on __file__ (this source is exec\'d in subprocesses where\n'
            '        __file__ may not be defined)."""\n'
            '        here = os.path.abspath(os.getcwd())\n'
            '        for _ in range(6):\n'
            '            if os.path.isdir(os.path.join(here, "sample_data")):\n'
            '                return here\n'
            '            parent = os.path.dirname(here)\n'
            '            if parent == here:\n'
            '                break\n'
            '            here = parent\n'
            '        return os.path.abspath(os.getcwd())\n'
            '\n'
            '    def _docs_root():\n'
            '        env_root = (os.environ.get("CMA_DOCS_ROOT") or "").strip()\n'
            '        if env_root:\n'
            '            return os.path.join(env_root, "uploads") if not env_root.rstrip("/\\\\").endswith("uploads") else env_root\n'
            '        return os.path.join(_find_repo_root(), "sample_docs", "uploads")\n'
            '\n'
            '    NEEDED = {"Scenario", "Quarter_ID", "Portfolio", "Product_L1", "Metric", "Value"}\n'
            '\n'
            '    # Auto-discover from the playbook upload folder when the agent\n'
            '    # passes `playbook_id` instead of a path. We scan every .csv /\n'
            '    # .xlsx / .parquet in the folder, score by schema + scenario\n'
            '    # match, and pick the best one. This is the recommended path\n'
            '    # — it spares the agent from constructing or escaping paths.\n'
            '    if not csv_path and playbook_id:\n'
            '        scope = os.path.join(_docs_root(), "playbook", playbook_id)\n'
            '        if not os.path.isdir(scope):\n'
            '            return {\n'
            '                "error":      "no upload folder for this playbook",\n'
            '                "scope":      scope,\n'
            '                "hint":       ("The analyst hasn\'t uploaded any files to this "\n'
            '                                "playbook yet. Either omit `playbook_id` (uses "\n'
            '                                "the bundled sample) or ask them to attach a CSV."),\n'
            '            }\n'
            '        candidates = []\n'
            '        for ext in ("*.csv", "*.xlsx", "*.xls", "*.parquet"):\n'
            '            for p in sorted(glob.glob(os.path.join(scope, ext))):\n'
            '                try:\n'
            '                    e = os.path.splitext(p)[1].lower()\n'
            '                    if e == ".csv":\n'
            '                        peek = pd.read_csv(p, nrows=200)\n'
            '                    elif e in (".xlsx", ".xls"):\n'
            '                        peek = pd.read_excel(p, nrows=200)\n'
            '                    else:\n'
            '                        peek = pd.read_parquet(p)\n'
            '                except Exception as ex:\n'
            '                    candidates.append({"path": p, "score": -1,\n'
            '                                        "reason": f"read failed: {ex}"})\n'
            '                    continue\n'
            '                cols = set(peek.columns)\n'
            '                missing = NEEDED - cols\n'
            '                if missing:\n'
            '                    candidates.append({"path": p, "score": 0,\n'
            '                                        "reason": f"missing cols: {sorted(missing)}"})\n'
            '                    continue\n'
            '                scenarios = set(peek["Scenario"].astype(str).unique())\n'
            '                hits = (1 if current_scenario in scenarios else 0) \\\n'
            '                     + (1 if benchmark_scenario in scenarios else 0)\n'
            '                # 1 point per scenario hit; bonus for both — that\'s\n'
            '                # the file we want. Schema-match alone scores 1.\n'
            '                candidates.append({"path": p, "score": 1 + hits,\n'
            '                                    "scenarios_in_file": sorted(scenarios)[:8],\n'
            '                                    "reason": "ok"})\n'
            '        ok = [c for c in candidates if c["score"] >= 1]\n'
            '        if not ok:\n'
            '            return {\n'
            '                "error":          "no usable CSV in playbook uploads",\n'
            '                "scope":          scope,\n'
            '                "files_checked":  candidates,\n'
            '                "needed_columns": sorted(NEEDED),\n'
            '                "hint":           ("None of the uploaded files match the variance "\n'
            '                                    "schema. Ask the analyst to upload a long-format "\n'
            '                                    "CSV with the columns above."),\n'
            '            }\n'
            '        ok.sort(key=lambda c: -c["score"])\n'
            '        csv_path = ok[0]["path"]\n'
            '\n'
            '    if not csv_path:\n'
            '        repo = _find_repo_root()\n'
            '        csv_path = os.path.join(repo, "sample_data", "ccar", "CCAR_Retail_Outputs.csv")\n'
            '    else:\n'
            '        # Resolve relative paths against the Knowledge Base / playbook\n'
            '        # uploads root so the agent can pass `playbook/<id>/file.csv`\n'
            '        # without having to escape Windows backslashes in tool args.\n'
            '        if not os.path.isabs(csv_path):\n'
            '            cand = os.path.join(_docs_root(), csv_path)\n'
            '            if os.path.exists(cand):\n'
            '                csv_path = cand\n'
            '        if not os.path.exists(csv_path):\n'
            '            return {\n'
            '                "error":     "csv file not found",\n'
            '                "csv_path":  csv_path,\n'
            '                "hint":      ("Pass either an absolute path or a path relative to "\n'
            '                              "the docs root (e.g. `playbook/<id>/file.csv`)."),\n'
            '            }\n'
            '\n'
            '    df = pd.read_csv(csv_path)\n'
            '    needed = {"Scenario", "Quarter_ID", "Portfolio", "Product_L1", "Metric", "Value"}\n'
            '    actual = set(df.columns)\n'
            '    missing = needed - actual\n'
            '    if missing:\n'
            '        return {\n'
            '            "error":           "csv missing required columns",\n'
            '            "missing_columns": sorted(missing),\n'
            '            "actual_columns":  sorted(actual),\n'
            '            "csv_path":        csv_path,\n'
            '            "hint":            ("Expected long-format CSV with one row per (Scenario, "\n'
            '                                "Quarter_ID, Portfolio, Product_L1, Metric, Value)."),\n'
            '        }\n'
            '\n'
            '    metrics_in_csv = sorted(df["Metric"].unique().tolist())\n'
            '    pivot = df[df["Metric"].isin(["Average_Balance_mm", "Rate_Paid_APR", metric])]\n'
            '    wide = pivot.pivot_table(\n'
            '        index=["Scenario", "Quarter_ID", "Portfolio", "Product_L1"],\n'
            '        columns="Metric", values="Value", aggfunc="first",\n'
            '    ).reset_index()\n'
            '\n'
            '    cur = wide[wide["Scenario"] == current_scenario]\n'
            '    ben = wide[wide["Scenario"] == benchmark_scenario]\n'
            '    if cur.empty or ben.empty:\n'
            '        return {\n'
            '            "error":              "scenario(s) not found in csv",\n'
            '            "current_scenario":   current_scenario,\n'
            '            "benchmark_scenario": benchmark_scenario,\n'
            '            "current_found":      not cur.empty,\n'
            '            "benchmark_found":    not ben.empty,\n'
            '            "available_scenarios": sorted(df["Scenario"].unique().tolist()),\n'
            '            "csv_path":           csv_path,\n'
            '        }\n'
            '    if metric not in metrics_in_csv:\n'
            '        return {\n'
            '            "error":             f"metric `{metric}` not in csv",\n'
            '            "available_metrics": metrics_in_csv,\n'
            '            "csv_path":          csv_path,\n'
            '        }\n'
            '\n'
            '    join_keys = ["Quarter_ID", "Portfolio", "Product_L1"]\n'
            '    m = cur.merge(ben, on=join_keys, how="outer", suffixes=("_cur", "_ben"))\n'
            '    m = m.fillna(0.0)\n'
            '\n'
            '    # Total dollar variance (cur - ben) for the metric.\n'
            '    total_var = (m[f"{metric}_cur"] - m[f"{metric}_ben"]).sum()\n'
            '\n'
            '    # Rate/Volume/Mix decomp using the standard CCAR walk:\n'
            '    #   rate   = (rate_cur - rate_ben) * vol_ben * 0.0025  (qtr quarter-share)\n'
            '    #   volume = (vol_cur - vol_ben)   * rate_ben          * 0.0025\n'
            '    #   mix    = (rate_cur - rate_ben) * (vol_cur - vol_ben) * 0.0025\n'
            '    rate_d = m["Rate_Paid_APR_cur"]      - m["Rate_Paid_APR_ben"]\n'
            '    vol_d  = m["Average_Balance_mm_cur"] - m["Average_Balance_mm_ben"]\n'
            '    rate_eff = (rate_d / 100.0) * m["Average_Balance_mm_ben"] * 0.25\n'
            '    vol_eff  = vol_d * (m["Rate_Paid_APR_ben"] / 100.0) * 0.25\n'
            '    mix_eff  = (rate_d / 100.0) * vol_d * 0.25\n'
            '    if metric == "NII_mm":\n'
            '        # NII rises when rate paid falls — flip sign on rate / mix effects.\n'
            '        rate_eff, mix_eff = -rate_eff, -mix_eff\n'
            '\n'
            '    # Starting-point variance: PQ0 delta carried as the persistent base.\n'
            '    pq0 = m[m["Quarter_ID"] == "PQ0"]\n'
            '    starting_pt = float((pq0[f"{metric}_cur"] - pq0[f"{metric}_ben"]).sum() * 9)\n'
            '\n'
            '    by_product = (\n'
            '        m.assign(\n'
            '            total_var=m[f"{metric}_cur"] - m[f"{metric}_ben"],\n'
            '            rate_eff=rate_eff, vol_eff=vol_eff, mix_eff=mix_eff,\n'
            '        )\n'
            '        .groupby(["Portfolio", "Product_L1"], dropna=False)\n'
            '        .agg(total_var=("total_var", "sum"),\n'
            '             rate_effect_mm=("rate_eff", "sum"),\n'
            '             volume_effect_mm=("vol_eff", "sum"),\n'
            '             mix_effect_mm=("mix_eff", "sum"))\n'
            '        .reset_index()\n'
            '    )\n'
            '    by_product_rows = [\n'
            '        {"portfolio": r["Portfolio"], "product": r["Product_L1"],\n'
            '         "total_variance_mm": round(float(r["total_var"]), 2),\n'
            '         "rate_effect_mm":    round(float(r["rate_effect_mm"]), 2),\n'
            '         "volume_effect_mm":  round(float(r["volume_effect_mm"]), 2),\n'
            '         "mix_effect_mm":     round(float(r["mix_effect_mm"]), 2)}\n'
            '        for _, r in by_product.iterrows()\n'
            '    ]\n'
            '    by_product_rows.sort(key=lambda r: -abs(r["total_variance_mm"]))\n'
            '\n'
            '    return {\n'
            '        "current_scenario":           current_scenario,\n'
            '        "benchmark_scenario":         benchmark_scenario,\n'
            '        "metric":                     metric,\n'
            '        "csv_path_used":              csv_path,\n'
            '        "playbook_id":                playbook_id,\n'
            '        "total_variance_mm":          round(float(total_var), 2),\n'
            '        "starting_point_variance_mm": round(starting_pt, 2),\n'
            '        "scenario_change_mm":         round(float(total_var) - starting_pt, 2),\n'
            '        "rate_effect_mm":             round(float(rate_eff.sum()), 2),\n'
            '        "volume_effect_mm":           round(float(vol_eff.sum()),  2),\n'
            '        "mix_effect_mm":              round(float(mix_eff.sum()),  2),\n'
            '        "by_product":                 by_product_rows,\n'
            '    }\n'
        ),
    )

    # ── Agent 4 — fact-checker ────────────────────────────────────────────
    ctx.register_python_tool(
        name="verify_numbers_in_narrative",
        description=(
            "Extract dollar figures from Agent 3's narrative text and "
            "verify each against Agent 1's variance JSON. Returns one row "
            "per claimed number with whether it ties (within tolerance)."
        ),
        parameters=[
            {"name": "narrative",       "type": "string",
             "description": "Full narrative text from Agent 3 (slide_header + drivers + overlays concatenated).",
             "required": True},
            {"name": "variance_json",   "type": "object",
             "description": "Agent 1's variance walk output (dict).",
             "required": True},
            {"name": "tolerance_pct",   "type": "number",
             "description": "Tolerance for matching numbers (default 0.10 = 10%).",
             "required": False},
        ],
        python_source=(
            'def verify_numbers_in_narrative(narrative, variance_json, tolerance_pct=0.10):\n'
            '    """Heuristic fact-checker: pull every $X.XB / $X.XMM figure from prose,\n'
            '    flag if absent from the variance JSON values."""\n'
            '    import re\n'
            '\n'
            '    # Collect known values (in $MM) from the variance JSON.\n'
            '    known_mm = set()\n'
            '    def add(val):\n'
            '        try:\n'
            '            v = float(val)\n'
            '            if abs(v) > 0.001:\n'
            '                known_mm.add(round(v, 2))\n'
            '        except Exception:\n'
            '            pass\n'
            '    for k in ("total_variance_mm", "starting_point_variance_mm",\n'
            '             "scenario_change_mm", "rate_effect_mm", "volume_effect_mm",\n'
            '             "mix_effect_mm"):\n'
            '        add(variance_json.get(k))\n'
            '    for row in (variance_json.get("by_product") or []):\n'
            '        for k in ("total_variance_mm", "rate_effect_mm",\n'
            '                  "volume_effect_mm", "mix_effect_mm"):\n'
            '            add(row.get(k))\n'
            '\n'
            '    # Extract $X.XB or $X.XMM tokens from the narrative.\n'
            '    pat = re.compile(r"\\$\\s*([+-]?[0-9]+(?:\\.[0-9]+)?)\\s*(B|MM|M)\\b", re.IGNORECASE)\n'
            '    checks = []\n'
            '    for m in pat.finditer(narrative):\n'
            '        amount = float(m.group(1))\n'
            '        unit = m.group(2).upper()\n'
            '        as_mm = amount * 1000.0 if unit == "B" else amount\n'
            '        # Tolerance bands\n'
            '        tol = max(abs(as_mm) * float(tolerance_pct), 0.01)\n'
            '        match = next((kv for kv in known_mm if abs(kv - as_mm) <= tol\n'
            '                       or abs(kv + as_mm) <= tol), None)\n'
            '        checks.append({\n'
            '            "claim":            m.group(0),\n'
            '            "claimed_mm":       round(as_mm, 2),\n'
            '            "tolerance_passed": match is not None,\n'
            '            "matched_value_mm": match,\n'
            '        })\n'
            '\n'
            '    all_pass = all(c["tolerance_passed"] for c in checks) if checks else True\n'
            '    return {\n'
            '        "all_numbers_tie":  all_pass,\n'
            '        "checks":           checks,\n'
            '        "known_values_mm":  sorted(known_mm),\n'
            '    }\n'
        ),
    )

    # ── Challenger — SR 11-7 red-flag patterns ────────────────────────────
    ctx.register_python_tool(
        name="audit_logic_rules",
        description=(
            "Run the registered SR 11-7-style red-flag checklist against a "
            "claim or narrative. Returns each rule with a `tripped` flag, "
            "a `severity`, and the `regulator_question` a reviewer would "
            "ask. Used by the model-challenger skill to find logical gaps "
            "(marketing → 0 but flat NABs, rate ↑ but beta ≈ 0, overlay "
            "without re-cal plan, etc.)."
        ),
        parameters=[
            {"name": "narrative", "type": "string",
             "description": "The claim or drafted narrative to audit.",
             "required": True},
            {"name": "context",   "type": "object",
             "description": "Optional structured signals — e.g. variance JSON, model assumption block, scenario tag — that lets some rules check more precisely.",
             "required": False},
        ],
        python_source=(
            'def audit_logic_rules(narrative, context=None):\n'
            '    """Heuristic SR 11-7 red-flag scan over a claim / narrative."""\n'
            '    import re\n'
            '\n'
            '    text = (narrative or "").lower()\n'
            '    ctx_d = context or {}\n'
            '\n'
            '    rules = [\n'
            '        {\n'
            '            "id": "marketing_to_zero_but_flat_nabs",\n'
            '            "label": "Marketing → 0 but new accounts unchanged",\n'
            '            "severity": "high",\n'
            '            "trigger": (\n'
            '                ("marketing" in text and ("zero" in text or "$0" in text or "to 0" in text))\n'
            '                and ("flat" in text or "unchanged" in text or "consistent" in text\n'
            '                     or "interchange" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "If marketing drops to $0, what empirical elasticity links marketing "\n'
            '                "spend to new-account inflows? The narrative implies NABs are macro-driven only."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.4 — Implementation, Use, Validation",\n'
            '        },\n'
            '        {\n'
            '            "id": "rate_up_beta_zero",\n'
            '            "label": "Rate ↑ but deposit beta ≈ 0",\n'
            '            "severity": "high",\n'
            '            "trigger": (\n'
            '                ("rate" in text and ("higher" in text or "increase" in text or "rising" in text))\n'
            '                and ("beta" in text and ("zero" in text or "0.0" in text or "no pass-through" in text))\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "Deposit pricing should track at non-zero beta in a rising-rate regime. "\n'
            '                "Is there a documented beta floor? What did 2022-2023 imply empirically?"\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.3 — Model Development, Implementation",\n'
            '        },\n'
            '        {\n'
            '            "id": "non_macro_model_in_stress",\n'
            '            "label": "Non-macro-sensitive model used in stress scenario",\n'
            '            "severity": "medium",\n'
            '            "trigger": (\n'
            '                ("non-macro" in text or "no macro" in text or "macro-insensitive" in text\n'
            '                 or "checking aof" in text)\n'
            '                and ("stress" in text or "ccar" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "If the model has no macro features, on what basis is its stress-period "\n'
            '                "behavior validated? Backtesting against 2008/2020 should be required."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.5 — Outcomes Analysis (Backtesting)",\n'
            '        },\n'
            '        {\n'
            '            "id": "overlay_without_recal_plan",\n'
            '            "label": "Overlay applied without re-calibration plan",\n'
            '            "severity": "high",\n'
            '            "trigger": (\n'
            '                ("overlay" in text)\n'
            '                and not ("re-calibrat" in text or "recal" in text or "permanent" in text\n'
            '                         or "retire" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "What is the timeline to re-calibrate the underlying model so the overlay can be retired? "\n'
            '                "Permanent overlays without a re-cal plan are a recurring SR 11-7 finding."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.4 — Use Limitations",\n'
            '        },\n'
            '        {\n'
            '            "id": "methodology_change_as_scenario_impact",\n'
            '            "label": "Methodology change attributed as scenario impact",\n'
            '            "severity": "high",\n'
            '            "trigger": (\n'
            '                ("benchmark" in text or "big 6" in text or "big 8" in text\n'
            '                 or "reconstitut" in text or "re-cal" in text)\n'
            '                and ("scenario" in text or "stress" in text)\n'
            '                and not ("methodology" in text or "model update" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "Is this delta a model/methodology change or a scenario-input change? "\n'
            '                "Mixing the two understates the size of methodology updates between cycles."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.4 — Change Management",\n'
            '        },\n'
            '        {\n'
            '            "id": "dfs_modeled_with_capital_one_only_data",\n'
            '            "label": "DFS / Discover behavior modeled with Capital One-only data",\n'
            '            "severity": "high",\n'
            '            "trigger": (\n'
            '                ("dfs" in text or "discover" in text)\n'
            '                and not ("validat" in text or "back-test" in text or "backtest" in text\n'
            '                         or "demograph" in text or "tenure" in text or "cohort align" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "How is DFS behavior validated against Capital One PSAV cohorts? "\n'
            '                "Demographic / tenure / channel differences should be empirically tested."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.3 — Data Quality and Relevance",\n'
            '        },\n'
            '        {\n'
            '            "id": "judgment_floor_no_history",\n'
            '            "label": "Floor / cap calibrated to management judgment with no historical anchor",\n'
            '            "severity": "medium",\n'
            '            "trigger": (\n'
            '                ("floor" in text or "cap" in text or "limit" in text)\n'
            '                and ("judgment" in text or "qualitative" in text or "expert" in text)\n'
            '                and not ("2008" in text or "2020" in text or "historical" in text\n'
            '                         or "back-test" in text or "backtest" in text)\n'
            '            ),\n'
            '            "regulator_question": (\n'
            '                "What historical period (2008 / 2020 / 2023) anchors the floor? "\n'
            '                "Pure management-judgment floors are weak under SR 11-7."\n'
            '            ),\n'
            '            "rule_citation": "SR 11-7 §III.3 — Calibration",\n'
            '        },\n'
            '    ]\n'
            '\n'
            '    flags = [r for r in rules if r["trigger"]]\n'
            '    return {\n'
            '        "tripped":       [{"id": r["id"], "label": r["label"],\n'
            '                            "severity": r["severity"],\n'
            '                            "regulator_question": r["regulator_question"],\n'
            '                            "rule_citation": r["rule_citation"]}\n'
            '                           for r in flags],\n'
            '        "passed":        [r["id"] for r in rules if not r["trigger"]],\n'
            '        "rule_count":    len(rules),\n'
            '        "max_severity":  max((r["severity"] for r in flags),\n'
            '                              key=lambda s: ["low","medium","high","critical"].index(s),\n'
            '                              default="none"),\n'
            '    }\n'
        ),
    )

    # ── Methodology / Challenger — per-product assumption lookup ──────────
    ctx.register_python_tool(
        name="get_model_assumptions",
        description=(
            "Return the documented assumption block for a retail-deposit "
            "product or cohort — beta, attrition floor, recapture rate, "
            "marketing pullback path, overlay status. Demo data; in "
            "production, back this with a registered config table."
        ),
        parameters=[
            {"name": "product", "type": "string",
             "description": "Product / cohort key. One of: 'PSAV' (Performance Savings), 'DFS_CD', 'DFS_SAVINGS', '360_SAVINGS', 'BRANCH_CHECKING', 'COMM_TIME', 'SBB_LIQUID'.",
             "required": True},
        ],
        python_source=(
            'def get_model_assumptions(product):\n'
            '    """Return per-product assumption block. Demo-grade; values\n'
            '    are illustrative and aligned with the bundled whitepapers."""\n'
            '    catalog = {\n'
            '        "PSAV": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_LIQUIDRATE",\n'
            '            "beta_floor": 0.30,\n'
            '            "beta_ceiling": 0.65,\n'
            '            "calibration_window": "2018-2024 monthly",\n'
            '            "marketing_elasticity": 0.18,\n'
            '            "validation_note": "PSAV is the legacy CapitalOne high-yield savings cohort. Used as the proxy for DFS savings until Q3-2026.",\n'
            '            "overlays": [],\n'
            '        },\n'
            '        "DFS_CD": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_CDRATE",\n'
            '            "beta_floor": 0.40,\n'
            '            "beta_ceiling": 0.85,\n'
            '            "benchmark": "Big 6 (Big 8 retired Q4-2025 to remove DFS double-count)",\n'
            '            "recapture_rate_at_maturity": 0.62,\n'
            '            "early_withdrawal_floor_pct": 0.015,\n'
            '            "validation_note": "Recapture rate is calibrated against 2018-2024 Discover internal data — DFS-native, not PSAV proxy.",\n'
            '            "overlays": [\n'
            '                {"name": "DFS CD benchmark overlay", "size_bps": 10,\n'
            '                 "rationale": "Discover historically prices ~10 bps above the Big 6 anchor; overlay preserves that spread post-acquisition."}\n'
            '            ],\n'
            '        },\n'
            '        "DFS_SAVINGS": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_LIQUIDRATE",\n'
            '            "beta_floor": 0.35,\n'
            '            "beta_ceiling": 0.70,\n'
            '            "validation_note": "DFS savings cohort is 18 months post-acquisition; segment alignment to PSAV is documented but tenure differs (DFS book skews longer-tenure).",\n'
            '            "overlays": [],\n'
            '        },\n'
            '        "360_SAVINGS": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_LIQUIDRATE",\n'
            '            "beta_floor": 0.45,\n'
            '            "beta_ceiling": 0.80,\n'
            '            "validation_note": "360 Savings rate paid is post-hoc adjusted via the +25 bps overlay to match observed pricing; underlying model has not been re-fit since 2022.",\n'
            '            "overlays": [\n'
            '                {"name": "360 Savings Rate Paid Overlay", "size_bps": 25,\n'
            '                 "rationale": "Reflects competitive repricing not yet captured in the core Liquid Rate model. Re-cal targeted Q1-2026 per Model Risk Office."}\n'
            '            ],\n'
            '        },\n'
            '        "BRANCH_CHECKING": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_BRANCHBALANCE",\n'
            '            "macro_features": False,\n'
            '            "attrition_pct_annual": 0.04,\n'
            '            "validation_note": "Legacy COF branch-checking AOF model is non-macro-sensitive — known limitation; backtested only against 2018-2024 quiet period.",\n'
            '            "overlays": [],\n'
            '        },\n'
            '        "COMM_TIME": {\n'
            '            "model_id": "PRED_RETAILDEPOSIT_CDATTRITION",\n'
            '            "early_withdrawal_floor_pct": 0.020,\n'
            '            "renewal_recapture": 0.55,\n'
            '            "validation_note": "Floor calibrated to Q4-2008 / Q2-2020 idiosyncratic-withdrawal observations.",\n'
            '            "overlays": [],\n'
            '        },\n'
            '        "SBB_LIQUID": {\n'
            '            "model_id": "PRED_SBB_BALANCEMODEL",\n'
            '            "submodels": 5,\n'
            '            "status": "Temporary — promotion to Permanent targeted Q3-2026.",\n'
            '            "validation_note": "Suite split into 5 sub-models in CCAR-26 (merchant volume vs loan-linked sweep disentangled).",\n'
            '            "overlays": [],\n'
            '        },\n'
            '    }\n'
            '    key = (product or "").upper().replace(" ", "_").replace("-", "_")\n'
            '    if key not in catalog:\n'
            '        return {"error": f"Unknown product `{product}`. Available: {sorted(catalog.keys())}"}\n'
            '    return {"product": key, **catalog[key]}\n'
        ),
    )

    # ── Sensitivity walk — perturb a parameter, recompute IE ──────────────
    ctx.register_python_tool(
        name="compute_sensitivity_walk",
        description=(
            "Sensitivity branch of the variance walk: take a base scenario "
            "+ a parameter perturbation (recapture rate Δ, beta Δ, attrition "
            "floor Δ) and return the implied Interest_Expense_mm impact and "
            "the new total. Used to answer 'what if X were Y% different?' "
            "questions in the chat."
        ),
        parameters=[
            {"name": "scenario",            "type": "string",
             "description": "Scenario name to perturb (e.g. 'CCAR_26_BHC_Stress').",
             "required": True},
            {"name": "parameter",           "type": "string",
             "description": "Which parameter to shock: 'recapture_rate', 'beta', or 'attrition_floor'.",
             "required": True},
            {"name": "delta_pct",           "type": "number",
             "description": "Relative perturbation (e.g. -0.20 = 20% lower than base, +0.10 = 10% higher).",
             "required": True},
            {"name": "product",             "type": "string",
             "description": "Optional product scope (e.g. 'DFS_CD'). If omitted, applies to all retail products.",
             "required": False},
            {"name": "csv_path",            "type": "string",
             "description": "Path to CCAR_Retail_Outputs.csv. Defaults to bundled sample.",
             "required": False},
        ],
        python_source=(
            'def compute_sensitivity_walk(scenario, parameter, delta_pct,\n'
            '                              product=None, csv_path=None):\n'
            '    """Approximate sensitivity: scale rate/balance/attrition by delta_pct\n'
            '    and recompute Interest_Expense_mm against the base scenario row."""\n'
            '    import os\n'
            '    import pandas as pd\n'
            '\n'
            '    if not csv_path:\n'
            '        here = os.path.dirname(os.path.abspath(__file__))\n'
            '        repo = os.path.abspath(os.path.join(here, "..", "..", ".."))\n'
            '        csv_path = os.path.join(repo, "sample_data", "ccar", "CCAR_Retail_Outputs.csv")\n'
            '\n'
            '    df = pd.read_csv(csv_path)\n'
            '    needed = {"Scenario", "Quarter_ID", "Portfolio", "Product_L1", "Metric", "Value"}\n'
            '    missing = needed - set(df.columns)\n'
            '    if missing:\n'
            '        return {"error": f"CSV missing columns: {sorted(missing)}"}\n'
            '\n'
            '    valid_params = {"recapture_rate", "beta", "attrition_floor"}\n'
            '    if parameter not in valid_params:\n'
            '        return {"error": f"parameter must be one of {sorted(valid_params)}"}\n'
            '\n'
            '    sub = df[df["Scenario"] == scenario].copy()\n'
            '    if product:\n'
            '        prod_norm = product.upper().replace("_", " ").replace("-", " ")\n'
            '        sub = sub[sub["Product_L1"].str.upper().str.contains(prod_norm.split()[0])]\n'
            '    if sub.empty:\n'
            '        return {"error": f"No rows for scenario={scenario!r}, product={product!r}",\n'
            '                "available_scenarios": sorted(df["Scenario"].unique().tolist())}\n'
            '\n'
            '    wide = sub.pivot_table(\n'
            '        index=["Quarter_ID", "Portfolio", "Product_L1"],\n'
            '        columns="Metric", values="Value", aggfunc="first",\n'
            '    ).reset_index().fillna(0.0)\n'
            '\n'
            '    base_ie_mm = (wide.get("Interest_Expense_mm", pd.Series([0])).sum())\n'
            '\n'
            '    # Approximate effect on Interest_Expense_mm:\n'
            '    #   beta            ≈ rate_paid scales by (1 + delta_pct)         → rate effect\n'
            '    #   attrition_floor ≈ balance scales by (1 - delta_pct/2)          → volume effect\n'
            '    #   recapture_rate  ≈ balance scales by (1 + delta_pct * 0.4)      → volume effect\n'
            '    rate_d, vol_d = 0.0, 0.0\n'
            '    if parameter == "beta":\n'
            '        rate_d = float(delta_pct)\n'
            '    elif parameter == "attrition_floor":\n'
            '        vol_d = -float(delta_pct) / 2.0\n'
            '    elif parameter == "recapture_rate":\n'
            '        vol_d = float(delta_pct) * 0.4\n'
            '\n'
            '    rate_eff = base_ie_mm * rate_d\n'
            '    vol_eff  = base_ie_mm * vol_d\n'
            '    mix_eff  = base_ie_mm * rate_d * vol_d\n'
            '    new_ie_mm = base_ie_mm + rate_eff + vol_eff + mix_eff\n'
            '\n'
            '    return {\n'
            '        "scenario":            scenario,\n'
            '        "parameter":           parameter,\n'
            '        "delta_pct":           float(delta_pct),\n'
            '        "product":             product,\n'
            '        "base_interest_expense_mm":   round(float(base_ie_mm), 2),\n'
            '        "perturbed_interest_expense_mm": round(float(new_ie_mm), 2),\n'
            '        "delta_mm":            round(float(new_ie_mm - base_ie_mm), 2),\n'
            '        "rate_effect_mm":      round(float(rate_eff), 2),\n'
            '        "volume_effect_mm":    round(float(vol_eff), 2),\n'
            '        "mix_effect_mm":       round(float(mix_eff), 2),\n'
            '        "method_note":         "Demo-grade linearization; production sensitivities should re-run the model.",\n'
            '    }\n'
        ),
    )
