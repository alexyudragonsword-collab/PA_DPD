"""One version number, five files, and nothing that kept them equal.

padpd's version is written out by hand in the Python package, the
packaging metadata, the Android app, a Windows batch file and the Windows
workflow. Four of those are invisible to `pip install -e .`, so a bump
that misses one produces an APK or an .exe that reports a version the
library does not have - and nothing fails.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import padpd  # noqa: E402


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# (file, pattern with one capturing group holding the version)
DECLARATIONS = [
    ("pyproject.toml", r'^version = "([0-9][^"]*)"', re.M),
    ("android/app/build.gradle", r'versionName "([0-9][^"]*)"', 0),
    ("packaging/build_windows_nuitka.bat",
     r"--product-version=([0-9][^\s]*)", 0),
    (".github/workflows/build-windows.yml",
     r"--product-version=([0-9][^\s]*)", 0),
]


@pytest.mark.parametrize("rel,pattern,flags", DECLARATIONS)
def test_declared_version_matches_the_package(rel, pattern, flags):
    found = re.findall(pattern, _text(rel), flags)
    assert found, f"{rel}: no version declaration matched {pattern!r}"
    for v in found:
        assert v == padpd.__version__, (
            f"{rel} says {v}, padpd.__version__ says {padpd.__version__}")


def test_file_version_tracks_product_version():
    """Nuitka takes two of them and they are bumped by the same hand."""
    for rel in ("packaging/build_windows_nuitka.bat",
                ".github/workflows/build-windows.yml"):
        text = _text(rel)
        prod = re.findall(r"--product-version=([0-9][^\s]*)", text)
        file = re.findall(r"--file-version=([0-9][^\s]*)", text)
        assert prod == file, f"{rel}: {prod} vs {file}"


def test_changelog_has_an_entry_for_this_version():
    """A released version with no changelog section is a version nobody
    can find out anything about."""
    head = _text("CHANGELOG.md")
    assert f"## [{padpd.__version__}]" in head, (
        f"CHANGELOG.md has no section for {padpd.__version__}")


def test_android_version_code_is_packed_from_the_version():
    """Android refuses to install an APK whose versionCode is not higher
    than the installed one, so a versionName bump with a forgotten code
    ships an update every existing device rejects - silently, because the
    build succeeds. Packing it from the version makes that impossible."""
    gradle = _text("android/app/build.gradle")
    code = int(re.search(r"versionCode (\d+)", gradle).group(1))
    major, minor, patch = (int(p) for p in padpd.__version__.split(".")[:3])
    assert code == major * 10000 + minor * 100 + patch, (
        f"versionCode {code} does not pack {padpd.__version__}")
