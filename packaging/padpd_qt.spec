# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the padpd PySide6 desktop GUI.
#
#   python -m PyInstaller --clean --noconfirm padpd_qt.spec
#
# PADPD_NO_TORCH=1 builds the slim variant (~400 MB onedir): all classical
# features (waveform/CFR/classical models/ILA DPD/quantize/coeff export)
# work; neural training, DLA and ONNX export report a missing-torch error
# in the GUI instead of crashing. Without it, torch (and on Linux its CUDA
# runtime libs, several GB) is bundled.

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821
NO_TORCH = os.environ.get("PADPD_NO_TORCH", "0") == "1"

# gui_qt/gui_core are repo-local (not pip-installed); make them importable
# for collect_submodules and for Analysis itself.
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# gui_qt.main loads pages via importlib, invisible to static analysis
hiddenimports = (
    collect_submodules("padpd")
    + collect_submodules("gui_core")
    + collect_submodules("gui_qt")
    + ["matplotlib.backends.backend_qtagg", "scipy.signal"]
)
excludes = ["streamlit", "plotly", "playwright", "IPython", "pytest",
            "tkinter", "PyQt5", "PyQt6"]
if NO_TORCH:
    excludes += ["torch", "onnx", "onnxscript", "onnxruntime",
                 "nvidia", "triton"]

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "desktop_launcher_qt.py")],  # noqa: F821
    pathex=[ROOT, os.path.join(ROOT, "src")],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "gui_qt", "style_template.qss"), "gui_qt"),
        (os.path.join(ROOT, "manual"), "manual"),
    ],
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="padpd-desktop",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="padpd-desktop",
)
