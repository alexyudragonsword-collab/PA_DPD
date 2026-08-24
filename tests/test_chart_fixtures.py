"""Chart fixtures: real specs, frozen, for the JVM screenshot tests.

The Kotlin renderer's golden images are only worth having if what they
render is what Python actually produces. Hand-writing a ChartSpec in
Kotlin would test the renderer against a fiction - and would quietly
omit the awkward cases, which are the ones a renderer gets wrong: a log
x axis, a twin y axis, a categorical x axis, a NaN gap in a bar series,
a shaded mask band.

``padpd_mobile/gallery.py`` already supplies deterministic inputs for
all fourteen chart kinds, precisely so the on-device gallery can
exercise every drawing primitive. Dumping those is therefore free and
keeps one source of truth rather than two.

Regenerate after changing chart_spec.py or gallery.py::

    PADPD_UPDATE_FIXTURES=1 python -m pytest tests/test_chart_fixtures.py

and commit the result - the golden images will change with it, which is
the point: a spec change that alters a picture should show up as an
altered picture.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
MOBILE = ROOT / "android" / "app" / "src" / "main" / "python"
FIXTURES = (ROOT / "android" / "app" / "src" / "screenshotTest"
            / "resources" / "chart-fixtures")

if str(MOBILE) not in sys.path:
    sys.path.insert(0, str(MOBILE))

UPDATE = os.environ.get("PADPD_UPDATE_FIXTURES") == "1"


def _entries():
    from padpd_mobile import gallery
    return [e["id"] for e in gallery.listing()]


def _build(entry_id: str) -> dict:
    """One fixture: the spec, and every array it references."""
    from padpd_mobile import chart_spec, gallery
    name, args, kwargs = gallery.chart_args(entry_id)
    spec, blobs = chart_spec.build(name, *args, lang="zh", **kwargs)
    return {
        "id": entry_id,
        "chart": name,
        "spec": spec,
        # float32 little-endian, the same encoding api._put_blob uses and
        # the same one Kotlin's Blobs.decode expects. Base64 because the
        # fixture is one file per chart and a sidecar per array would be
        # sixty files for fourteen charts.
        "blobs": {
            key: base64.b64encode(
                np.ascontiguousarray(
                    np.asarray(arr, dtype=np.float64).ravel(),
                    dtype=np.float32).tobytes()).decode("ascii")
            for key, arr in blobs.items()
        },
    }


def _decode(b64: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype="<f4")


@pytest.mark.parametrize("entry_id", _entries())
def test_fixture_matches_what_python_builds_today(entry_id):
    """The guard against the fixture drifting away from chart_spec.py.

    Values are compared with a tolerance rather than byte-for-byte. The
    fixture is generated on one machine and checked on another - CI also
    runs a job pinned to numpy 1.23.3, the Android version ceiling - and
    a last-ulp difference in a PSD is not a contract change. The spec
    itself is compared exactly: labels, limits and axis assignments are
    the contract, and they are not subject to rounding.
    """
    path = FIXTURES / f"{entry_id}.json"
    built = _build(entry_id)

    if UPDATE:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(built, ensure_ascii=False, indent=1,
                                   sort_keys=True) + "\n",
                        encoding="utf-8")

    assert path.is_file(), (
        f"missing fixture {path.name}; regenerate with "
        f"PADPD_UPDATE_FIXTURES=1")
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored["chart"] == built["chart"]
    assert stored["spec"] == built["spec"], (
        f"{entry_id}: the chart spec changed; regenerate the fixtures and "
        f"the golden images with it")
    assert set(stored["blobs"]) == set(built["blobs"]), entry_id
    for key, b64 in built["blobs"].items():
        want, got = _decode(stored["blobs"][key]), _decode(b64)
        assert want.shape == got.shape, (entry_id, key)
        # NaN is meaningful here - the bar chart uses it for a missing
        # metric, which is one of the cases the renderer must handle.
        assert np.allclose(want, got, rtol=1e-5, atol=1e-8,
                           equal_nan=True), (entry_id, key)


def test_every_drawing_primitive_is_covered():
    """The fixtures exist to exercise the renderer, so they have to reach
    every branch of it. Losing a primitive would leave a whole drawing
    path with no picture and no complaint."""
    kinds, features = set(), set()
    for entry_id in _entries():
        for panel in _build(entry_id)["spec"]["panels"]:
            kinds.add(panel["kind"])
            if panel.get("xscale") == "log":
                features.add("log x")
            if panel.get("yscale") == "log":
                features.add("log y")
            if panel.get("x_ticks"):
                features.add("categorical x")
            if panel.get("vspans"):
                features.add("shaded span")
            if panel.get("hlines"):
                features.add("threshold line")
            if any(s.get("axis") == "right" for s in panel["series"]):
                features.add("twin axis")
            if panel.get("aspect_equal"):
                features.add("equal aspect")
    assert kinds == {"line", "scatter", "bar"}, kinds
    assert features == {"log x", "log y", "categorical x", "shaded span",
                        "threshold line", "twin axis", "equal aspect"}, (
        f"a drawing feature lost its fixture: {sorted(features)}")
