"""Make repo-local packages importable under any pytest invocation.

The `pytest` console script (used by CI) does not put the current
directory on sys.path, so `import gui_core` / `import padpd` fail at
collection time without this. `python -m pytest` worked by accident
(cwd auto-inserted), which hid the breakage locally.
"""

import os
import sys
from pathlib import Path

# Single-threaded OpenMP for the whole test process. The suite mixes Qt
# worker threads and streamlit ScriptRunner threads with torch/numpy ops;
# libgomp parallel teams have been observed to lose a barrier wakeup in
# that mix under load (gdb: workers stuck in gomp_barrier_wait_end, the
# region's master frozen holding the GIL -> every Python thread stalls at
# a bytecode boundary). No parallel regions, no barrier, no deadlock;
# test-scale workloads don't need OpenMP speedup. Must be set before the
# first torch/numpy import in this process.
os.environ.setdefault("OMP_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Pre-import pandas on the main thread. Streamlit's AppTest otherwise
# performs pandas' heavy first import inside its ScriptRunner worker
# thread, which has been observed to deadlock (futex wait mid-import)
# when the gui_web tests run after the Qt suite under load. Importing it
# here removes that window entirely; skip silently if not installed.
try:
    import pandas  # noqa: F401
except ImportError:
    pass
