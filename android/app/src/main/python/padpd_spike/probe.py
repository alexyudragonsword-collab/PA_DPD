"""Phase 0 feasibility probe: does the padpd compute core work on Android?

This module answers three questions that cannot be answered from a desktop:

1. Does Chaquopy's scipy wheel carry the submodules padpd actually uses?
   ``scipy.signal`` alone is not enough - the de-embedder needs
   ``scipy.optimize.curve_fit``, the state spline needs
   ``scipy.interpolate.PchipInterpolator``, and the MATLAB loader needs
   ``scipy.io.loadmat``. A partial wheel would fail late, inside a page,
   instead of here.
2. Does ``gui_core.services`` - the service layer both desktop GUIs sit
   on - import on device without dragging in torch?
3. How long do the real modeling operations take on this SoC?

Deliberately free of any Android import so the exact same code runs on a
desktop (``python -m padpd_spike.probe``) and on device. The desktop run
is the baseline the device numbers are compared against; keeping one
implementation is what makes that comparison meaningful.

Every step is individually guarded: a probe that dies on the first
missing module tells you far less than one that reports all five
failures at once.
"""

from __future__ import annotations

import io
import os
import platform
import sys
import time
import traceback

# padpd's own pitfall list warns that OpenMP threading has deadlocked this
# codebase before (tests/conftest.py pins OMP_NUM_THREADS=1 for exactly
# that reason). Android's thread limits differ again, so pin explicitly
# rather than inheriting whatever the runtime guesses - and do it before
# numpy is imported, which is the only point where it takes effect.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

# Waveform under test: 160 MHz / 1024-QAM / 12 symbols at 4x oversampling
# = 104,448 complex samples. Chosen to match the desktop baseline recorded
# in docs, and because 160 MHz is the WiFi 7 case that actually stresses
# the fit - an 80 MHz probe would flatter the device.
BW_HZ = 160e6
N_SYMBOLS = 12

SCIPY_SUBMODULES = [
    ("scipy.signal", "welch / lfilter / correlate - PSD, ACLR, de-embed"),
    ("scipy.optimize", "curve_fit - gain-modulation tau fitting"),
    ("scipy.interpolate", "PchipInterpolator - state-conditioned spline"),
    ("scipy.io", "loadmat - MATLAB capture import"),
]


class Report:
    """Accumulates lines plus a machine-readable pass/fail verdict."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.results: dict[str, object] = {}
        self.failures: list[str] = []

    def say(self, line: str = "") -> None:
        self.lines.append(line)

    def fail(self, what: str, exc: BaseException) -> None:
        self.failures.append(what)
        self.say(f"  FAIL {what}: {type(exc).__name__}: {exc}")
        buf = io.StringIO()
        traceback.print_exc(limit=4, file=buf)
        for ln in buf.getvalue().rstrip().splitlines():
            self.say(f"       {ln}")

    def text(self) -> str:
        return "\n".join(self.lines)


def _section(rep: Report, title: str) -> None:
    rep.say()
    rep.say(f"--- {title} ---")


def probe_platform(rep: Report) -> None:
    _section(rep, "platform")
    rep.say(f"  python     {sys.version.split()[0]}")
    rep.say(f"  machine    {platform.machine()}")
    rep.say(f"  system     {platform.system()} {platform.release()}")
    rep.results["python"] = sys.version.split()[0]
    rep.results["machine"] = platform.machine()


def probe_imports(rep: Report) -> None:
    """Time each scipy submodule import separately.

    Import time matters on its own: scipy submodules are lazily compiled
    Fortran/C extensions, and a multi-second first import on device would
    show up to the user as a frozen page, not as a slow fit.
    """
    _section(rep, "scipy submodules")
    for name, why in SCIPY_SUBMODULES:
        t = time.perf_counter()
        try:
            __import__(name)
            dt = time.perf_counter() - t
            rep.say(f"  ok   {name:<20} {dt:6.2f} s   ({why})")
            rep.results[f"import:{name}"] = round(dt, 3)
        except Exception as e:                       # noqa: BLE001
            rep.fail(f"import {name}", e)


def probe_numpy_config(rep: Report) -> None:
    _section(rep, "numpy / BLAS")
    try:
        import numpy as np
        rep.say(f"  numpy      {np.__version__}")
        rep.results["numpy"] = np.__version__
        try:
            import scipy
            rep.say(f"  scipy      {scipy.__version__}")
            rep.results["scipy"] = scipy.__version__
        except Exception:                            # noqa: BLE001
            pass
        # Which BLAS numpy is linked against decides whether the LS solve
        # is a few seconds or a few minutes. show_config() is verbose, so
        # keep only the lines that name a library.
        try:
            buf = io.StringIO()
            stdout, sys.stdout = sys.stdout, buf
            try:
                np.show_config()
            finally:
                sys.stdout = stdout
            hits = [ln.strip() for ln in buf.getvalue().splitlines()
                    if any(k in ln.lower() for k in
                           ("openblas", "blas", "lapack", "name:"))]
            for ln in hits[:12]:
                rep.say(f"  cfg  {ln}")
        except Exception:                            # noqa: BLE001
            rep.say("  cfg  (show_config unavailable)")
        for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            rep.say(f"  env  {var}={os.environ.get(var)}")
    except Exception as e:                           # noqa: BLE001
        rep.fail("import numpy", e)


def probe_service_layer(rep: Report) -> None:
    """Import the shared service layer and confirm it stays torch-free.

    ``gui_core.services`` is the boundary the Android app will call
    through. It is written to be pure Python with no GUI import, and
    ``padpd.dpd`` lazy-loads its torch entry points - but that property is
    load-bearing here rather than merely tidy, because torch has no
    Android wheel at all. If something upstream ever adds an eager torch
    import, this line is where it surfaces.
    """
    _section(rep, "service layer")
    try:
        t = time.perf_counter()
        import gui_core.services as services         # noqa: F401
        dt = time.perf_counter() - t
        rep.say(f"  ok   import gui_core.services   {dt:6.2f} s")
        rep.results["import:gui_core.services"] = round(dt, 3)
    except Exception as e:                           # noqa: BLE001
        rep.fail("import gui_core.services", e)
        return

    torch_loaded = "torch" in sys.modules
    rep.results["torch_loaded"] = torch_loaded
    if torch_loaded:
        rep.say("  FAIL torch was imported - it has no Android wheel")
        rep.failures.append("torch imported by service layer")
    else:
        rep.say("  ok   torch not imported")


def probe_benchmarks(rep: Report) -> None:
    """Time the six operations that gate an interactive UI."""
    _section(rep, f"benchmarks ({BW_HZ/1e6:.0f} MHz, {N_SYMBOLS} symbols)")
    try:
        import numpy as np                           # noqa: F401
        from padpd.dpd import ILAPredistorter
        from padpd.metrics import aclr
        from padpd.pa import (GMPModel, ReferencePA, SplineGMP,
                              SplineMemoryPolynomial)
        from padpd.waveform.ofdm import OFDMConfig, generate_ofdm
    except Exception as e:                           # noqa: BLE001
        rep.fail("import padpd benchmark deps", e)
        return

    def timed(label: str, fn):
        t = time.perf_counter()
        try:
            out = fn()
        except Exception as e:                       # noqa: BLE001
            rep.fail(label, e)
            return None
        dt = time.perf_counter() - t
        rep.say(f"  {label:<26} {dt:7.2f} s")
        rep.results[f"bench:{label}"] = round(dt, 3)
        return out

    cfg = OFDMConfig(bandwidth_hz=BW_HZ, n_symbols=N_SYMBOLS)
    wf = timed("ofdm generate", lambda: generate_ofdm(cfg))
    if wf is None:
        return
    x = wf.x
    fs = cfg.bandwidth_hz * cfg.oversampling
    rep.say(f"  (n_samples = {x.size}, fs = {fs/1e6:.0f} MHz)")
    rep.results["n_samples"] = int(x.size)

    pa = ReferencePA()
    y = pa(x)

    gmp = GMPModel()
    timed("gmp fit", lambda: gmp.fit(x, y))
    if gmp.coeffs is not None:
        rep.say(f"  (gmp n_coeffs = {len(gmp.coeffs)})")
        timed("gmp predict", lambda: gmp(x))

    timed("spline-mp fit", lambda: SplineMemoryPolynomial().fit(x, y))
    timed("spline-gmp fit", lambda: SplineGMP().fit(x, y))
    timed("ila 3-iter",
          lambda: ILAPredistorter(model_factory=GMPModel,
                                  n_iterations=3).fit(pa, x))
    timed("aclr", lambda: aclr(y, fs, BW_HZ))


def probe_data_dir(rep: Report) -> None:
    """Confirm the run registry lands in the writable dir we were given.

    ``gui_core/paths.py`` already honours PADPD_DATA_DIR (it was added for
    tests and portable builds); on Android the host sets it to filesDir
    before starting Python, so no code change is needed. This checks that
    the override actually took, rather than assuming it.
    """
    _section(rep, "data dir")
    try:
        from gui_core.paths import user_data_dir
        p = user_data_dir()
        writable = os.access(p, os.W_OK)
        rep.say(f"  PADPD_DATA_DIR={os.environ.get('PADPD_DATA_DIR')}")
        rep.say(f"  user_data_dir()={p}  writable={writable}")
        rep.results["data_dir"] = str(p)
        rep.results["data_dir_writable"] = bool(writable)
        if not writable:
            rep.failures.append("data dir not writable")
    except Exception as e:                           # noqa: BLE001
        rep.fail("user_data_dir", e)


def run() -> str:
    """Run every probe and return the report as text.

    Called from Kotlin via Chaquopy (on a background thread - these calls
    block for seconds) and from ``__main__`` on desktop.
    """
    rep = Report()
    rep.say("padpd Android feasibility probe")
    rep.say("=" * 46)
    total = time.perf_counter()

    probe_platform(rep)
    probe_imports(rep)
    probe_numpy_config(rep)
    probe_service_layer(rep)
    probe_data_dir(rep)
    probe_benchmarks(rep)

    rep.say()
    rep.say("=" * 46)
    elapsed = time.perf_counter() - total
    if rep.failures:
        rep.say(f"VERDICT: {len(rep.failures)} FAILURE(S) in {elapsed:.1f} s")
        for f in rep.failures:
            rep.say(f"  - {f}")
    else:
        rep.say(f"VERDICT: all probes passed in {elapsed:.1f} s")
    rep.say()
    rep.say("Compare against the acceptance criteria in android/README.md.")
    return rep.text()


def boot(data_dir: str) -> str:
    """Entry point the Android host calls.

    Sets PADPD_DATA_DIR before anything under ``padpd``/``gui_core`` is
    imported - ``gui_core.prefs`` resolves its path at import time, so
    setting the variable afterwards would be too late. Java has no
    portable way to mutate the process environment, which is why the
    host passes the directory in and Python sets it rather than the
    other way round.
    """
    os.environ["PADPD_DATA_DIR"] = data_dir
    return run()


if __name__ == "__main__":
    print(run())
