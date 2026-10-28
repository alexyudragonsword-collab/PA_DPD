# 3. Page-by-Page Guide

This chapter explains, page by page, what to enter, what to press and what
to read. Every experiment page uses the same template, inputs on the left
and results on the right; the template comes first, then each page's own
inputs and how to read its results.

## 3.0 The Experiment Page

- **Inputs** stack in one column by group, and only the ones that apply to
  the current choices are shown (with ILA selected, the DPD page shows no
  neural-network inputs; on a synthetic source it shows no PA surrogate).
  Rarely used inputs fold under "Advanced". A hidden input does not reach
  the run and is not written into its record.
- **Verdict tiles** give the value, the limit, the margin and "passed" or
  "failed", with a coloured stripe that says the same; where there is a
  baseline (no DPD, for instance) its value and verdict are shown too.
  Limits come from the project spec in the top bar; after the spec is
  edited, results already on screen are **re-judged immediately**, without
  re-running. A tile without a limit is a reading and says neither.
- **Charts**: hover to read every curve at the cursor; drag a rectangle to
  zoom, double-click to reset. A right-axis quantity goes to a smaller plot
  underneath that shares the x axis, rather than onto a second y scale.
- **Provenance** at the bottom: run id, inputs, source and time taken.
  "Reproduce" puts those inputs back into the form; "Open in Compare" opens
  the Compare Runs page with the two newest runs of the same kind picked.
- **Stale banner**: if an input is changed or the source is switched after
  a run, a yellow banner says the result below is still the previous one.
  Press "Run again" or "Reproduce".

## 3.1 Overview

The four workflow steps (Data source → PA model → DPD → Deployment) with
their current state (active source, number of models, number of runs),
each one click away; the project spec; the studies; an environment check
(PyTorch, OpenDPD dataset path); and the most recent runs.

![Overview page](assets/qt_home.png)

## 3.2 Waveform

Generates an 802.11be-style OFDM baseband waveform.

- **Inputs**: bandwidth (20–320 MHz), modulation (256/1024/4096-QAM),
  number of OFDM symbols; optional **CFR clipping** with a target PAPR (dB);
  the random seed is under Advanced.
- **Results**: sample rate, FFT size and active subcarriers, PAPR (with CFR
  on, also the PAPR after CFR and its EVM cost); Spectrum, CCDF,
  Constellation and Time domain tabs, with before/after CFR overlaid.
- **Export .npz** writes an IQDataset that the Data source page can load.

![Waveform: spectrum before and after CFR](assets/qt_waveform.png)

## 3.3 Data source

The workspace's sources, with "●" marking the active one (double-click or
"Make active" to switch; the top bar can switch it too). A source is kept as
a **reference** - a synthetic source as its generator parameters, a measured
one as its file path and loader - so it survives a restart and is loaded on
first use.

- **New synthetic source**: bandwidth, modulation, symbols, CFR, PA drive
  and TX front-end impairments (IQ imbalance / LO leakage / C-IM3); "Add
  synthetic source" makes it the active source.
- **Import measured**: open a Cadence CSV / MATLAB `.mat` / IQDataset
  `.npz` (recognised by suffix, with optional **Auto delay alignment**, see
  Chapter 4); pick a dataset under the OpenDPD directory and "Load dataset";
  "Load complete-source example" loads the demo container with all five
  capture groups.
- **Preview**: sample rate, train/val/test sample counts, main bandwidth,
  modulation; input/output spectrum and AM-AM/AM-PM; for a complete source,
  the capture groups it carries and "Run complete-source tools" (tau
  identification, state spline, RX calibration, scheduler).

![Data source: the complete-source example and its capture groups](assets/qt_data.png)

## 3.4 PA model

Fits a PA behavioral model on the active source.

- **Classical (LS)**: type (MP / GMP / DDR, the OpenDPD ~500-parameter
  presets MP-500 / GMP-510 / DDR-140, the spline family, ...), nonlinear
  order, memory depth; closed-form, seconds.
- **Neural network**: architecture (DGRU / GRU / TCN), hidden units, epochs;
  while training, the status line shows the epoch and the validation NMSE.
  Without PyTorch a notice appears under the choice. The GUI defaults are
  small for interactive use; for paper-grade training use
  `scripts/train_neural_pa.py`.
- **Results**: test NMSE and parameter count; measured vs predicted
  spectrum and AM-AM/AM-PM; a training curve for neural models.
- **Models in the workspace**, at the bottom of the page, lists every
  fitted model with its type, source, NMSE, run id and whether it is saved.
  Models are saved to the workspace automatically; they are the DPD page's
  evaluation surrogates and the Deployment page's inputs.

![PA model: a GMP-510 fit](assets/qt_modeling.png)

## 3.5 DPD

Identifies a predistorter on the active source and judges it against the
spec.

- **Algorithm**: **ILA · classical LS** - pick a basis (GMP-510 / DDR-140 /
  MP-500 / GMP / DDR / MP / the spline family); **DLA · neural direct
  learning** - needs a neural PA surrogate; the predistorter is trained by
  gradient through the frozen surrogate.
- **PA surrogate** appears only when it is needed: for DLA, or when the
  active source is measured (measured data has no demodulable ground
  truth, so the post-DPD output has to be predicted by a model, which
  should be neural; see Section 6.3).
- **Verdicts**: EVM, ACLR worse side, and the **emission-mask out-of-band
  margin** (the smallest distance below the 802.11 template; positive
  passes), each against its no-DPD baseline; the table gives lower and upper
  ACLR and the improvement. The evaluation convention follows the source
  (constellation EVM on a synthetic source, the published convention on an
  OpenDPD one) and is stated under the result.

![DPD: ILA GMP-510, EVM -19.0 → -59.8 dB, mask margin -7.2 → +18.7 dB](assets/qt_dpd.png)

> The mask margin counts only the band outside the template's first break.
> The PSD is normalised to its in-band peak, which sits exactly on the
> template's 0 dB, so counting the channel itself would give every signal a
> margin of 0.0.

## 3.6 Deployment

- **Bit-width sweep**: tick workspace models and word lengths (W16–W8) for a
  bit-true fixed-point simulation. A verdict tile per model gives the
  **narrowest word length with an NMSE loss of at most 1 dB**; the curve
  and table include MACs per sample and a GMAC/s estimate, with the float
  baseline dashed. "Also sweep LUT depth" adds a lookup-table depth sweep
  for spline/MP models that have a gain curve.
- **Export hand-off files…**: pick a model, a word length and a directory
  to write integer coefficients (JSON) and bit-true reference vectors (CSV);
  classical models also get `rtl/dpd_mac.v`, checked bit for bit with Icarus
  Verilog, and neural models an ONNX export with a numerical check.

![Deployment: bit width vs accuracy](assets/qt_deploy.png)

## 3.7 Studies

Each study is a page of its own, on the same template.

- **Gain modulation**: a constant-envelope step probe identifies the
  thermal/trap time constants and configures a state-conditioned spline with
  the identified alpha; the virtual DUT is Self-heating (thermal) or Static
  control (static).
- **Adaptive tracking**: block-by-block EVM of an adaptive DPD (RLS /
  whitened RLS / APA) against a frozen batch DPD on a drifting PA.
- **Front-end 3-loop**: a drifting PA with TX image and LO leakage and a
  contaminated observation loopback; de-embedding only against all three
  loops (QMC + de-embedding + adaptive DPD). The raw loopback fails at full
  drift with a positive EVM; it is stated in the callout instead of drawn,
  where it would flatten the other two curves.
- **Co-Design**: sweeps the PA operating point for a given EVM target and
  DPD coefficient budget; shaded regions are infeasible (non-invertible or
  over budget), and two tiles compare "Sequential design (efficiency-first)"
  with "Co-design (best efficiency in budget)". Seconds to a minute,
  depending on the machine.
- **Differentiable co-design**: closed-form LS-DPD inside, gradient on the
  drive outside, for the best efficiency under the EVM constraint (needs
  PyTorch; the page does not appear without it).
- **Two-tone diagnosis**: reads an IM3-versus-tone-spacing table and, before
  any DPD is trained, estimates the memory strength and a memory depth; an
  empty path uses the built-in example.

![Co-Design: Pareto sweep and the feasible region](assets/qt_codesign.png)

## 3.8 Compare Runs

Only runs of **one kind** are compared (PA model / DPD / Deployment),
because metrics of different kinds of run do not convert into each other.
Ticking two or more draws the chart; the table lists each run's metrics, and
"Inputs that differ" lists only the inputs whose values differ, which is
where the difference came from. Runs can be deleted or exported as JSON.
Runs are kept in `gui_runs/` and survive a restart.

![Compare Runs: two PA model runs and the inputs that differ](assets/qt_compare.png)
