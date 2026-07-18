"""Framework-agnostic service layer shared by both GUIs.

The Streamlit web workbench (gui/) and the PySide6 desktop app (gui_qt/)
are thin presentation layers over this module: all computation, run
bookkeeping, and artifact I/O live here so the two GUIs behave
identically and algorithms are never duplicated.
"""

from .runstore import RunStore, Run
from . import services

__all__ = ["RunStore", "Run", "services"]
