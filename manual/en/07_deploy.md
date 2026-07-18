# 7. Deployment & Packaging

## 7.1 Fixed-Point Bit-Width Sweep

The Deployment page runs a **bit-true fixed-point simulation** of fitted
models: coefficients and activations are quantized symmetrically with
power-of-two scaling, and the NMSE is recomputed on the test data. Check the
models and bit widths (W16–W8) to obtain a "bit width vs accuracy" curve with
the floating-point baseline as a dashed line, used to set the hardware
bit-width boundary.

Empirical conclusions (see the tables in Chapter 6): the neural TCN can be
compressed to W10–W12 nearly losslessly; polynomial models are safe at W16
and degrade significantly below W12.

![Bit-width sweep](assets/qt_deploy.png)

## 7.2 FPGA/ASIC Hand-Off Artifacts

"Export hand-off artifacts" generates a three-piece set:

| Artifact | Contents | Purpose |
|---|---|---|
| Integer-coefficient JSON | Quantized integer coefficients + scale factors + structure description | RTL coefficient ROM |
| Reference-vector CSV | Bit-true input/output sample sequences | Sample-by-sample comparison in RTL simulation |
| ONNX (neural models) | Standard compute graph with numerical verification (max err ~1e-6) | Import into toolchains/accelerators |

Command-line equivalents: `python scripts/export_deploy.py`,
`scripts/quantize_dpd.py`, `scripts/quantize_neural_pa.py`.

## 7.3 Packaging the Desktop App as a Windows exe

**Recommended: build in the cloud with GitHub Actions (no local Windows
needed)** — run the **Build Windows EXE** workflow from the repo's
Actions page, then download `padpd-desktop-windows-slim.zip` (slim) or
`-full.zip` (with CPU torch) from the run's Artifacts; pushing a `v*`
tag builds both variants automatically and attaches them to a GitHub
Release. The cloud build includes a 20-second launch smoke test.

Alternatively, package locally on Windows with PyInstaller as an
installation-free directory (onedir):

```bat
cd packaging
build_windows.bat            :: full build (with torch, about 2 GB)
build_windows.bat --no-torch :: lite build (about 400 MB, all classical features available)
```

The output lands in `packaging/dist/padpd-desktop/` with the entry point
`padpd-desktop.exe`; copy the whole directory to distribute it.

**Key limitation: PyInstaller cannot cross-compile** — a Windows exe must be
built on Windows (this repository has verified building and launching on
Linux with the same spec file).

| | Lite build --no-torch | Full build |
|---|---|---|
| Waveforms / CFR / data / classical modeling / ILA / fixed-point export / discrete co-design | ✅ | ✅ |
| Neural modeling / DLA / ONNX / gradient optimization | ❌ (notice shown in the UI) | ✅ |
| Size | ~400 MB | ~2 GB |

For the full build, install the **CPU build of torch** first
(`pip install torch --index-url https://download.pytorch.org/whl/cpu`) to
avoid packing several GB of CUDA runtime libraries into the bundle.

Remaining details (antivirus false positives, missing DLLs, Chinese fonts)
are covered in `packaging/README_packaging.md`.

## 7.4 Deploying the Web Version

The Web version is positioned as a team workbench, not an exe: on any machine
with Python, run `pip install -e .[gui] && streamlit run gui/app.py`; add
`--server.address 0.0.0.0` for LAN sharing. Both versions share the
`gui_runs/` registry.
