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

![Web workbench overview (dark theme)](assets/web_home_dark.png)

## 1.2 Two Graphical Interfaces

The platform ships two functionally isomorphic GUIs sharing the same compute
service layer and experiment registry:

| | Web workbench | Desktop app |
|---|---|---|
| Stack | Streamlit + Plotly (interactive zoom) | PySide6 + matplotlib |
| Launch | `streamlit run gui/app.py` | `python -m gui_qt.main` |
| Install | `pip install -e .[gui]` | `pip install -e .[gui-qt]` |
| Best for | Team sharing, remote access | Single-machine use, packaging as a Windows exe |

Experiments completed in either GUI (model fits, DPD runs, bit-width sweeps)
are written to the shared `gui_runs/` registry, and the other GUI's Compare
Runs page sees them immediately.

![Desktop Overview page](assets/qt_home.png)

## 1.3 Installation

Python 3.10–3.12 is required:

```bash
git clone <this repository>
cd PA_DPD
pip install -e .            # core (numpy/scipy/matplotlib)
pip install -e .[gui]       # + Web workbench (streamlit/plotly)
pip install -e .[gui-qt]    # + Desktop app (pyside6)
pip install -e .[nn]        # + neural features (torch, optional)
```

All classical features work without installing `torch` (waveforms / classical
modeling / ILA DPD / fixed-point export / discrete co-design); the neural
modeling, DLA, and gradient-optimization pages show a clear notice when torch
is missing.

For real measured data, clone the public OpenDPD dataset (about 55 MB):

```bash
git clone --depth 1 https://github.com/lab-emi/OpenDPD.git ../OpenDPD
```

## 1.4 Language and Theme

Both GUIs have language (Chinese / English) and theme (Dark / Light) switchers at
the **bottom of the sidebar**. The choice is saved in `gui_prefs.json` and
shared between the two GUIs — switch to English + Light in the Web workbench,
and the desktop app starts with the same look next time.

![Light theme + English UI example](assets/web_en_light.png)

## 1.5 A Five-Minute Tour

1. Open **Waveform Studio**, click "Generate waveform" with the default
   parameters, and inspect the PSD and PAPR;
2. Go to the **PA Modeling** page, pick "Synthetic ReferencePA" as the data
   source, and click "Fit model" (GMP by default, done in seconds) to get the
   NMSE and the fitted PSD;
3. Go to **DPD Lab** and simply click "Run DPD"; after about half a minute,
   review the before/after EVM/ACLR comparison and the mask badge;
4. On the **Compare Runs** page, check the two runs you just produced and
   click "Compare selected" to get bar charts;
5. On the **Deployment** page, check a model and run a "Bit-width sweep", then
   "Generate artifacts" to export integer coefficients and reference vectors.

The following chapters walk through each page in detail. Engineering details
(algorithm derivations, training recipes, complete experiment records) are in
the repository's `docs/` directory.
