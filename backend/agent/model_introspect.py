"""Best-effort introspection of uploaded model artifacts.

Goal: produce a structured JSON-safe description of any model file the analyst
uploads (.pkl / .pickle / .joblib / .onnx / .json) so the Model Explainer agent
can talk about it concretely instead of treating it as a black box.

Strategy by format
------------------
- **joblib / pickle / pickle**: try `joblib.load` → walk the resulting object,
  extract sklearn params, coefficients, feature names, dataclass fields,
  custom-class metadata. If unpickling fails (most often because the user's
  class isn't importable in the backend), fall back to `pickletools` to at
  least pull the class names and module references out of the bytecode.
- **onnx**: load with the `onnx` library and report inputs / outputs / op
  types / node count.
- **json**: parse and report top-level shape.

Security note: loading a pickle is equivalent to executing code from the
uploaded file. We trust the analyst because they uploaded the artifact
themselves. In a multi-tenant deployment, run introspection in a sandboxed
subprocess.
"""
from __future__ import annotations

import importlib.util
import io
import json
import pickle
import pickletools
import sys
import warnings
from pathlib import Path
from typing import Any


MAX_LIST_PREVIEW = 12
MAX_STRING = 200


def introspect_artifact(path: Path, fmt: str) -> dict[str, Any]:
    """Top-level dispatcher. Always returns a dict (never raises)."""
    fmt = (fmt or "").lower().lstrip(".")
    try:
        if fmt in ("pkl", "pickle", "joblib"):
            return _introspect_pickle(path)
        if fmt == "onnx":
            return _introspect_onnx(path)
        if fmt == "json":
            return _introspect_json(path)
        return {"format": fmt, "error": f"Unsupported file format `{fmt}`"}
    except Exception as e:
        return {"format": fmt, "error": f"Introspection threw: {e}"}


# ── Pickle / joblib ─────────────────────────────────────────────────────
class _ResilientUnpickler(pickle.Unpickler):
    """Tries `__main__.X` lookups against our sample-models generator file
    before giving up. Lets us introspect pickles that were dumped from a
    standalone script without forcing the user to refactor their classes
    into a package.
    """

    _generator_module: Any = None

    def find_class(self, module: str, name: str):
        # Standard resolution first
        try:
            return super().find_class(module, name)
        except Exception:
            if module == "__main__":
                gen = self._load_sample_generator()
                if gen is not None and hasattr(gen, name):
                    return getattr(gen, name)
            raise

    @classmethod
    def _load_sample_generator(cls):
        if cls._generator_module is not None:
            return cls._generator_module
        gen_path = (
            Path(__file__).resolve().parent.parent.parent
            / "sample_models" / "portfolio" / "generate.py"
        )
        if not gen_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location("cma_sample_generate", gen_path)
            if spec is None or spec.loader is None:
                return None
            mod = importlib.util.module_from_spec(spec)
            # Required: dataclass decorator does sys.modules[cls.__module__] lookup
            sys.modules["cma_sample_generate"] = mod
            spec.loader.exec_module(mod)
            cls._generator_module = mod
            return mod
        except Exception:
            sys.modules.pop("cma_sample_generate", None)
            return None


def _introspect_pickle(path: Path) -> dict[str, Any]:
    """Try resilient pickle.load, then plain joblib, then pickletools fallback."""
    _augment_sys_path()
    info: dict[str, Any] = {"format": "pickle", "file_size_bytes": path.stat().st_size}

    # Attempt 1: resilient unpickler (handles __main__ → sample-generator fallback)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with open(path, "rb") as f:
                obj = _ResilientUnpickler(f).load()
        info["loaded"] = True
        info.update(_describe_object(obj))
        return info
    except Exception as e:
        info["load_error_pickle"] = f"{type(e).__name__}: {e}"

    # Attempt 2: joblib (handles numpy-heavy artifacts that plain pickle can't)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import joblib
            obj = joblib.load(str(path))
        info["loaded"] = True
        info.update(_describe_object(obj))
        info.pop("load_error_pickle", None)
        return info
    except Exception as e:
        info["loaded"] = False
        info["load_error"] = f"{type(e).__name__}: {e}"

    # Attempt 3: pickletools — extract structural info without execution
    try:
        info.update(_describe_pickle_structure(path))
    except Exception as e:
        info["structure_error"] = str(e)
    return info


def _augment_sys_path() -> None:
    """Add common dirs so pickled custom classes can be resolved."""
    here = Path(__file__).resolve().parent.parent.parent
    candidates = [
        here / "sample_models" / "portfolio",
    ]
    for p in candidates:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


def _describe_object(obj: Any) -> dict[str, Any]:
    """Walk an unpickled object and pull structured facts about it."""
    info: dict[str, Any] = {
        "class_name": type(obj).__name__,
        "module": type(obj).__module__,
        "doc": (type(obj).__doc__ or "").strip()[:MAX_STRING],
    }

    # ── sklearn-style introspection ──────────────────────────────────────
    if hasattr(obj, "get_params") and callable(getattr(obj, "get_params", None)):
        try:
            info["sklearn_params"] = {
                k: _safe_repr(v) for k, v in obj.get_params(deep=False).items()
            }
        except Exception:
            pass

    if hasattr(obj, "coef_"):
        try:
            import numpy as np
            arr = np.asarray(obj.coef_)
            info["coefficients"] = {
                "shape": list(arr.shape),
                "preview": arr.flatten()[:MAX_LIST_PREVIEW].tolist(),
            }
        except Exception:
            pass
    if hasattr(obj, "intercept_"):
        try:
            import numpy as np
            arr = np.asarray(obj.intercept_)
            info["intercept"] = arr.tolist() if arr.size <= 10 else float(arr.flat[0])
        except Exception:
            pass

    if hasattr(obj, "feature_importances_"):
        try:
            import numpy as np
            arr = np.asarray(obj.feature_importances_)
            info["feature_importances"] = {
                "shape": list(arr.shape),
                "preview": arr.flatten()[:MAX_LIST_PREVIEW].tolist(),
            }
        except Exception:
            pass

    if hasattr(obj, "feature_names_in_"):
        try:
            info["feature_names"] = list(obj.feature_names_in_)
        except Exception:
            pass
    if hasattr(obj, "n_features_in_"):
        try:
            info["n_features_in"] = int(obj.n_features_in_)
        except Exception:
            pass
    if hasattr(obj, "classes_"):
        try:
            info["classes"] = [str(c) for c in obj.classes_]
        except Exception:
            pass

    # Neural-network attrs
    for attr in ("hidden_layer_sizes", "activation", "solver", "n_iter_",
                 "n_layers_", "loss_", "best_loss_"):
        if hasattr(obj, attr):
            try:
                info[attr] = _safe_repr(getattr(obj, attr))
            except Exception:
                pass

    # Pipeline steps
    if hasattr(obj, "steps") and isinstance(obj.steps, list):
        try:
            info["pipeline_steps"] = [
                {"name": name, "class": type(step).__name__}
                for name, step in obj.steps
            ]
        except Exception:
            pass

    # Dataclass fields
    if hasattr(obj, "__dataclass_fields__"):
        try:
            info["dataclass_fields"] = {
                k: _safe_repr(getattr(obj, k))
                for k in list(obj.__dataclass_fields__.keys())[:20]
            }
        except Exception:
            pass

    # Custom `metadata` dict (our sample models all expose one)
    if hasattr(obj, "metadata"):
        try:
            md = getattr(obj, "metadata")
            if isinstance(md, dict):
                info["metadata"] = {k: _safe_repr(v) for k, v in md.items()}
        except Exception:
            pass

    # Feature/target name lists (custom classes)
    for attr in ("feature_names", "target_name", "target_names", "input_features"):
        if hasattr(obj, attr) and attr not in info:
            try:
                info[attr] = _safe_repr(getattr(obj, attr))
            except Exception:
                pass

    # Public methods
    methods: list[str] = []
    for m in dir(obj):
        if m.startswith("_"):
            continue
        try:
            if callable(getattr(obj, m, None)):
                methods.append(m)
        except Exception:
            continue
    info["public_methods"] = methods[:20]

    # If nothing else surfaced, dump public attribute names
    if len(info) <= 4:  # class_name, module, doc, public_methods
        try:
            attrs = [a for a in dir(obj) if not a.startswith("_") and not callable(getattr(obj, a, None))]
            info["public_attrs"] = attrs[:30]
        except Exception:
            pass

    return info


def _describe_pickle_structure(path: Path) -> dict[str, Any]:
    """Use pickletools to extract class names without executing the pickle."""
    classes: list[str] = []
    modules: list[str] = []
    memo_size = 0
    raw = path.read_bytes()
    sink = io.StringIO()
    try:
        pickletools.dis(raw, sink)
    except Exception:
        return {"pickletools_error": "Could not disassemble"}

    for line in sink.getvalue().splitlines():
        # Lines like:  "    66: c    GLOBAL     'numpy.core.multiarray scalar'"
        if "GLOBAL" in line:
            try:
                _, ref = line.rsplit("'", 2)[0].rsplit("'", 1)
            except Exception:
                continue
            ref = ref.strip()
            if " " in ref:
                mod, _, cls = ref.partition(" ")
                full = f"{mod}.{cls}"
                if full not in classes:
                    classes.append(full)
                if mod not in modules:
                    modules.append(mod)

    return {
        "classes_referenced": classes[:25],
        "modules_referenced": modules[:25],
        "raw_bytes": len(raw),
        "note": "Object could not be unpickled; this is a static structural read.",
    }


# ── ONNX ─────────────────────────────────────────────────────────────────
def _introspect_onnx(path: Path) -> dict[str, Any]:
    try:
        import onnx
    except ImportError:
        return {"format": "onnx", "error": "onnx package not installed"}
    try:
        m = onnx.load(str(path))
    except Exception as e:
        return {"format": "onnx", "error": f"Could not load ONNX: {e}"}
    g = m.graph

    def _shape_of(io_proto) -> str:
        try:
            dims = []
            for d in io_proto.type.tensor_type.shape.dim:
                if d.HasField("dim_value"):
                    dims.append(str(d.dim_value))
                elif d.HasField("dim_param"):
                    dims.append(d.dim_param)
                else:
                    dims.append("?")
            return f"[{', '.join(dims)}]"
        except Exception:
            return "?"

    op_types: dict[str, int] = {}
    for n in g.node:
        op_types[n.op_type] = op_types.get(n.op_type, 0) + 1

    return {
        "format": "onnx",
        "ir_version": int(m.ir_version),
        "producer_name": m.producer_name,
        "producer_version": m.producer_version,
        "model_version": int(m.model_version),
        "doc_string": (m.doc_string or "").strip()[:MAX_STRING],
        "inputs": [
            {"name": i.name, "shape": _shape_of(i)}
            for i in g.input
        ][:10],
        "outputs": [
            {"name": o.name, "shape": _shape_of(o)}
            for o in g.output
        ][:10],
        "node_count": len(g.node),
        "op_types": dict(sorted(op_types.items(), key=lambda kv: -kv[1])[:15]),
        "initializer_count": len(g.initializer),
        "opset_imports": [
            {"domain": op.domain or "ai.onnx", "version": int(op.version)}
            for op in m.opset_import
        ],
    }


# ── JSON ─────────────────────────────────────────────────────────────────
def _introspect_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"format": "json", "error": f"Could not parse JSON: {e}"}

    info: dict[str, Any] = {"format": "json", "file_size_bytes": path.stat().st_size}
    if isinstance(data, dict):
        info["root_type"] = "object"
        info["top_level_keys"] = list(data.keys())[:25]
        # If it looks like a model card, surface known fields
        for k in ("name", "model_type", "version", "framework", "metadata", "feature_names"):
            if k in data:
                info[k] = _safe_repr(data[k])
    elif isinstance(data, list):
        info["root_type"] = "array"
        info["length"] = len(data)
        if data and isinstance(data[0], dict):
            info["element_keys"] = list(data[0].keys())[:25]
    else:
        info["root_type"] = type(data).__name__
        info["value"] = _safe_repr(data)
    return info


# ── Helpers ──────────────────────────────────────────────────────────────
def _safe_repr(v: Any) -> Any:
    """Return a JSON-safe representation, trimmed for size."""
    try:
        if v is None or isinstance(v, bool):
            return v
        if isinstance(v, (int, float, str)):
            if isinstance(v, str) and len(v) > MAX_STRING:
                return v[:MAX_STRING] + "…"
            return v
        if isinstance(v, (list, tuple)):
            return [_safe_repr(x) for x in v[:MAX_LIST_PREVIEW]]
        if isinstance(v, dict):
            return {str(k): _safe_repr(val) for k, val in list(v.items())[:MAX_LIST_PREVIEW]}
        # numpy scalars / arrays
        try:
            import numpy as np
            if isinstance(v, np.ndarray):
                return {
                    "shape": list(v.shape),
                    "preview": v.flatten()[:MAX_LIST_PREVIEW].tolist(),
                }
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return float(v)
        except Exception:
            pass
        return str(v)[:MAX_STRING]
    except Exception:
        return "<unrepresentable>"
