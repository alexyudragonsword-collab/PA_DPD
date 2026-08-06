"""Make repo-local packages importable under any pytest invocation.

The `pytest` console script (used by CI) does not put the current
directory on sys.path, so `import gui_core` / `import padpd` fail at
collection time without this. `python -m pytest` worked by accident
(cwd auto-inserted), which hid the breakage locally.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)
