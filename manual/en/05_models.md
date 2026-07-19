# 5. Models & Algorithms

The minimum background a user needs: what each model/algorithm is and when to
choose it. Derivations and implementation details are in
`docs/00_overview.md` and `docs/04_neural.md`.

## 5.1 Classical PA Behavioral Models (Closed-Form LS)

| Model | Characteristics | Best for |
|---|---|---|
| Saleh | Memoryless AM-AM/AM-PM analytic form | Teaching, rough simulation |
| Memory Polynomial (MP) | Diagonal Volterra, order x memory | Quick baseline |
| GMP | MP + cross lag/lead terms | **Golden baseline**, balanced accuracy/cost |
| DDR-Volterra | Dynamic deviation reduction, order-r truncation | **First choice as a DPD basis** (see 5.4) |

Three OpenDPD benchmark presets: MP-500, GMP-510, DDR-140 (the numbers are
actual parameter counts).

**Important**: these linear-in-parameters models must be fitted with the
closed-form least-squares solution, not SGD — the same GMP trained with SGD
loses more than 9 dB of ACLR (confirmed independently by OpenDPD and by this
project). The GUI's "Classical (LS)" path is the closed-form solution.

![Classical modeling: measured vs predicted PSD](assets/qt_modeling.png)

## 5.2 Neural PA Models (SGD Training)

| Backbone | Structure | Characteristics |
|---|---|---|
| GRU | Raw IQ sequence input | Baseline RNN |
| DGRU | 6-channel features (I, Q, amplitude, amplitude³, sin, cos) + feed-forward bypass | OpenDPD's workhorse architecture |
| TCN | Pointwise convolution + 4 dilated depthwise layers (d=1/2/4/8) | No recurrence, **most fixed-point/ASIC friendly** |

On measured data, TCN-H16 (464 parameters) achieves -34.9 dB NMSE, the first
neural model to beat the GMP-510 classical baseline; its quantization
robustness also far exceeds the polynomials (see Chapter 6).

## 5.3 The Two DPD Routes

- **ILA (indirect learning)**: identify the PA's post-inverse (LS with `y/G`
  as input and `x` as target) and move the post-inverse to the front end.
  Classical, seconds-fast, no torch required. Synthetic sources support
  closed-loop iteration; measured data uses the data-driven variant
  (`fit_measured`).
- **DLA (direct learning)**: the (neural) predistorter is cascaded with a
  **frozen neural PA surrogate** and trained end to end by gradient descent
  with `G·x` as the target. It requires fitting a neural surrogate first, but
  is markedly stronger on real PAs (e.g. GaN, where polynomials fail).

![PSD and constellation before/after DPD](assets/qt_dpd.png)

## 5.4 Three Empirically Validated Selection Rules

1. **DPD evaluation must use a neural surrogate**: polynomial surrogates
   distort out-of-band extrapolation, and their ACLR readings can be off by
   12 dB (APA measurements); a good global NMSE does not make the ACLR
   trustworthy.
2. **Accurate modeling ≠ good DPD**: DDR only matches GMP in forward
   modeling, yet as a DPD basis it wins across the board with 55% of the
   parameters (8.5 dB ahead on GaN). Choose the basis by directly evaluating
   the post-DPD metrics.
3. **CFR first at deep-compression operating points**: when peaks enter the
   PA's non-invertible region, DPD diverges; CFR trades a bounded EVM cost
   (clipping) for restored invertibility — only "CFR + DPD" achieves mask
   PASS.

## 5.5 Metric Conventions

| Convention | Metrics | Purpose |
|---|---|---|
| padpd native | Constellation-domain EVM (after demodulation), 802.11-style ACLR, transmit mask | Engineering acceptance |
| OpenDPD compatible | Spectral-domain EVM, ACLR_AVG (nperseg segmented Welch) | Cross-benchmarking against papers |

Numbers from the two conventions **must never be compared directly**; the GUI
selects the convention automatically per data source and labels it in the
results.

## 5.6 Pre-Tapeout: From Circuit Simulation to a PA+DPD Verdict

Before the PA exists in silicon, circuit simulation already provides
everything a first behavioral model needs:

| Simulation | Extract | Used as |
|---|---|---|
| Harmonic-balance power sweep | AM-AM / AM-PM table | static nonlinearity |
| S-parameters / PSS+PAC | input/output matching S21 | linear memory (FIR) |
| Envelope transient | input/output IQ pairs | import directly as Cadence CSV (Chapter 4) |

`padpd.pa.load_hb_pa` assembles the AM-AM/AM-PM table plus S21 tables
into a Wiener-Hammerstein model (FIR -> LUT nonlinearity -> FIR,
saturating beyond the table):

```python
from padpd.pa import load_hb_pa
pa = load_hb_pa("hb_amam.csv", "s21_in.csv", "s21_out.csv",
                fs=320e6, drive=0.14)   # a standard PAModel, plug and play
```

`scripts/import_hb_pa.py --demo` generates example CSVs and runs the
full prediction chain — demo result: GMP fits the imported PA to
NMSE -43.7 dB; predicted DPD takes EVM from -18.3 to **-48.1 dB** with
the mask going FAIL -> PASS. Sweeping `--drive` (with CFR and the
co-design tools) answers, before tapeout, **how much DPD this PA needs
and how much back-off passes spec**. A robustness sweep (perturb the
nonlinearity strength / memory depth by +/-20%) is recommended to
confirm the verdict does not flip. CSV column conventions are in
`docs/02_data_interface.md`, Section 8.

## 5.7 Adaptive / Online DPD and Field Drift

Batch DPD identifies once; a product must adapt continuously from a
loopback to track PA drift (temperature/supply/aging).
`padpd.dpd.AdaptiveDPD` recursively updates a GMP/DDR predistorter with
block RLS:

```python
from padpd.dpd import AdaptiveDPD
dpd = AdaptiveDPD(forget=0.6)      # smaller forget = faster, noisier tracking
dpd.warm_start(pa, x, blocks=6)    # converge from pass-through
dpd.update(pa, x)                  # update from each block's loopback
```

**Only RLS is offered**: the polynomial basis has a condition number of
~1e10, so LMS/NLMS (even whitened) diverge — the online counterpart of
"linear-in-params models need LS, not SGD".

`scripts/run_drift_study.py` quantifies the field value: as the PA
drifts cold->hot, a frozen batch DPD degrades to **-28.4 dB EVM** while
the adaptive one holds **-38.8 dB** (a 10.4 dB gap at full drift) —
the answer to "will DPD hold up in the field".

## 5.8 Two-Tone Memory Diagnostics: Sizing DPD Before Tapeout

A single-tone AM-AM/AM-PM sweep gives only the **static** nonlinearity
and is blind to memory: the same static curve fits both a memoryless and
a strongly dynamic PA. A **two-tone spacing sweep (delta-f)** is exactly
the large-signal characterization a pre-tapeout circuit simulator gives
cheaply (a harmonic-balance two-tone at a few tone spacings), making it
the natural bridge from Spectre to a DPD-complexity estimate.

The idea is not to force the two-tone to hand over full memory kernels,
but to **gauge memory strength from IM3 across several delta-f**, decide
how much DPD memory to reserve, and leave coefficient training to
measured data. `padpd.two_tone` reads two orthogonal memory signatures:

- **spacing dependence** — sweeping tone spacing sweeps the envelope
  frequency; IM3 that changes with spacing means memory (bias/matching
  electrical memory at MHz spacings, thermal memory at kHz). A memoryless
  nonlinearity gives IM3 flat in spacing.
- **upper/lower asymmetry** — a memoryless nonlinearity gives equal
  lower and upper IM3; any imbalance is a memory (complex/cross-term)
  signature, and its growth toward small spacing points at thermal memory.

The larger of the two condenses to a scalar **memory strength (dB)** —
roughly how many dB of IM3 a static model cannot reproduce.
`recommend_dpd_budget` maps it to a rough DPD size: how much diagonal
memory depth to reserve and whether GMP cross terms are worth carrying.

```python
from padpd.two_tone import sweep_two_tone, recommend_dpd_budget
r = sweep_two_tone(pa, [0.5e6,1e6,2e6,5e6,10e6,20e6,40e6], fs=320e6)
b = recommend_dpd_budget(r)          # {'memory_depth':3,'use_cross_terms':True,...}
# a circuit two-tone sweep feeds in directly:
from padpd.two_tone import memory_strength_from_table
r = memory_strength_from_table(spacings, im3_lower_dbc, im3_upper_dbc)
```

`scripts/run_two_tone_study.py` closes the loop: a memoryless Saleh reads
**0.0 dB** memory strength (reserve depth 1), a strongly dispersive PA
reads **3.0 dB** (reserve depth 3 + cross terms). Sweeping a real ILA-GMP
DPD over memory depth on a modulated 802.11 signal puts the EVM knee
exactly at the two-tone-predicted depth 3: a memoryless DPD reaches only
-19.7 dB, depth 2/3 bank the bulk (-27.9/-36.1 dB), and going deeper
(depth 4/6 -> -39.9/-41.5) yields diminishing returns. So the **cheap
two-tone sizes DPD memory before tapeout**, with the coefficients left to
measured-data training.
