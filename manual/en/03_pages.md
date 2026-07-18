# 3. Page-by-Page Guide

This chapter explains, page by page, "what to enter, what to click, what to
look at". The two GUIs are page-for-page isomorphic; screenshots show the
desktop app. In the Web version most controls sit in the left sidebar, but the
operations are identical.

## 3.1 Overview

What you see on launch: representative-result metric cards (all measured
numbers), an environment self-check (whether PyTorch is available, the
OpenDPD dataset path, counts of saved checkpoints and runs), and a
recent-experiments table. Use it to confirm the environment is ready and to
quickly review recent experiments.

![Overview page](assets/qt_home.png)

## 3.2 Waveform Studio

Generates 802.11be-style OFDM baseband waveforms.

- **Inputs**: bandwidth (20–320 MHz), QAM order (16–4096), number of OFDM
  symbols, random seed; optional **CFR peak clipping** and target PAPR (dB).
- **Actions**: click "Generate waveform"; click "Export .npz" when you want
  the waveform on disk.
- **Outputs**: metric cards for sample rate / FFT size and active subcarriers
  / PAPR (with CFR enabled, also the post-clipping PAPR and the EVM cost);
  four plot tabs — PSD, CCDF, transmit constellation, and time-domain
  envelope. With CFR enabled, the PSD/CCDF plots overlay the before/after
  clipping curves.

![Waveform Studio: PSD before/after CFR](assets/qt_waveform.png)

The exported `.npz` is in IQDataset format; it can be reloaded on the Data
Manager page or consumed by external toolchains.

## 3.3 Data Manager

Registers measured/simulated data as "data sources" for the modeling and DPD
pages to select.

- **OpenDPD directory**: enter the datasets path → "Scan directory" → pick a
  dataset → "Load dataset". The spec metadata (sample rate, bandwidth,
  modulation) is parsed automatically.
- **Open file**: Cadence CSV / MATLAB `.mat` / IQDataset `.npz`, recognized
  automatically by extension; you can enable **automatic delay alignment**
  (cross-correlation estimates the integer + fractional delay and corrects
  it — see Chapter 4).
- **Preview**: metric cards for sample rate, train/val/test sample counts,
  main bandwidth, and modulation, plus PSD and AM-AM/AM-PM preview plots for
  a quick check of data quality and alignment.

![Data Manager: loading the OpenDPD DPA_200MHz measured data](assets/qt_data.png)

## 3.4 PA Modeling

- **Data source**: "Synthetic ReferencePA" (with an adjustable drive
  operating point) or any registered measured source.
- **Classical (LS)**: choose MP / GMP / DDR, or an OpenDPD ~500-parameter
  preset (MP-500 / GMP-510 / DDR-140), with adjustable order and memory
  depth; the closed-form solution completes in seconds.
- **Neural (SGD)**: backbone (GRU / DGRU / TCN), hidden size, epochs;
  training runs on a background thread with a progress bar showing live
  validation NMSE. The GUI defaults to small parameter counts for interactive
  experiments; for paper-grade training use `scripts/train_neural_pa.py`.
- **Outputs**: metric cards for test NMSE and parameter count, measured vs
  predicted PSD, predicted AM-AM/AM-PM; "Save checkpoint" writes the model to
  disk. Fit results are automatically registered as a model (for the
  DPD/Deployment pages) and as a run (for the Compare Runs page).

![PA Modeling: GMP-510 fit result](assets/qt_modeling.png)

## 3.5 DPD Lab

- **Algorithms**: **ILA (classical)** — basis choice GMP-510 / DDR-140 /
  MP-500 or custom, identified by least squares; closed-loop iteration on
  synthetic sources, data-driven on measured sources. **DLA (neural)** —
  requires a neural surrogate trained beforehand on the modeling page; the
  predistorter is cascaded with the frozen surrogate and trained directly by
  gradient descent.
- **Automatic metric-convention switching**: synthetic sources use
  constellation EVM + the 802.11 transmit mask; OpenDPD sources automatically
  use their published convention (spectral-domain EVM / ACLR_AVG); other
  measured sources require selecting a PA surrogate model for evaluation.
- **Outputs**: four metric cards for pre/post-DPD EVM and ACLR (with a mask
  PASS/FAIL badge), before/after PSD comparison, before/after constellation
  comparison; the result is registered as a run.

![DPD Lab: ILA-GMP, EVM -19 → -59.8 dB, mask FAIL → PASS](assets/qt_dpd.png)

## 3.6 Compare Runs

A registry view of all runs (modeling / DPD / deployment): check several
entries → "Compare selected" generates grouped bar charts (NMSE / EVM /
ACLR); runs can be deleted or exported to JSON. The registry persists in
`gui_runs/` and is shared between the Web and desktop versions.

![Compare Runs: cross-experiment metric comparison](assets/qt_compare.png)

## 3.7 Deployment

- **Bit-width sweep**: check models and bit widths (W16–W8) → sweep curves +
  a table (including per-sample MACs and a GMAC/s estimate), with the
  floating-point baseline as a dashed line. Quantization is performed in a
  bit-true fixed-point simulation.
- **Export hand-off artifacts**: choose a model and coefficient bit width →
  generate the integer-coefficient JSON and the bit-true reference-vector CSV
  (for sample-by-sample comparison against RTL); neural models additionally
  export ONNX (with numerical verification).

![Deployment: bit-width vs accuracy sweep](assets/qt_deploy.png)

## 3.8 Co-Design

- **Discrete Pareto sweep**: given an EVM spec and a DPD coefficient budget,
  sweep 7 PA operating points, with a DPD complexity ladder search at each
  point; the red region in the plot marks infeasible (non-invertible)
  operating points, and two cards contrast "sequential design" with
  "co-design".
- **Differentiable gradient optimization**: inner closed-form LS-DPD + outer
  gradient with respect to drive, automatically pushing a conservative
  operating point toward the spec boundary; the trajectory plot shows the
  evolution of drive and EVM (requires PyTorch).

![Co-Design: Pareto sweep and feasible region](assets/qt_codesign.png)
