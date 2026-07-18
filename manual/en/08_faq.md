# 8. FAQ & Roadmap

## 8.1 Frequently Asked Questions

**Q: The neural modeling / DLA / gradient-optimization pages report that
PyTorch is missing?**
Install torch with `pip install -e .[nn]` (the CPU build is sufficient). All
classical features work without it.

**Q: The Overview page says "OpenDPD not found"?**
Run `git clone --depth 1 https://github.com/lab-emi/OpenDPD.git` and point
the Data Manager page at its `datasets/` directory; or ignore it — the
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

**Q: Why are experiments visible across both GUIs?**
The run registry (`gui_runs/`), the language/theme preferences
(`gui_prefs.json`), and the model checkpoints (`models/`) are all shared in
the repository directory.

**Q: Chart text is hard to read in the light theme / Chinese characters show
as boxes?**
The platform ships separate chart color schemes for the dark and light themes
and automatically selects a system CJK font (Microsoft YaHei on Windows; on
Linux install a package such as `fonts-wqy-zenhei`).

**Q: After switching the language, plots on desktop pages disappeared?**
Switching language/theme rebuilds the pages (labels are frozen at
construction time). Data sources, models, and runs are all preserved — click
"Run" once more to redraw.

## 8.2 Environment Requirements

| Scenario | Requirements |
|---|---|
| Full classical flow + GUI | A 4-core CPU and 8 GB RAM suffice |
| Interactive neural experiments (GUI) | Runs on CPU (minutes) |
| Paper-grade neural training / multi-seed | GPU recommended (CUDA build of torch) |

## 8.3 Roadmap and Boundaries

Completed: Phase 1 (classical chain) → 1.5 (OpenDPD benchmarking) → 2/2.5
(neural modeling and DLA) → 3 (fixed-point deployment and export) → 4
(co-design) → dual GUIs and this manual.

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
