"""Domain packs — opt-in bundles of skills + tools + datasets + models.

A pack is a self-contained directory under `backend/packs/<id>/` that ships:

  - **Skills**:       markdown agent skills (`skills/*.md`)
  - **Python tools**: tools registered via `ctx.register_python_tool(...)`
  - **Datasets**:     bundled CSV/Parquet files staged for specific functions
  - **Models**:       bundled artifacts (.pkl, .joblib, …) for specific functions

Each pack lives next to a `pack.py` exposing a single `register(ctx)` function.
At backend startup, `discover_and_register()` scans `backend/packs/`, imports
every `<id>/pack.py`, and invokes `register(ctx)` so the pack can install its
artifacts via the `PackContext` API.

Why a pack?
  - Domain isolation — adding "interest_rate_risk" or "treasury" is a new
    directory, not edits scattered across routers.
  - Authorization — packs declare `user_groups`; non-matching users don't see
    pack-scoped artifacts.
  - Lifecycle — a pack can be disabled (skip `discover_and_register`) without
    touching any router.

Source tag conventions for AgentSkill / PythonTool / Dataset / TrainedModel:
  - `source = "builtin"`  : universal, ships with the platform
  - `source = "user"`     : created/uploaded at runtime by an analyst
  - `source = "pack"`     : installed by a domain pack; `pack_id` carries the
                            pack's id (e.g. "portfolio")
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger("cma.packs")

PACKS_DIR = Path(__file__).resolve().parent


# ── Pack metadata ──────────────────────────────────────────────────────────
@dataclass
class Pack:
    """A discovered domain pack. Populated by the pack's `pack.py:register`.

    Attributes:
      id:                  short identifier (e.g. "portfolio")
      label:               human-readable name shown in the UI
      description:         one-line summary
      attach_to_functions: list of function_ids this pack auto-installs to
                           (empty = available to every function)
      user_groups:         list of user-group strings allowed to see the pack;
                           empty or `["*"]` means "everyone"
      color, icon:         optional UI metadata
    """
    id: str
    label: str = ""
    description: str = ""
    attach_to_functions: list[str] = field(default_factory=list)
    user_groups: list[str] = field(default_factory=list)
    color: str | None = None
    icon: str | None = None
    skills_dir: Path | None = None  # filled by ctx.register_skill_dir
    enabled: bool = True


# Global registries the routers consume.
# Populated by `discover_and_register()` calling each pack's `register(ctx)`.
_PACKS: dict[str, Pack] = {}
_PYTHON_TOOL_SEEDS: list[dict] = []           # consumed by routers/tools.py
_DATASET_ATTACHMENTS: list[dict] = []         # consumed by routers/datasets.py
_MODEL_ATTACHMENTS: list[dict] = []           # consumed by routers/models_registry.py


# ── PackContext (the API a pack uses) ──────────────────────────────────────
class PackContext:
    """The narrow API a pack uses inside its `register(ctx)` function.

    A `PackContext` knows which pack is currently registering, so that every
    artifact gets stamped with the right `pack_id` automatically.
    """

    def __init__(self, pack: Pack):
        self.pack = pack
        self.pack_dir: Path = PACKS_DIR / pack.id

    # ── Skills ─────────────────────────────────────────────────────────────
    def register_skill_dir(self, path: Path | str | None = None) -> None:
        """Register a directory of `.md` skill files for this pack.

        Defaults to `<pack_dir>/skills/` if no path is given. The skill loader
        will pick these up on its next call (mtime-based reload also picks up
        new files dropped in here)."""
        from agent.skill_loader import register_skill_source

        p = Path(path) if path else self.pack_dir / "skills"
        if not p.exists():
            log.warning("[pack:%s] skill dir missing: %s", self.pack.id, p)
            return
        self.pack.skills_dir = p
        register_skill_source(p, source="pack", pack_id=self.pack.id)

    # ── Python tools ───────────────────────────────────────────────────────
    def register_python_tool(
        self,
        *,
        name: str,
        description: str,
        parameters: list[dict],
        python_source: str,
        function_name: str | None = None,
        enabled: bool = True,
    ) -> None:
        """Register a Python tool that ships with this pack.

        The tool will appear in `/api/tools` with `source='pack'` and
        `pack_id=<this pack's id>`. The router consumes this seed list
        on first import."""
        _PYTHON_TOOL_SEEDS.append({
            "id": f"tool-{self.pack.id}-{name.replace('_', '-')}",
            "name": name,
            "description": description,
            "parameters": parameters,
            "python_source": python_source,
            "function_name": function_name or name,
            "enabled": enabled,
            "source": "pack",
            "pack_id": self.pack.id,
        })

    # ── Dataset attachments ────────────────────────────────────────────────
    def attach_dataset(
        self,
        *,
        function_id: str,
        dataset_id: str,
        name: str,
        description: str,
        source_path: Path | str,
    ) -> None:
        """Stage a bundled CSV/Parquet/etc. as a dataset for a function.

        The router (datasets.py) copies the file into its data dir on first
        load and registers a `Dataset` with `source='pack'` + `pack_id`."""
        _DATASET_ATTACHMENTS.append({
            "function_id": function_id,
            "dataset_id": dataset_id,
            "name": name,
            "description": description,
            "source_path": Path(source_path),
            "pack_id": self.pack.id,
        })

    # ── Model attachments ──────────────────────────────────────────────────
    def attach_model(
        self,
        *,
        function_id: str,
        model_id: str,
        name: str,
        description: str,
        source_path: Path | str,
        train_metrics: dict | None = None,
    ) -> None:
        """Stage a bundled model artifact for a function. Same pattern."""
        _MODEL_ATTACHMENTS.append({
            "function_id": function_id,
            "model_id": model_id,
            "name": name,
            "description": description,
            "source_path": Path(source_path),
            "train_metrics": train_metrics or {},
            "pack_id": self.pack.id,
        })


# ── Discovery + registration ───────────────────────────────────────────────
def discover_and_register() -> None:
    """Scan `backend/packs/` for sub-directories with a `pack.py` and call
    each pack's `register(ctx)` function. Idempotent — calling twice is a
    no-op for packs already loaded."""
    if not PACKS_DIR.exists():
        return
    for child in sorted(PACKS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_") or child.name.startswith("."):
            continue
        pack_module_path = child / "pack.py"
        if not pack_module_path.exists():
            continue
        if child.name in _PACKS:
            continue  # already registered
        try:
            mod = importlib.import_module(f"packs.{child.name}.pack")
        except Exception as e:
            log.error("[pack:%s] import failed: %s", child.name, e)
            continue
        register_fn: Callable[[PackContext], None] | None = getattr(mod, "register", None)
        if register_fn is None:
            log.error("[pack:%s] missing register() function", child.name)
            continue
        # The pack should construct its Pack metadata (id, label, ...) and
        # call ctx methods. We pass a minimal stub Pack which the register
        # function may overwrite via `ctx.pack = ...` if needed.
        ctx = PackContext(Pack(id=child.name))
        try:
            register_fn(ctx)
            _PACKS[child.name] = ctx.pack
            log.info(
                "[pack:%s] registered (%s)",
                ctx.pack.id, ctx.pack.label or "(no label)",
            )
        except Exception as e:
            log.error("[pack:%s] register() failed: %s", child.name, e)


# ── Read-side helpers (used by routers + auth) ─────────────────────────────
def list_packs() -> list[Pack]:
    return list(_PACKS.values())


def get_pack(pack_id: str | None) -> Pack | None:
    if not pack_id:
        return None
    return _PACKS.get(pack_id)


def python_tool_seeds() -> list[dict]:
    return list(_PYTHON_TOOL_SEEDS)


def dataset_attachments() -> list[dict]:
    return list(_DATASET_ATTACHMENTS)


def model_attachments() -> list[dict]:
    return list(_MODEL_ATTACHMENTS)


# ── Authorization helper ───────────────────────────────────────────────────
def is_pack_visible(pack_id: str | None, user_groups: list[str]) -> bool:
    """Return True if the user (with the supplied groups) can see artifacts
    from the given pack. Universal artifacts (pack_id=None) are always
    visible. The wildcard group "*" grants access to every pack."""
    if not pack_id:
        return True
    if "*" in user_groups:
        return True
    pack = _PACKS.get(pack_id)
    if not pack:
        return True  # unknown pack — fail open rather than hide everything
    if not pack.user_groups or "*" in pack.user_groups:
        return True
    return any(g in pack.user_groups for g in user_groups)
