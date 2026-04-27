"""Workflow validation logic — shared by chat tools, the validation endpoint,
and the chat router itself. Lives outside chat.py to avoid circular imports.
"""
from __future__ import annotations

from typing import Any

from routers.datasets import _DATASETS
from routers.models_registry import _MODELS
from routers.scenarios import _SCENARIOS


def validate_workflow_payload(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a list of {severity, message, node_id?} for the given workflow."""
    issues: list[dict[str, Any]] = []
    by_id = {n["id"]: n for n in nodes}
    incoming: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    outgoing: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e.get("source") in by_id and e.get("target") in by_id:
            incoming[e["target"]].append(e["source"])
            outgoing[e["source"]].append(e["target"])

    def has_cycle() -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n["id"]: WHITE for n in nodes}
        def visit(v: str) -> bool:
            if color[v] == GRAY: return True
            if color[v] == BLACK: return False
            color[v] = GRAY
            for c in outgoing.get(v, []):
                if visit(c): return True
            color[v] = BLACK
            return False
        return any(visit(n["id"]) for n in nodes if color[n["id"]] == WHITE)

    if has_cycle():
        issues.append({"severity": "error", "message": "Workflow contains a cycle. Models can't loop back into themselves."})

    for n in nodes:
        kind = n.get("kind")
        nid = n["id"]
        if kind == "model" and not incoming[nid]:
            issues.append({
                "severity": "error",
                "message": "Model node has no input. Connect a dataset, scenario, or upstream model.",
                "node_id": nid,
            })
        if kind == "destination":
            if not incoming[nid]:
                issues.append({
                    "severity": "warning",
                    "message": "Destination has no upstream model — nothing will be written.",
                    "node_id": nid,
                })
            cfg = n.get("config", {})
            target = cfg.get("table") or cfg.get("bucket") or cfg.get("filename") or cfg.get("ref")
            if not target:
                issues.append({
                    "severity": "warning",
                    "message": "Destination has no target configured.",
                    "node_id": nid,
                })
        if kind in ("dataset", "scenario") and not outgoing[nid]:
            issues.append({
                "severity": "info",
                "message": "Input node isn't wired to anything — it'll be skipped at run time.",
                "node_id": nid,
            })

    # Feature-mismatch check
    for n in nodes:
        if n.get("kind") != "model":
            continue
        m = _MODELS.get(n.get("ref_id", ""))
        if not m or not m.coefficients:
            continue
        model_features = {f.lower() for f in m.coefficients.keys()}
        for src_id in incoming[n["id"]]:
            src = by_id.get(src_id)
            if not src:
                continue
            available: set[str] = set()
            if src.get("kind") == "scenario":
                sc = _SCENARIOS.get(src["ref_id"])
                if sc:
                    available |= {v.lower() for v in sc.variables}
            elif src.get("kind") == "dataset":
                d = _DATASETS.get(src["ref_id"])
                if d:
                    available |= {c.name.lower() for c in d.columns}
            if available:
                missing = model_features - available
                if missing == model_features:
                    issues.append({
                        "severity": "warning",
                        "message": f"Model expects features {sorted(model_features)} — none found in `{src.get('ref_id')}`. The model will only contribute its intercept.",
                        "node_id": n["id"],
                    })
                elif missing and len(missing) >= len(model_features) // 2 + 1:
                    issues.append({
                        "severity": "info",
                        "message": f"Model expects {sorted(model_features)} — {len(missing)} feature(s) missing in `{src.get('ref_id')}`: {sorted(missing)}.",
                        "node_id": n["id"],
                    })
    return issues
