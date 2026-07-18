# 4. Data Interfaces

All external data is unified internally as an **IQDataset**: a pair of
sample-aligned complex baseband sequences (PA input `x`, output `y`) + sample
rate + metadata. The GUI Data Manager page and the `padpd.data` loaders accept
the following four sources.

## 4.1 General Conventions

- **Complex baseband IQ**: equivalent-baseband (envelope) signals, no
  carrier;
- **Sample alignment**: `x[n]` and `y[n]` must correspond to the same time
  instant (see the alignment tool in 4.6);
- **Sample rate**: at least 4x the channel bandwidth is recommended, so that
  spectral regrowth up to 5th order remains observable;
- **Amplitude units**: arbitrary (volts or normalized); the gain relationship
  is preserved in `y/x`.

## 4.2 OpenDPD Dataset Directory (Recommended)

Load a complete [OpenDPD](https://github.com/lab-emi/OpenDPD) dataset folder;
the `spec.json` metadata is parsed automatically (sample rate, main/sub
channel bandwidths, modulation, `nperseg`, etc. — these are required inputs
for computing the OpenDPD-compatible metrics). Two directory formats are
supported:

| Format | Files | Notes |
|---|---|---|
| split_csv | `{train,val,test}_{input,output}.csv` (each with I,Q columns) | Pre-split, aligned sample by sample |
| single_csv | `data.csv` (four columns: I_in,Q_in,I_out,Q_out) | Contiguous 0.6/0.2/0.2 split |

GUI operation: on the Data Manager page, enter the directory → scan → select
→ load. The datasets are pre-aligned, so no further delay alignment is
needed.

![Loading an OpenDPD dataset on the Data Manager page](assets/qt_data.png)

## 4.3 Cadence Envelope CSV

A single CSV with a header row; column names are case-insensitive:

```csv
time,i_in,q_in,i_out,q_out
0.000000000000e+00,0.1234,-0.0567,0.1180,-0.0611
1.562500000000e-09,0.1301,-0.0432,0.1245,-0.0489
```

`time` must be uniformly sampled (the sample rate is inferred from it).
Cadence Envelope exports usually contain link delay, so **enabling automatic
delay alignment is recommended**.

## 4.4 MATLAB .mat

Variable convention: `x` (complex vector, PA input), `y` (complex vector, PA
output), `fs` (scalar, Hz). On the MATLAB side:
`save('cap.mat','x','y','fs')` (v5/v7 format).

## 4.5 IQDataset .npz (Internal Format)

Stored via `numpy.savez_compressed` with `x`, `y`, `sample_rate_hz`, and
`meta`. This is the format exported by Waveform Studio; for synthetic data,
`meta` records the bandwidth, QAM order, seed, etc., guaranteeing
reproducibility.

## 4.6 Automatic Delay Alignment

Measured/EDA data often contains an unknown integer delay, a fractional delay
(DAC/ADC clock phase), and a complex gain. Enabling "automatic delay
alignment" at load time performs:

1. Cross-correlation to estimate the integer delay, with parabolic
   interpolation for the fractional part;
2. FFT phase-ramp correction when the fractional delay exceeds 0.02 samples;
3. LS complex-gain normalization.

The alignment result (total delay in samples) is shown in the page message;
if the AM-AM preview collapses from a "cloud" into a clean curve, the
alignment succeeded.

## 4.7 Recommended Data Sizes

| Purpose | Recommended sample count |
|---|---|
| MP/GMP/DDR least-squares fitting | ≥ 100k (about 2000x the number of coefficients) |
| Neural model training | On the order of 10M (much less is fine for quick GUI experiments) |
| Metric evaluation | ≥ 10 OFDM symbols, with a seed different from training |

Training and validation **must use waveforms with different random seeds** to
avoid optimistic bias from memorization.

## 4.8 Lab Capture and the Loopback Observation Budget

There are two routes to a real PA output for DPD evaluation:

1. **Instrument route (golden reference)**: VSG -> PA -> coupler +
   calibrated attenuation chain -> VSA / high-speed ADC. Key points:
   the receive chain's own distortion must be >=10 dB better than the
   target under test; observation bandwidth >= 5x the signal bandwidth;
   shared reference clock between TX and RX; post-processing performs
   delay alignment (Section 4.6) and frequency-response equalization.
   Captured IQ pairs import via the formats in this chapter and reuse
   the entire flow.
2. **Loopback route (product form)**: TX -> coupler -> loopback RX
   capture. Any impairment of the loopback chain gets "learned" into
   the DPD (effectively appending the RX inverse to the TX path), so
   every metric needs a budget. `padpd.loopback.LoopbackChannel`
   injects nine impairment types specified in dBc/dB, and
   `scripts/run_loopback_study.py` quantifies each one's cost on the
   post-DPD metrics:

![Loopback observation-path budget (single impairments vs the clean-observation baseline)](assets/loopback_budget.png)

Budget conclusions (80 MHz / 1024-QAM, clean-observation baseline
EVM -55.1 / ACLR -51.9): loopback **SNR >= 50 dB** for zero cost;
**IQ imbalance is the most expensive single item** (IRR 40 dB still
costs ~20 dB of EVM — run IQ calibration before enabling DPD); RX IM3
needs to be ~15 dB better than the target ACLR; frequency-response
ripple must be calibrated out; phase noise shows the value of a shared
LO; **an unaligned delay is catastrophic** (+53 dB EVM) while the
aligned cost is only +2.5 dB, and drift over the capture calls for
periodic re-estimation.

One pitfall every lab post-processing chain must know (reproduced in
this study): the aligner absorbs the PA's own group delay, so the DPD
carries a fractional-sample advance — **perform receiver-style timing
sync before measuring EVM**, or the constellation shows a phase ramp
and EVM saturates near -20 dB while ACLR looks fine.
