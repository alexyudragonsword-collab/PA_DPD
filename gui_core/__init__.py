"""Framework-agnostic layer shared by both front ends.

The PySide6 desktop workbench (gui_qt/) and the Android app
(android/, via padpd_mobile.api) are thin presentation layers over this
package: computation, run bookkeeping, artifact I/O, the screen and chart
contracts and the experiment schema live here, so the two behave the
same and algorithms are never duplicated. (A Streamlit web GUI, gui/,
was the third front end until 2026-10-28.)
"""

from . import services
from .runstore import Run, RunStore

__all__ = ["RunStore", "Run", "services"]
