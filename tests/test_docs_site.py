"""The docs site config must stay in sync with the files on disk.

Cheap guard against the kind of rot that let docs/03_roadmap.md sit two
phases behind README for months: a nav entry pointing at a deleted page,
or an API page referencing a module that was renamed.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "mkdocs.yml"


def _nav_files(node, out):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, list):
        for item in node:
            _nav_files(item, out)
    elif isinstance(node, dict):
        for v in node.values():
            _nav_files(v, out)
    return out


@pytest.fixture(scope="module")
def cfg():
    # mkdocs.yml uses python-specific tags in some setups; plain safe_load
    # is enough for this config
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


def test_every_nav_target_exists(cfg):
    docs_dir = ROOT / cfg.get("docs_dir", "docs")
    missing = [f for f in _nav_files(cfg["nav"], [])
               if not (docs_dir / f).exists()]
    assert not missing, f"nav points at missing files: {missing}"


def test_api_pages_reference_real_modules(cfg):
    """Every '::: padpd.x' identifier must resolve to a source file."""
    src = ROOT / "src"
    missing = []
    for page in (ROOT / "docs" / "api").glob("*.md"):
        for mod in re.findall(r"^::: ([\w.]+)", page.read_text(), re.M):
            rel = Path(*mod.split("."))
            if not (src / rel).with_suffix(".py").exists() \
                    and not (src / rel / "__init__.py").exists():
                missing.append(f"{page.name}: {mod}")
    assert not missing, f"API pages reference missing modules: {missing}"


def test_roadmap_covers_shipped_phases():
    """README and the roadmap must agree on which phases exist."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "03_roadmap.md").read_text(encoding="utf-8")
    phases = set(re.findall(r"Phase (\d+(?:\.\d+)?)", readme))
    missing = sorted(p for p in phases if f"Phase {p}" not in roadmap)
    assert not missing, (
        f"README mentions Phase {missing} but docs/03_roadmap.md does not")
