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
dpd = AdaptiveDPD(forget=0.6)      # default method="rls"; smaller forget = faster/noisier
# the middle grounds are selectable too:
#   AdaptiveDPD(method="whitened", mu=0.5)       # amortized RLS (figure below)
#   AdaptiveDPD(method="apa", apa_k=4, mu=0.3)   # affine projection, tunable K
dpd.warm_start(pa, x, blocks=6)    # converge from pass-through
dpd.update(pa, x)                  # update from each block's loopback
```

**Plain LMS/NLMS is not offered**: the polynomial basis has a condition
number of ~1e10, so a scale-only gradient method diverges or stalls — the
online counterpart of "linear-in-params models need LS, not SGD". The
offered methods (`rls`, `whitened`, `apa`) all use the off-diagonal
covariance to clear that conditioning.

`scripts/run_lms_vs_rls.py` runs several online estimators from the same
pass-through start, on the same static PA and GMP basis, putting the
options "between RLS and NLMS" on one axis:

![Online DPD estimator spectrum: RLS / middle grounds / LMS·NLMS](assets/lms_vs_rls.png)

- **RLS** (O(N^2)/sample): inverts the covariance each block, convergence
  independent of the conditioning — reaches the least-squares floor in
  **one block** (EVM ~-46 dB steady state) and holds; **most robust**.
- **Whitened NLMS** (O(N^2)/sample, frozen whitening): a one-time Cholesky
  whitening (O(N^3)) of the warm-up covariance, then NLMS in the
  decorrelated domain. **Note: applying the dense whitening is still
  O(N^2)/sample — the same order as block-RLS, not cheaper** (an earlier
  "O(N)/sample" note was wrong). It settles very low on **stationary** data
  (-65..-68, even below the RLS LS floor) — but that is a per-sample,
  recency-weighted fixed point of the self-referential ILA loop, so it is
  **setup-specific, not a universal "whitened beats RLS"**; the whitening
  is frozen, so it goes stale when the signal statistics shift, whereas RLS
  re-estimates every block.
- **APA (affine projection, K=4, O(K^2*N)/sample)**: decorrelates over a
  K-sample window (a mini-RLS), climbing near RLS within a few blocks — the
  middle ground that actually **lowers per-sample cost** (small K), tunable
  (K=1 is NLMS, larger K approaches RLS).
- **NLMS** (O(N)/sample): survives but crawls and plateaus ~6-12 dB above
  RLS (the ill-conditioned modes barely move).
- **plain LMS** (O(N)/sample): diverges to NaN on the first block.

**The key point**: every method that clears the conditioning uses the
covariance's **off-diagonal** terms (whitening / APA / RLS). An honest
counter-example: naive **diagonal** preconditioning — dividing each column
by its own power — also diverges here, because it amplifies the weak,
collinear high-order columns. The killer on this basis is column
**correlation**, not scale, so fixing scale without decorrelating does not
help.

**Choosing**: default to **RLS** (most robust; at small N its O(N^2) is
nearly free, optionally at a low update rate). To push lower on a
**stationary** signal when compute is not the constraint -> **whitened
NLMS**. To genuinely **cut per-sample cost** -> **APA (small K)** or
transform-domain LMS (DCT-LMS, a fixed fast transform, O(N log N)). Large
N / hardware that still needs RLS accuracy -> **QR-RLS** (fixed-point-safe
numerics).

`scripts/run_drift_study.py` quantifies the field value: as the PA
drifts cold->hot, a frozen batch DPD degrades to **-28.4 dB EVM** while
the adaptive one holds **-38.8 dB** (a 10.4 dB gap at full drift) —
the answer to "will DPD hold up in the field".

**GUI entry**: the DPD Lab's "🔁 Adaptive / online DPD (drift tracking)"
panel picks the method (rls / whitened / apa), **bandwidth (20–320 MHz)**,
block count, drift span, forget, and the **APA projection order K**, and
plots the
adaptive-vs-frozen per-block EVM in one click; sweeping K (1→8) shows APA
converging from NLMS toward RLS live.

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

The decision runs in three stages — **measure IM3 -> condense to three
criteria -> gradient thresholds pick the size**:

![Two-tone memory -> DPD budget decision flow](assets/two_tone_budget.png)

- **Measure**: a two-tone sweep over several spacings reads the lower and
  upper IM3 (dBc). A memoryless PA gives equal, spacing-flat IM3; memory
  breaks that symmetry.
- **Criteria**: `spread = ptp(avg IM3 over spacing)` gauges diagonal
  (symmetric) memory; `asym = max|upper-lower|` gauges cross (complex)
  memory; asymmetry peaking at the smallest spacing flags thermal memory;
  `memory strength = max(spread, asym)`.
- **Decide**: `spread` maps through `<0.5/1.5/3/6` to memory depth
  `1/2/3/4/5`; `asym >= 1 dB` turns on GMP cross terms (`>= 4 dB` deepens
  them); a thermal flag adds a slow envelope-LPF branch; the result is a
  GMP recipe plus its coefficient count. The thresholds are a heuristic
  calibrated against a closed-loop DPD sweep — they set a floor to
  reserve, and the coefficients are still trained on measured data.

```python
from padpd.two_tone import sweep_two_tone, recommend_dpd_budget
r = sweep_two_tone(pa, [0.5e6,1e6,2e6,5e6,10e6,20e6,40e6], fs=320e6)
b = recommend_dpd_budget(r)          # {'memory_depth':3,'use_cross_terms':True,...}
# a circuit two-tone sweep feeds in directly:
from padpd.two_tone import memory_strength_from_table
r = memory_strength_from_table(spacings, im3_lower_dbc, im3_upper_dbc)
```

**GUI entry**: the Data Manager's "〰️ Two-tone memory" tab lets you
"Load example" or upload your own two-tone IM3 CSV and immediately see the
memory strength, the recommended memory depth / cross terms / coefficient
count, the IM3-vs-spacing curve, and the thermal-memory verdict (the
shipped `examples/two_tone_example.csv` reads 8.5 dB, depth 5, cross terms
needed, thermal suspected).

`scripts/run_two_tone_study.py` closes the loop: a memoryless Saleh reads
**0.0 dB** memory strength (reserve depth 1), a strongly dispersive PA
reads **3.0 dB** (reserve depth 3 + cross terms). Sweeping a real ILA-GMP
DPD over memory depth on a modulated 802.11 signal puts the EVM knee
exactly at the two-tone-predicted depth 3: a memoryless DPD reaches only
-19.7 dB, depth 2/3 bank the bulk (-27.9/-36.1 dB), and going deeper
(depth 4/6 -> -39.9/-41.5) yields diminishing returns. So the **cheap
two-tone sizes DPD memory before tapeout**, with the coefficients left to
measured-data training.

## 5.9 Piecewise Spline Models and LUT DPD: From Fit to Hardware Tables

MP/GMP describe the envelope nonlinearity with global powers |x|^k,
whose columns are strongly collinear (condition numbers of 1e7+ on
measured data): high orders go numerically ill-conditioned and
extrapolate wildly in the peak region. The spline family instead uses a
**locally-supported B-spline basis**: each basis function covers only a
few adjacent knot spans, and at any amplitude only degree+1 bases (4
for cubic) are non-zero.

![Knot placement and spline vs polynomial basis](../assets/spline_knots.png)

**The model family** (all linear in coefficients — one LS solve;
`from_signal()` places knots from data and then they are fixed, so the
models persist and serve as AdaptiveDPD templates):

| Model | Structure | Use case |
|---|---|---|
| `SplineMemoryPolynomial` | x(n-m)·B_j(\|x(n-m)\|) | default spline basis, SMP |
| `SplineGMP` | + lag/lead cross-envelope branches | PAs with asymmetric memory |
| `StateConditionedSpline` | + slow power states q_k and an (r,q) surface | thermal transients / long-term memory |
| `CoefficientScheduler` | coefficients interpolated across temperature/bias/power | scheduling across operating points |

**Knot placement**: `place_knots` supports uniform / quantile / hybrid
(default: quantiles for the bulk + a uniform tail above the 95th
percentile) — resolution where the data lives, with guaranteed knots at
the compression knee and peak region. **Estimation upgrades**:
`fit(x, y, regularization=..., smoothness=... (P-spline second-
difference penalty), weights=... (WLS))`; `basis_cond()` compares
conditioning directly (splines beat an order-7 MP by 100x or more).

**Runtime and deployment** — the spline's core selling point is that it
IS the hardware LUT:

1. `lut_from_model(model, n_entries)` samples each branch's complex
   gain into a uniform interpolation table; `LUTDPD` is the floating-
   point twin of that datapath (per-branch `np.interp` + endpoint
   clamping);
2. per sample and branch: one linear interpolation + one complex
   multiply (about 6 real MACs), independent of the knot count —
   compare `spline_mac_cost` with the coefficient-level `mac_cost` of
   a GMP;
3. `export_lut` writes integer table entries as JSON; `emit_lut_rtl`
   generates the **Verilog for LUT addressing + linear interpolation +
   delay lines + complex MAC**, with a self-checking testbench and an
   integer golden model; `verify_with_iverilog` proves it bit-true
   (errors=0 or it does not ship);
4. the bit-width axis (`bitwidth_sweep`) and the table-depth axis
   (`lut_sweep`) are orthogonal; the deploy page has one panel for
   each.

**Thermal / long-term memory**: `ThermalReferencePA` is a self-heating
virtual DUT — dissipated power drives the drift state through a
two-pole RC network, so cold and hot gains differ visibly under burst
stimuli (`burst_stimulus`). A plain SMP can only fit the average curve;
`StateConditionedSpline` adds the slow power states and improves NMSE
by about 8-11 dB (on both training and held-out bursts). The two-tone
budget (section 5.8) now also emits a spline recipe alongside the GMP
one (`spline_config` / `spline_runtime_macs`).

**Image distortion (widely-linear branches)**: TX I/Q imbalance turns
the transmit signal into `a*x + b*conj(x)`; through the PA the image
term both passes linearly and intermodulates with the main signal — a
phase-equivariant x-only basis is *structurally* unable to represent
an image, so modeling/DPD floors get pinned near the image rejection
ratio (IRR). `SplineMemoryPolynomial(conjugate=True)` appends
`conj(x(n-m))*B_j(|x(n-m)|)` branches (still linear in coefficients,
linearly independent of the direct branches, no identifiability fix
needed); `IQImbalancePA` is the matching TX-imbalance virtual DUT.
Measured at 0.3 dB / 3 deg (IRR about 30 dB): x-only DPD EVM stops at
-30.5 dB, widely-linear reaches **-52.8 dB (+22 dB)**. LUT extraction,
JSON export and the interpolation RTL all carry the conjugate flag
(hardware cost: one sign flip on the imaginary carrier), verified
bit-true under iverilog.

**Time-constant identification (characterization-driven state
config)**: `StateConditionedSpline`'s `state_alphas` no longer need
guessing — `padpd.gain_modulation.identify_gain_modulation(pa, fs)`
runs the classic step-response experiment (constant-envelope probe:
short full-power calibration burst -> long low-power settle -> step up
-> step down) and fits a 1..N-pole multi-exponential to the **complex**
gain trajectory (magnitude droop and AM-PM drift jointly), with
time-bin averaging against sample-rate noise and a leading guard
window that discards the electrical (matching-FIR) transient — without
it a perfectly static PA gets a fake droop. Extra poles must cut the
residual by >10% to be kept; heating and cooling are fitted separately,
and a tau ratio far from 1 flags trapping / bias hysteresis. On the
self-heating DUT with known truth (5/30 us) it identifies 4.9/29.1 us
(weights 0.58/0.42 vs truth 0.6/0.4); a state model configured from
the identified alphas lands within 1 dB of the truth-configured one.
The probe amplitude must sit in the compression region (default
a_hi=1.5 for unit-RMS baseband) — a small-signal probe is nearly blind
to gain modulation.
