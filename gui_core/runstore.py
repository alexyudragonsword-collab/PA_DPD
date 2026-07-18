"""Experiment run registry shared by both GUIs.

Each modeling / DPD / deployment experiment is recorded as a Run and
persisted as one JSON file under ``gui_runs/``, so results survive
restarts and are visible from either GUI (web or desktop) for
comparison.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Run:
    name: str
    kind: str                       # "pa_model" | "dpd" | "deploy" | ...
    config: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)   # label -> file path
    timestamp: float = field(default_factory=time.time)
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def when(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.timestamp))


class RunStore:
    def __init__(self, root: str | Path = "gui_runs"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{10}", run_id):
            raise ValueError(f"invalid run id: {run_id!r}")
        return self.root / f"{run_id}.json"

    def add(self, run: Run) -> Run:
        with open(self._path(run.run_id), "w") as f:
            json.dump(asdict(run), f, indent=1, default=str)
        return run

    def list(self, kind: str | None = None) -> list[Run]:
        runs = []
        for p in sorted(self.root.glob("*.json")):
            try:
                runs.append(Run(**json.load(open(p))))
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupt entries rather than crash the GUI
        runs.sort(key=lambda r: r.timestamp, reverse=True)
        if kind:
            runs = [r for r in runs if r.kind == kind]
        return runs

    def get(self, run_id: str) -> Run | None:
        p = self._path(run_id)
        return Run(**json.load(open(p))) if p.exists() else None

    def delete(self, run_id: str) -> bool:
        p = self._path(run_id)
        if p.exists():
            p.unlink()
            return True
        return False
