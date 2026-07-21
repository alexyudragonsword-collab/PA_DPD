@echo off
REM Build the padpd desktop app as a SINGLE .exe with Nuitka (slim only).
REM Run ON WINDOWS. Produces one file: packaging\build_nuitka\padpd-desktop.exe
REM
REM Unlike build_windows.bat (PyInstaller onedir, supports torch), this is
REM onefile and slim-only: torch is intentionally excluded because a onefile
REM extracts itself to %TEMP% on every launch and bundling several GB of torch
REM would make startup and size impractical. For the full (neural) build use
REM PyInstaller (build_windows.bat).
setlocal
cd /d %~dp0..

python -m pip install -e ".[gui-qt]" "nuitka[onefile]" || goto :err

python -m nuitka --standalone --onefile --assume-yes-for-downloads ^
  --enable-plugin=pyside6 ^
  --include-package=gui_qt --include-package=gui_core --include-package=padpd ^
  --include-module=matplotlib.backends.backend_qtagg ^
  --include-data-dir=manual=manual ^
  --include-data-dir=gui_qt/assets=gui_qt/assets ^
  --include-data-files=gui_qt/style_template.qss=gui_qt/style_template.qss ^
  --nofollow-import-to=streamlit,plotly,playwright,IPython,pytest,tkinter,PyQt5,PyQt6,torch,onnx,onnxscript,onnxruntime,nvidia,triton ^
  --windows-icon-from-ico=packaging/icon/padpd.ico ^
  --windows-console-mode=disable ^
  --company-name=padpd --product-name=padpd-desktop ^
  --output-dir=packaging/build_nuitka --output-filename=padpd-desktop.exe ^
  packaging/desktop_launcher_qt.py || goto :err

echo.
echo Build OK: packaging\build_nuitka\padpd-desktop.exe (single file)
goto :eof

:err
echo BUILD FAILED
exit /b 1
