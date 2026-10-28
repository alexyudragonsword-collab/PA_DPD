"""The desktop's working set: sources, fitted models, and the project spec.

The old desktop kept these in a process-lifetime dict, so closing the
window threw away every fitted model and every imported capture, and a
model was known only by a long display string. This keeps them on disk
under the user data directory, each with the lineage a result needs to be
read later:

- a **source** is stored as a *reference* - the synthetic generator's
  parameters, or the path and loader of a measured file - never as its
  arrays. Captures are megabytes; the reference is a line of JSON, and
  loading is lazy and cached for the session.
- a **model** is the fitted object saved with its own ``save()``, plus the
  source it was fitted on, its config, its metrics and the run that
  produced it. A model whose class cannot be serialised stays in memory
  for the session and says so (``persisted: False``) rather than
  pretending to be saved.
- the **spec** is the set of limits every verdict is judged against.

Pure Python, no GUI imports - the same rule as services.py.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_SPEC = {"evm_db": -40.0, "aclr_dbc": -45.0}

# The synthetic source a fresh workspace starts with: the DPD lab's old
# default operating point, so a first run reproduces the numbers in
# docs/05_performance_summary.md.
DEFAULT_SYNTHETIC = {"bandwidth_hz": 160e6, "qam": 1024, "symbols": 8,
                     "drive": 0.14, "cfr_papr_db": None, "frontend": "none"}


@dataclass
class SourceEntry:
    name: str
    # {"kind": "synthetic", "params": {...}} or
    # {"kind": "file", "loader": .., "path": .., "auto_align": ..}
    ref: dict
    added: float = field(default_factory=time.time)

    @property
    def synthetic(self) -> bool:
        return self.ref.get("kind") == "synthetic"


@dataclass
class ModelEntry:
    name: str
    family: str                     # "classical" | "neural"
    label: str                      # short type label, e.g. "GMP" / "DGRU-H8"
    config: dict
    source: str                     # SourceEntry.name it was fitted on
    metrics: dict
    run_id: str = ""
    file: str = ""                  # relative to the workspace, "" if unsaved
    added: float = field(default_factory=time.time)

    @property
    def persisted(self) -> bool:
        return bool(self.file)


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:60] or "model"


class Workspace:
    """Sources, models and spec, persisted as one index plus model files."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        (self.root / "models").mkdir(parents=True, exist_ok=True)
        self.spec: dict = dict(DEFAULT_SPEC)
        self.sources: dict[str, SourceEntry] = {}
        self.models: dict[str, ModelEntry] = {}
        self.active_source: str = ""
        self._loaded_sources: dict[str, dict] = {}
        self._loaded_models: dict[str, object] = {}
        self._load()
        if not self.sources:
            self.add_synthetic(DEFAULT_SYNTHETIC)

    # ---- persistence -----------------------------------------------
    @property
    def _index(self) -> Path:
        return self.root / "workspace.json"

    def _load(self) -> None:
        if not self._index.is_file():
            return
        try:
            d = json.loads(self._index.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return                  # a damaged index starts fresh, not crash
        self.spec = {**DEFAULT_SPEC, **d.get("spec", {})}
        for s in d.get("sources", []):
            e = SourceEntry(**s)
            self.sources[e.name] = e
        for m in d.get("models", []):
            e = ModelEntry(**m)
            if e.file and not (self.root / e.file).is_file():
                continue            # its file was deleted outside the app
            if e.file:
                self.models[e.name] = e
        self.active_source = d.get("active_source", "")
        if self.active_source not in self.sources:
            self.active_source = next(iter(self.sources), "")

    def save(self) -> None:
        d = {"version": 1, "spec": self.spec,
             "active_source": self.active_source,
             "sources": [asdict(e) for e in self.sources.values()],
             # session-only models are not written: on reload they would
             # point at an object that no longer exists
             "models": [asdict(e) for e in self.models.values()
                        if e.persisted]}
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self._index)

    # ---- spec --------------------------------------------------------
    def set_spec(self, **limits) -> None:
        self.spec.update({k: float(v) for k, v in limits.items()})
        self.save()

    # ---- sources -----------------------------------------------------
    def add_synthetic(self, params: dict, activate: bool = True) -> str:
        from gui_core import services
        p = {**DEFAULT_SYNTHETIC, **params}
        src = services.cached_synthetic_source(**p)
        name = src["name"]
        self.sources[name] = SourceEntry(name, {"kind": "synthetic",
                                                "params": p})
        self._loaded_sources[name] = src
        if activate:
            self.active_source = name
        self.save()
        return name

    def add_file(self, loader: str, path: str, auto_align: bool = False,
                 activate: bool = True) -> str:
        """Import a measured source. ``loader`` is a services.load_source
        kind: opendpd | cadence | mat | npz."""
        from gui_core import services
        src = services.load_source(loader, path, auto_align=auto_align)
        name = src["name"]
        if name in self.sources and not self.sources[name].synthetic:
            # same file name from a different folder: keep both
            name = f"{name} ({Path(path).parent.name})"
            src["name"] = name
        self.sources[name] = SourceEntry(name, {
            "kind": "file", "loader": loader, "path": str(path),
            "auto_align": bool(auto_align)})
        self._loaded_sources[name] = src
        if activate:
            self.active_source = name
        self.save()
        return name

    def remove_source(self, name: str) -> None:
        self.sources.pop(name, None)
        self._loaded_sources.pop(name, None)
        if self.active_source == name:
            self.active_source = next(iter(self.sources), "")
        self.save()

    def set_active(self, name: str) -> None:
        if name in self.sources:
            self.active_source = name
            self.save()

    def source(self, name: str | None = None) -> dict:
        """The loaded source dict (arrays), loading it on first use."""
        from gui_core import services
        name = name or self.active_source
        if name in self._loaded_sources:
            return self._loaded_sources[name]
        e = self.sources[name]
        if e.synthetic:
            src = services.cached_synthetic_source(**e.ref["params"])
        else:
            src = services.load_source(e.ref["loader"], e.ref["path"],
                                       auto_align=e.ref.get("auto_align",
                                                            False))
            src["name"] = name
        self._loaded_sources[name] = src
        return src

    def loaded_sources(self) -> dict:
        """Sources already in memory, by name - what services.
        eval_source_for consults before rebuilding a synthetic one."""
        return dict(self._loaded_sources)

    # ---- models ------------------------------------------------------
    def add_model(self, model, *, family: str, label: str, config: dict,
                  source: str, metrics: dict, run_id: str = "") -> str:
        name = f"{label} @ {source}"
        file = ""
        suffix = ".pt" if family == "neural" else ".npz"
        rel = f"models/{_slug(name)}_{int(time.time())}{suffix}"
        try:
            model.save(str(self.root / rel))
            file = rel
        except Exception:                        # noqa: BLE001
            # Not every fitted class is serialisable (some spline
            # variants have no get_config yet). It still works for this
            # session; the entry says it was not saved.
            file = ""
        old = self.models.get(name)
        if old and old.file and old.file != file:
            (self.root / old.file).unlink(missing_ok=True)
        self.models[name] = ModelEntry(
            name=name, family=family, label=label, config=dict(config),
            source=source, metrics={k: v for k, v in metrics.items()
                                    if isinstance(v, (int, float, str))},
            run_id=run_id, file=file)
        self._loaded_models[name] = model
        self.save()
        return name

    def model(self, name: str):
        if name in self._loaded_models:
            return self._loaded_models[name]
        from gui_core import services
        e = self.models[name]
        obj = services.load_saved_model(str(self.root / e.file))
        self._loaded_models[name] = obj
        return obj

    def remove_model(self, name: str) -> None:
        e = self.models.pop(name, None)
        self._loaded_models.pop(name, None)
        if e and e.file:
            (self.root / e.file).unlink(missing_ok=True)
        self.save()

    def model_meta(self, name: str) -> dict:
        """The meta dict services.eval_source_for expects."""
        e = self.models[name]
        return {"source": e.source, "config": e.config, "metrics": e.metrics}

    def eval_source_for(self, model_name: str) -> dict:
        from gui_core import services
        e = self.models[model_name]
        if e.source in self.sources:
            return self.source(e.source)
        return services.eval_source_for(self.model_meta(model_name),
                                        self.loaded_sources())
