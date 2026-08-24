"""The launcher icon, and that it is the desktop one.

The Android app shipped without an icon at first - no ``android:icon`` in
the manifest at all, so the launcher drew the stock robot next to an app
whose desktop build has had its own artwork since packaging was written.
These check the fix stays fixed: that every density is present, that the
manifest points at it, and - the part that actually matters - that the
picture is the same picture.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android" / "app" / "src" / "main" / "res"
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
DESKTOP_PNG = ROOT / "gui_qt" / "assets" / "padpd.png"
SOURCE = ROOT / "packaging" / "icon" / "source.png"

Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")

# density -> legacy icon edge in px. The adaptive layers are 108dp, of
# which the system mask keeps the middle 72dp.
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144,
             "xxxhdpi": 192}
ADAPTIVE = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324,
            "xxxhdpi": 432}


@pytest.mark.parametrize("bucket", sorted(DENSITIES))
def test_every_density_has_the_icon(bucket):
    folder = RES / f"mipmap-{bucket}"
    for name, want in (("ic_launcher", DENSITIES[bucket]),
                       ("ic_launcher_round", DENSITIES[bucket]),
                       ("ic_launcher_background", ADAPTIVE[bucket])):
        path = folder / f"{name}.png"
        assert path.is_file(), f"{path} missing; run packaging/make_icon.py"
        with Image.open(path) as im:
            assert im.size == (want, want), (path, im.size)


def test_the_manifest_asks_for_both_icons():
    """minSdk is 24, so the legacy PNG still has to be named: API 26+
    resolves the adaptive icon from mipmap-anydpi-v26, and 24-25 do
    not."""
    ns = "{http://schemas.android.com/apk/res/android}"
    app = ET.parse(MANIFEST).getroot().find("application")
    assert app.get(f"{ns}icon") == "@mipmap/ic_launcher"
    assert app.get(f"{ns}roundIcon") == "@mipmap/ic_launcher_round"


def test_the_adaptive_icon_uses_the_full_bleed_background():
    """The artwork reaches all four edges, so it belongs in the
    background layer where the launcher's own mask crops it. Scaled into
    the 72dp safe zone instead it would read as a small square badge on a
    flat field, which is not what the desktop shows."""
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        root = ET.parse(RES / "mipmap-anydpi-v26" / name).getroot()
        ns = "{http://schemas.android.com/apk/res/android}"
        background = root.find("background").get(f"{ns}drawable")
        assert background == "@mipmap/ic_launcher_background", name


def test_the_phone_icon_is_the_desktop_icon():
    """The point of the exercise: same artwork, not merely some artwork.

    Compared as pixels at a common size, with a tolerance, because the
    two are resampled separately and Pillow's resampling is not promised
    to be identical across versions. A different picture is nowhere near
    this threshold - the desktop tile is a dark field with a cyan mark,
    and anything else differs by tens of levels, not by two.
    """
    with Image.open(DESKTOP_PNG) as desktop, \
            Image.open(RES / "mipmap-xxxhdpi" / "ic_launcher_background.png") \
            as phone:
        size = (128, 128)
        a = np.asarray(desktop.convert("RGB").resize(size, Image.LANCZOS),
                       dtype=float)
        b = np.asarray(phone.convert("RGB").resize(size, Image.LANCZOS),
                       dtype=float)

    # The desktop PNG is corner-rounded to transparency and the phone's
    # background layer is not, so the corners genuinely differ. Compare
    # the inscribed centre, which both share.
    yy, xx = np.mgrid[0:size[0], 0:size[1]]
    centre = ((yy - 63.5) ** 2 + (xx - 63.5) ** 2) < 55 ** 2
    difference = np.abs(a - b)[centre].mean()
    assert difference < 6.0, (
        f"mean channel difference {difference:.1f}/255 - the phone icon is "
        f"not the desktop artwork; rerun packaging/make_icon.py")


def test_the_generator_is_the_only_source():
    """Both icons are generated from one file, so that replacing the
    artwork is one command and cannot update one platform and not the
    other."""
    assert SOURCE.is_file(), "packaging/icon/source.png is the artwork"
    text = (ROOT / "packaging" / "make_icon.py").read_text(encoding="utf-8")
    assert "mipmap-" in text and "gui_qt" in text
