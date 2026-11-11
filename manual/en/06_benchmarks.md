# 6. Performance Benchmarks

This chapter summarizes the platform's measured metrics on the synthetic
chain and on real measured data (4-core CPU, no GPU, single-seed environment;
full analysis in `docs/05_performance_summary.md`).

## 6.1 Synthetic Chain (WiFi 7-Style OFDM + Virtual ReferencePA)

| Bandwidth/modulation | EVM without DPD | After ILA-GMP DPD | ACLR improvement | Mask |
|---|---|---|---|---|
| 160 MHz / 1024-QAM | -19.0 dB | **-57.4 dB** | -31 → -55 dBc | FAIL → PASS |
| 320 MHz / 4096-QAM | -19.0 dB | **-64.2 dB** | -31 → -66 dBc | FAIL → PASS |

The 320 MHz row is the 10-symbol configuration; with the script's default
of 20 symbols it reads -58.0 dB (see the correction in the performance
summary, section 2.1).

Deep-compression operating point (drive 0.18): DPD alone reaches -37.7 dB
EVM / -40.6 dBc / mask PASS; **CFR (8 dB) + DPD** gives -36.9 dB /
-56.3 dBc / PASS, so CFR buys about 16 dB of out-of-band margin.

> Correction (2026-11-11): this used to say DPD alone only reaches
> -27.7 dB / FAIL because the peaks are non-invertible. That reading came
> from the second ILA iteration diverging; ILA now keeps the best observed
> iteration.

## 6.2 Real Data: PA Modeling (OpenDPD Datasets, Test-Set NMSE)

| Dataset | GMP-510 (classical) | Best neural | OpenDPD published |
|---|---|---|---|
| DPA_200MHz | -33.7 | **TCN-H16 -34.9** (464 parameters) | — |
| DPA_160MHz | -39.2 | DGRU-H8 -37.3 | GRU-H24 -38.4 |
| APA_200MHz (GaN) | -35.5 | DGRU-H23 -31.6 | GRU-H23 -43.5* |

TCN is the first neural model to surpass the classical GMP. *The published
APA value was, after systematic investigation, judged not reproducible from
public information (the same pipeline lands within 1 dB of the published
value on DPA_160).

## 6.3 Real Data: DPD Linearization (OpenDPD Convention)

DLA neural DPD (DGRU-H8, 486 parameters):

| Dataset | ACLR without DPD | After DLA DPD | OpenDPD published |
|---|---|---|---|
| DPA_200MHz | -30.6 | **-49.5** | — |
| DPA_160MHz | -34.5 | **-53.1** (clears the -52 acceptance line) | GRU -51.9 |

Classical ILA basis comparison (evaluated with the same neural surrogate,
ACLR_AVG dBc):

| Dataset | ILA-GMP-510 | **ILA-DDR r=1 (140 parameters)** |
|---|---|---|
| DPA_200MHz | -47.5 | **-49.1** |
| DPA_160MHz | -50.2 | **-51.6** |
| APA_200MHz (GaN) | -38.6 | **-47.1** (8.5 dB ahead) |

**Key surrogate re-evaluation experiment** (same DPD, only the evaluation
surrogate swapped): the GMP surrogate reads ACLR -26.2, the neural surrogate
reads **-38.56**, within 0.24 dB of the OpenDPD published value of
-38.80 — proving that polynomial surrogates cannot be trusted out of band.

## 6.4 Fixed-Point Deployment (DPA_200MHz Modeling, Test NMSE dB)

| Model | MAC/sample | float | W16 | W12 | W10 | W8 |
|---|---|---|---|---|---|---|
| **TCN-H16 (neural PTQ)** | **448** | -34.9 | -34.9 | **-34.8** | **-33.3** | -25.9 |
| DDR r=1 (fixed-point) | 560 | -34.0 | -33.9 | -27.7 | -16.9 | -4.9 |
| GMP-510 (fixed-point) | 1020 | -33.7 | -33.7 | -31.3 | -22.5 | -11.4 |

The TCN is **the most accurate in floating point + the most quantization
robust + the cheapest in compute**; the polynomial basis functions |x|^k have
a large dynamic range and collapse at low bit widths. ONNX export passes
numerical verification with max err ~1e-6.

![Bit-width sweep example on the Deployment page](assets/qt_deploy.png)

## 6.5 PA/DPD Co-Design (Synthetic Chain)

- Discrete Pareto (EVM spec -40 dB): the 43.4% PAE operating point reached by
  sequential design **hits the wall** (DPD only reaches -25.0); co-design
  meets the spec at -43.5 with drive 0.17 / 33.3% PAE / only 23 coefficients.
  (Correction 2026-11-11: previously 32.3% / -20.7 and 24.1% / -40.6. The
  EVMs were affected by ILA iteration divergence and the PAE used an older
  efficiency proxy; the wall has not moved.)
- Gradient optimization (spec -38 dB): a conservative drive of 0.08
  (11.8% PAE) is automatically optimized to 0.146 (**20.9% PAE**) while still
  meeting the spec. This PAE is the differentiable proxy, a different
  convention from the bullet above (by `drain_efficiency` the same two
  drives read 16.8% → 29.2%).

![Co-Design Pareto sweep](assets/qt_codesign.png)
