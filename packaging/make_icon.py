"""Generate the app icon assets from the source artwork.

Takes ``packaging/icon/source.png`` (a square tile) and emits:

- ``packaging/icon/padpd.ico`` — multi-resolution Windows icon (16..256),
  used by the PyInstaller EXE (see ``padpd_qt.spec``);
- ``gui_qt/assets/padpd.png`` — a 512px RGBA icon bundled with the app and
  set as the window / taskbar icon (see ``gui_qt/main.py``).

The outer square corners are rounded to transparency so the tile reads as
a proper app icon instead of a black square. Re-run after replacing
``source.png``:  ``python packaging/make_icon.py``
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "icon" / "source.png"
ICO = HERE / "icon" / "padpd.ico"
PNG = ROOT / "gui_qt" / "assets" / "padpd.png"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
CORNER_FRAC = 0.16          # rounded-corner radius as a fraction of size


def rounded(img: Image.Image, size: int) -> Image.Image:
    """Square-resize to ``size`` and clip to a rounded-rect alpha mask."""
    im = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * CORNER_FRAC), fill=255)
    im.putalpha(mask)
    return im


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} — drop the source artwork there")
    src = Image.open(SRC)
    if src.width != src.height:                       # center-crop to square
        s = min(src.size)
        left, top = (src.width - s) // 2, (src.height - s) // 2
        src = src.crop((left, top, left + s, top + s))

    PNG.parent.mkdir(parents=True, exist_ok=True)
    rounded(src, 512).save(PNG)
    print(f"wrote {PNG}")

    base = rounded(src, 256)
    base.save(ICO, sizes=[(s, s) for s in ICO_SIZES])
    print(f"wrote {ICO} ({', '.join(str(s) for s in ICO_SIZES)})")


if __name__ == "__main__":
    main()
