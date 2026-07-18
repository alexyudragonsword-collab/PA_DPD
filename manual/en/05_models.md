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
