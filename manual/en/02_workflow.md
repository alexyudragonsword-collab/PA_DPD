# 2. The R&D Workflow

## 2.1 From PA Design to System Verification

padpd covers the full closed loop of PA + DPD development:

![padpd R&D pipeline](assets/pipeline.png)

1. **PA design / data sources**: transistor-level design of CMOS/SOI/GaN PAs
   is done in EDA tools. The platform obtains the PA's input/output behavioral
   data in three ways:
   - **Virtual DUT**: the built-in `ReferencePA` (Wiener-Hammerstein
     structure with memory and strong nonlinearity), for exercising the full
     flow with no hardware;
   - **Circuit simulation**: CSV exported from Cadence Envelope analysis;
   - **Measurements**: instrument captures or the public OpenDPD measured
     datasets.
2. **Behavioral modeling**: fit the PA's nonlinearity + memory behavior with
   classical polynomials (closed-form LS, seconds) or neural networks (SGD
   training), yielding a reproducible, differentiable digital twin of the PA.
3. **Digital predistortion (DPD)**: place a predistorter ahead of the PA to
   cancel its nonlinearity. ILA identifies the PA's post-inverse via least
   squares; DLA cascades the predistorter with a frozen neural PA and trains
   it directly by gradient descent. Deep-compression operating points apply
   CFR peak clipping first.
4. **Fixed-point deployment**: quantize the floating-point model to fixed
   point (bit-width sweeps establish the precision boundary) and export the
   FPGA/ASIC hand-off artifacts.
5. **System verification**: EVM / ACLR / transmit mask decide whether the
   802.11be requirements are met; if not, iterate back through DPD/modeling.

## 2.2 Three AI-Native Key Points

Compared with the traditional serial flow of "design the PA first, patch up
linearity later", the platform emphasizes:

- **Neural models as the evaluation surrogate**: polynomial models
  systematically distort out-of-band extrapolation, so their ACLR readings
  cannot be trusted (off by 12 dB on measured data); DPD performance must be
  evaluated with a neural surrogate. This is the core conclusion this project
  has validated on real data.
- **Modeling accuracy ≠ DPD performance**: DDR-Volterra only matches GMP in
  forward modeling, yet as a DPD basis it wins across the board with 55% of
  the parameters. Choose a DPD scheme by directly evaluating the post-DPD
  metrics.
- **PA/DPD co-design**: efficiency and linearizability are separated by an
  abrupt "invertibility wall" — after sequential design pushes to the
  highest-efficiency point, DPD cannot recover it; the Co-Design page puts the
  operating point and DPD complexity into a single optimization trade-off.

## 2.3 Mapping GUI Pages to the Workflow

| Workflow stage | GUI page | Artifacts |
|---|---|---|
| Waveform/stimulus | Waveform Studio | IQDataset `.npz` |
| Data intake | Data Manager | Registered data sources |
| Behavioral modeling | PA Modeling | Model (checkpoint savable) + run |
| Predistortion | DPD Lab | Pre/post-DPD metrics + run |
| Comparative analysis | Compare Runs | Metric bar charts / JSON export |
| Deployment | Deployment | Bit-width curves, ONNX/coefficients/vectors |
| Co-design | Co-Design | Pareto table + optimization trajectory |

Command-line scripts (`scripts/`) provide batch entry points with the same
capabilities as the GUI; long neural training runs (paper-grade reproduction)
are best executed via the scripts in a GPU environment.
