"""Moved to ``gui_core.chart_spec``; this name is kept as an alias.

The screen layer and the chart specs used to live here because only the
Android app consumed them. The desktop now renders the same contract, so
they moved to gui_core, which both front ends ship. Kotlin only ever
imports ``padpd_mobile.api``; this alias exists so that
``padpd_mobile.chart_spec`` keeps resolving for anything else (tests,
older notebooks) - and it is the *same module object*, not a copy, so
module-level state such as the fitted-model registry is shared rather
than silently split in two.
"""

import sys

from gui_core import chart_spec as _target

sys.modules[__name__] = _target
