@echo off
REM Build the padpd desktop exe. Run ON WINDOWS from this directory:
REM   build_windows.bat            (full build, bundles torch if installed)
REM   build_windows.bat --no-torch (slim build ~400 MB, classical features only)
setlocal
cd /d %~dp0

set PADPD_NO_TORCH=0
if "%~1"=="--no-torch" set PADPD_NO_TORCH=1

python -m pip install -e "..[gui-qt]" pyinstaller || goto :err
if "%PADPD_NO_TORCH%"=="0" (
    python -m pip install -e "..[nn]" || goto :err
)

python -m PyInstaller --clean --noconfirm padpd_qt.spec || goto :err

echo.
echo Build OK: dist\padpd-desktop\padpd-desktop.exe
goto :eof

:err
echo BUILD FAILED
exit /b 1
