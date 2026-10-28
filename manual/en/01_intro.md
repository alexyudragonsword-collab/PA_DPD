# 1. Introduction & Quick Start

## 1.1 What is padpd

**padpd** is a **WiFi 7 (802.11be) power amplifier (PA) + digital predistortion
(DPD) AI-assisted R&D platform** for RFIC / Analog IC teams. It packs the
complete chain — from waveform generation to FPGA/ASIC hand-off — into a
single Python project:

- **802.11be-style waveforms**: 20–320 MHz bandwidth, 16–4096-QAM OFDM, with
  CFR (crest factor reduction) peak clipping;
- **PA behavioral modeling**: two tracks — classical (Saleh / Memory
  Polynomial / GMP / DDR-Volterra) and neural (GRU / DGRU / TCN);
- **Digital predistortion**: ILA (classical least squares) and DLA (neural
  direct learning);
- **System metrics**: constellation EVM, ACLR, transmit spectral mask,
  AM-AM/AM-PM, CCDF, plus a built-in OpenDPD paper-compatible metric
  convention for cross-benchmarking;
- **Fixed-point deployment**: bit-true bit-width sweeps, neural PTQ,
  ONNX / integer-coefficient / reference-vector export;
- **PA/DPD co-design**: discrete Pareto sweeps and differentiable
  gradient-based optimization.

Representative results on real measured data: on the DPA_160MHz dataset, DLA
neural DPD improves ACLR from -34.5 to **-53.1 dBc** (clearing the -52 dBc
acceptance line); a TCN neural PA model reaches **-34.9 dB** NMSE with 464
parameters, beating the classical GMP baseline of roughly 500 parameters.

![The desktop workbench: the DPD page, judged against the project spec](assets/qt_dpd.png)

## 1.2 The Graphical Interface

The graphical interface is a PySide6 desktop workbench
(`python -m gui_qt.main`), which can also be packaged as a Windows exe
(Chapter 7); the same compute layer and screen contract drive the Android
app.

The window has three parts:

- **The left rail** follows the workflow: Waveform → Data source → PA model
  → DPD → Deployment; then the studies (Gain modulation, Adaptive tracking,
  Front-end 3-loop, Co-Design, Differentiable co-design, Two-tone diagnosis)
  and analysis (Compare Runs, User Manual).
- **The top bar** keeps three things in view, because every result is read
  against them: the **active data source**, the number of **PA models** in
  the workspace, and the **project spec** (EVM and ACLR limits; the emission
  mask is the 802.11 template). Click the source to switch it, click Spec to
  edit it.
- **An experiment page** has its inputs on the left (only the ones that
  apply to the current choices) and its results on the right, in this
  order: verdict tiles against the spec (value, limit, margin, passed or
  failed, and the baseline), supporting numbers, charts you can hover to
  read and drag to zoom, the before/after table, and where the result came
  from (run id, inputs, source, time taken).

Sources, fitted models and the spec are kept in a workspace and survive a
restart; every run is recorded in `gui_runs/` and can be compared side by
side on the Compare Runs page.

![Desktop Overview page](assets/qt_home.png)

> Earlier versions also had a Streamlit web GUI (`gui/`), retired on
> 2026-10-28: the two front ends were written by hand and had drifted apart
> (the same DPD page took 21 inputs on the desktop and 12 on the web). There
> is now one screen contract (`gui_core/experiments.py`), shared by the
> desktop and Android.

## 1.3 Installation

Python 3.10–3.12 is required:

```bash
git clone <this repository>
cd PA_DPD
pip install -e .            # core (numpy/scipy/matplotlib)
pip install -e .[gui-qt]    # + desktop workbench (pyside6/pyqtgraph)
pip install -e .[nn]        # + neural features (torch, optional)
python -m gui_qt.main
```

All classical features work without installing `torch` (waveforms /
classical modeling / ILA DPD / fixed-point export / discrete co-design); the
neural model and DLA choices show a notice under the input, and the
Differentiable co-design page does not appear.

For real measured data, clone the public OpenDPD dataset (about 55 MB):

```bash
git clone --depth 1 https://github.com/lab-emi/OpenDPD.git ../OpenDPD
```

## 1.4 Language and Theme

The right end of the top bar switches the language (Chinese / EN) and the theme
(Light / Dark). The switch happens **in place**: results on screen are not
lost, only presented again in the other language. The choice is saved in
`gui_prefs.json` and used at the next launch.

![English UI, dark theme](assets/qt_en_dark.png)

## 1.5 A Five-Minute Tour

1. Open **Data source**: the workspace starts with a synthetic source
   (ReferencePA, 160 MHz / 1024-QAM, drive 0.14), already active;
2. On **PA model**, press Run with the default GMP (seconds) to get the test
   NMSE; the model is saved to the workspace;
3. On **DPD**, press Run (a few seconds) and read the three verdict tiles:
   EVM, ACLR worse side and emission-mask out-of-band margin, each with the
   no-DPD baseline;
4. Change an input (the basis, say): a yellow "inputs changed" banner
   appears above the result, which is still the previous one; press
   Reproduce to put the old inputs back, or Run again;
5. Press "Open in Compare" under the result to line up runs of the same
   kind and see which inputs differ;
6. On **Deployment**, tick a model, run the bit-width sweep, then "Export
   hand-off files…".

The following chapters walk through each page in detail. Engineering details
(algorithm derivations, training recipes, complete experiment records) are in
the repository's `docs/` directory.
