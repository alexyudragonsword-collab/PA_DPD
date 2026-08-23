"""Adapter layer between the Android host and padpd's service layer.

``api`` is the only module Kotlin calls; ``chart_spec`` turns figure
definitions into renderer-agnostic data. Neither holds algorithm logic -
that stays in ``gui_core/services.py``, shared with both desktop GUIs.
"""
