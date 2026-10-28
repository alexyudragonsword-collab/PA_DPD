#!/usr/bin/env python3
"""Regenerate the desktop screenshots in manual/assets/.

Drives the real window offscreen on a throwaway workspace, runs each
experiment with the inputs the manual describes, and saves 1280x860
grabs as palette PNGs (the manual ships inside the APK too, so size
matters). Every number visible in a screenshot is one this script just
computed.

    QT_QPA_PLATFORM=offscreen python scripts/make_gui_screenshots.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = ROOT / "manual" / "assets"


def main():
    from PIL import Image
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    app.setStyle("Fusion")
    from gui_qt import common
    common.save_prefs = lambda *a, **k: None       # leave the user's alone
    common.PREFS.update(lang="zh", theme="light")
    common.reset_state(Path(tempfile.mkdtemp(prefix="padpd_shots_")))
    from gui_qt.main import MainWindow

    win = MainWindow()
    win.resize(1280, 860)
    win.show()

    def settle(page=None):
        if page is not None and hasattr(page, "wait"):
            page.wait()
        for _ in range(50):
            app.processEvents()
            time.sleep(0.01)

    def run(pid, **values):
        win.navigate(pid)
        page = win.pages[pid]
        page.form.set_values(values)
        page.run()
        settle(page)
        if page.error:
            raise RuntimeError(f"{pid}: {page.error}")
        return page

    def shot(name):
        settle()
        path = OUT / f"{name}.png"
        tmp = path.with_suffix(".raw.png")
        win.grab().save(str(tmp))
        Image.open(tmp).convert("RGB").quantize(
            colors=256, method=Image.Quantize.MEDIANCUT).save(
                path, optimize=True)
        tmp.unlink()
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")

    run("waveform", bw=160, cfr=True, papr=8.0)
    shot("qt_waveform")

    run("pa_model", family="classical", type="GMP", order=5, memory=4)
    run("pa_model", family="classical", type="GMP-510 (OpenDPD)")
    shot("qt_modeling")

    run("dpd", algo="ILA", basis="GMP-510 (OpenDPD)")
    shot("qt_dpd")

    ws = common.state().workspace
    win.workspace_changed()
    run("deploy", models=tuple(ws.models), bits=(16, 14, 12, 10, 8))
    shot("qt_deploy")

    run("codesign")
    shot("qt_codesign")

    win.pages["pa_model"].open_compare.emit("pa_model")
    shot("qt_compare")

    win.navigate("sources")
    src = win.pages["sources"]
    synthetic = ws.active_source
    src.add_example()
    settle(src)
    shot("qt_data")
    ws.set_active(synthetic)
    win.workspace_changed()

    win.navigate("overview")
    shot("qt_home")

    win.set_lang("en")
    win.set_theme("dark")
    win.navigate("dpd")
    shot("qt_en_dark")

    win.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main()
