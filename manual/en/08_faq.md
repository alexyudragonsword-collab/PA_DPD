# 8. FAQ & Roadmap

## 8.1 Frequently Asked Questions

**Q: The neural-network / DLA choices say "Needs PyTorch", or there is no
Differentiable co-design page?**
Install torch with `pip install -e .[nn]` (the CPU build is sufficient). All
classical features work without it.

**Q: The Overview page says "OpenDPD not found"?**
Run `git clone --depth 1 https://github.com/lab-emi/OpenDPD.git` and point
the OpenDPD directory on the Data source page at its `datasets/` directory; or ignore it — the
synthetic ReferencePA does not depend on it.

**Q: After loading my own CSV, the AM-AM plot is a "cloud"?**
The input and output are not aligned. Reload with **automatic delay
alignment** enabled; if it is still scattered, check that the sample rate is
correct and that the I/Q columns are mapped properly.

**Q: EVM gets worse after DPD / DPD does not converge?**
The operating point is too deep (peaks enter the PA's non-invertible region).
Lower the drive, or enable CFR (target PAPR 7–8 dB) before running DPD; see
Section 5.4.

**Q: Can neural training inside the GUI reach paper-grade accuracy?**
The GUI defaults to epochs ≤ 100 and hidden ≤ 32, intended for interactive
experiments. For paper-grade reproduction use
`scripts/train_neural_pa.py --frame-length 200 ...` (recipe in
`docs/04_neural.md`); a GPU is recommended.

**Q: Why must an "evaluation surrogate" be selected for measured sources?**
Measured data has no demodulatable constellation ground truth, so the PA
output after DPD must be predicted by a PA model; and that surrogate should
be a neural model (polynomials are not trustworthy out of band, see
Section 6.3).

**Q: Where are sources, models and runs stored?**
In the user data directory: the repository root when running from source,
`%APPDATA%\padpd` (Windows) or `~/.local/share/padpd` (Linux) for the
packaged app. `workspace/` holds the source references, fitted models and
the project spec, `gui_runs/` the run records, `gui_prefs.json` the language
and theme. Deleting `workspace/` starts a fresh workspace.

**Q: Chart text is hard to read in the light theme / Chinese characters show
as boxes?**
Charts and the interface share one theme palette and switch together. Chinese
text needs a system CJK font: Windows ships one; on Linux install a package
such as `fonts-noto-cjk`.

**Q: A yellow "inputs changed" banner appeared above a result?**
An input was changed, or the source switched, after the run: the result
shown is still the previous one. Press "Run again" to compute with the new
inputs, or "Reproduce" to put the old ones back. Switching language or theme
or editing the spec does not raise it - those change how a result is
presented and judged, not the result.

## 8.2 Environment Requirements

| Scenario | Requirements |
|---|---|
| Full classical flow + GUI | A 4-core CPU and 8 GB RAM suffice |
| Interactive neural experiments (GUI) | Runs on CPU (minutes) |
| Paper-grade neural training / multi-seed | GPU recommended (CUDA build of torch) |

## 8.3 Roadmap and Boundaries

Completed: Phase 1 (classical chain) → 1.5 (OpenDPD benchmarking) → 2/2.5
(neural modeling and DLA) → 3 (fixed-point deployment and export) → 4
(co-design) → the desktop workbench and this manual (the web version was
retired on 2026-10-28).

Directions pending hardware/EDA availability (interfaces and scripts are
ready):

- **QAT** (quantization-aware training, to hold accuracy below W8) and
  multi-seed statistics — needs a GPU;
- **FPGA RTL bring-up** — sample-by-sample comparison using the reference
  vectors from Chapter 7;
- **Spectre-in-the-loop co-design** — replace the virtual PA with an EDA
  simulation loop;
- **SDR/instrument bench-in-the-loop DPD** — the `fit_measured` data-driven
  interface is already in place.

Engineering details, complete experiment records, and per-phase conclusions
are in the seven documents under the repository's `docs/` directory;
packaging details are in `packaging/README_packaging.md`.
