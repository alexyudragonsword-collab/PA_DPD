"""Theme tokens for the desktop workbench: one palette, two consumers.

The Qt style sheet and the chart renderer read the same tokens, so a
chart can never be dark navy on a light window again. Chart colours are
the validated categorical slots (blue, orange, aqua, yellow, magenta) in
their fixed order - colour follows the series' position in the spec, the
same order the Android renderer uses - and status colours are reserved
for verdicts and never reused for a series.
"""

from __future__ import annotations

TOKENS = {
    "light": {
        "bg": "#ECEFF0", "panel": "#FFFFFF", "panel2": "#F5F7F7",
        "ink": "#12191C", "ink2": "#3F4C53", "muted": "#66747B",
        "line": "#D3DADD", "line2": "#E4E9EB",
        "accent": "#0E6B64", "accent_ink": "#FFFFFF", "accent_wash": "#DDEEEB",
        "chart": "#FCFCFB", "grid": "#E1E0D9", "axis": "#B7B6AD",
        "tick": "#6F6D67",
        "good": "#0CA30C", "good_ink": "#006300", "good_wash": "#E4F4E2",
        "bad": "#D03B3B", "bad_ink": "#B02A2A", "bad_wash": "#FBE7E6",
        "warn_ink": "#8A5A00", "warn_wash": "#FFF3D6",
        "neutral_stripe": "#C9D1D4",
    },
    "dark": {
        "bg": "#0E1315", "panel": "#161E21", "panel2": "#1B2427",
        "ink": "#E8EDEF", "ink2": "#B9C4C8", "muted": "#8B989E",
        "line": "#2A3539", "line2": "#222C30",
        "accent": "#4CB5AA", "accent_ink": "#0B1513", "accent_wash": "#16302C",
        "chart": "#1A1F21", "grid": "#2C2C2A", "axis": "#4A5052",
        "tick": "#9A9890",
        "good": "#0CA30C", "good_ink": "#3FCB3F", "good_wash": "#14301A",
        "bad": "#D03B3B", "bad_ink": "#F07A7A", "bad_wash": "#3A1A1A",
        "warn_ink": "#F2C14E", "warn_wash": "#33290F",
        "neutral_stripe": "#3A4549",
    },
}

# Categorical series colours, fixed order (validated palette, see the
# dataviz reference): blue, orange, aqua, yellow, magenta.
SERIES = {
    "light": ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4"],
    "dark": ["#3987E5", "#D95926", "#199E70", "#C98500", "#D55181"],
}
# Spec colour roles (gui_core.chart_spec) -> colour
ROLES = {
    "light": {"primary": "#2A78D6", "accent": "#EB6834", "muted": "#52514E",
              "warn": "#D03B3B"},
    "dark": {"primary": "#3987E5", "accent": "#D95926", "muted": "#C3C2B7",
             "warn": "#D03B3B"},
}


def _chevron(color: str, up: bool) -> str:
    """A chevron for spin boxes and combos, written once per colour.

    Any style sheet on a QSpinBox makes Fusion stop drawing its arrows,
    and hiding the buttons instead collapses the editor to 1 px (Qt
    6.12, measured), so the arrows come back as images.
    """
    import tempfile
    from pathlib import Path
    d = Path(tempfile.gettempdir()) / "padpd_qss"
    d.mkdir(exist_ok=True)
    name = f"chev_{'u' if up else 'd'}_{color.lstrip('#')}.svg"
    p = d / name
    if not p.exists():
        pts = "1,6 5,2 9,6" if up else "1,2 5,6 9,2"
        p.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="8">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            'stroke-width="1.6" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg>', encoding="utf-8")
    return p.as_posix()


def _arrows(t: dict) -> str:
    up, down = _chevron(t["ink2"], True), _chevron(t["ink2"], False)
    return f"""
QAbstractSpinBox {{ padding-right: 18px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 16px; border: 0;
    background: transparent; }}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 8px; }}
QAbstractSpinBox::down-arrow {{ image: url({down}); width: 10px; height: 8px; }}
QComboBox {{ padding-right: 22px; }}
QComboBox::drop-down {{ subcontrol-origin: padding;
    subcontrol-position: center right; width: 20px; border: 0;
    background: transparent; }}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 8px; }}
"""


def qss(theme: str) -> str:
    t = TOKENS[theme]
    arrows = _arrows(t)
    return f"""
QWidget {{ color: {t['ink']}; font-size: 13px; }}
QMainWindow, QDialog, QWidget#appRoot, QWidget#page {{ background: {t['bg']}; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget#qt_scrollarea_viewport,
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['line']}; border-radius: 4px;
    min-height: 30px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t['line']}; border-radius: 4px;
    min-width: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* top bar */
QWidget#bar {{ background: {t['panel']}; border-bottom: 1px solid {t['line']}; }}
QLabel#brand {{ font-size: 16px; font-weight: 600; }}
QLabel#brandSub, QLabel#muted {{ color: {t['muted']}; }}
QToolButton#chip {{ background: {t['panel2']}; border: 1px solid {t['line']};
    border-radius: 13px; padding: 3px 10px; color: {t['ink']}; }}
QToolButton#chip:hover {{ border-color: {t['accent']}; }}
QToolButton#chip::menu-indicator {{ image: none; width: 0; }}
QPushButton#seg {{ background: {t['panel2']}; border: 1px solid {t['line']};
    padding: 3px 10px; color: {t['ink2']}; border-radius: 0; }}
QPushButton#seg:checked {{ background: {t['ink']}; color: {t['panel']}; }}

/* rail */
QScrollArea#rail {{ background: {t['panel2']}; border: 0;
    border-right: 1px solid {t['line']}; }}
QWidget#rail {{ background: {t['panel2']}; }}
QLabel#railHead {{ color: {t['muted']}; font-size: 11px; letter-spacing: 1px;
    padding: 10px 12px 2px 12px; }}
QPushButton#railItem {{ text-align: left; border: 0; border-radius: 6px;
    padding: 6px 12px; color: {t['ink2']}; background: transparent; }}
QPushButton#railItem:hover {{ background: {t['line2']}; color: {t['ink']}; }}
QPushButton#railItem:checked {{ background: {t['accent_wash']}; color: {t['ink']};
    font-weight: 600; border-left: 3px solid {t['accent']}; }}

/* page */
QLabel#pageTitle {{ font-size: 22px; font-weight: 600; }}
QLabel#summary {{ color: {t['ink2']}; }}
QFrame#setup, QFrame#card {{ background: {t['panel']}; border: 1px solid {t['line']};
    border-radius: 8px; }}
QLabel#groupHead {{ color: {t['muted']}; font-size: 11px; letter-spacing: 1px;
    padding-top: 6px; }}
QLabel#fieldLabel {{ color: {t['ink2']}; }}
QLabel#help {{ color: {t['muted']}; font-size: 12px; }}
QLabel#warn {{ color: {t['warn_ink']}; background: {t['warn_wash']};
    border-radius: 5px; padding: 4px 8px; font-size: 12px; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{ background: {t['panel2']};
    border: 1px solid {t['line']}; border-radius: 5px; padding: 4px 6px;
    color: {t['ink']}; min-height: 20px; }}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {t['accent']}; }}
{arrows}
QComboBox QAbstractItemView {{ background: {t['panel']}; color: {t['ink']};
    selection-background-color: {t['accent_wash']}; selection-color: {t['ink']}; }}
QPushButton {{ background: {t['panel2']}; border: 1px solid {t['line']};
    border-radius: 6px; padding: 5px 12px; color: {t['ink']}; }}
QPushButton:hover {{ border-color: {t['accent']}; }}
QPushButton:disabled {{ color: {t['muted']}; }}
QPushButton#primary {{ background: {t['ink']}; color: {t['panel']};
    border-color: {t['ink']}; font-weight: 600; padding: 8px 12px; }}
QPushButton#primary:disabled {{ background: {t['muted']}; border-color: {t['muted']}; }}
QPushButton#flowStep, QPushButton#studyCard {{ background: {t['panel']};
    border: 1px solid {t['line']}; border-radius: 8px; padding: 10px 12px;
    text-align: left; color: {t['ink']}; }}
QPushButton#flowStep {{ font-size: 15px; font-weight: 600; }}
QPushButton#flowStep:hover, QPushButton#studyCard:hover {{
    border-color: {t['accent']}; background: {t['accent_wash']}; }}
QPushButton#link {{ border: 0; background: transparent; color: {t['accent']};
    padding: 2px 4px; }}
QProgressBar {{ background: {t['line2']}; border: 0; border-radius: 2px;
    max-height: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}

/* results */
QFrame#stale {{ background: {t['warn_wash']}; border: 1px solid {t['warn_ink']};
    border-radius: 8px; }}
QFrame#tile {{ background: {t['panel']}; border: 1px solid {t['line']};
    border-radius: 8px; }}
QLabel#tileLabel {{ color: {t['ink2']}; }}
QLabel#tileValue {{ font-size: 26px; font-weight: 600; }}
QLabel#tileUnit {{ color: {t['ink2']}; }}
QLabel#tileMeta {{ color: {t['muted']}; font-size: 12px; }}
QLabel#pillPass {{ color: {t['good_ink']}; background: {t['good_wash']};
    border-radius: 9px; padding: 1px 8px; font-size: 11px; font-weight: 700; }}
QLabel#pillFail {{ color: {t['bad_ink']}; background: {t['bad_wash']};
    border-radius: 9px; padding: 1px 8px; font-size: 11px; font-weight: 700; }}
QLabel#metricValue {{ font-size: 16px; font-weight: 600; }}
QLabel#callout {{ background: {t['panel2']}; border: 1px dashed {t['line']};
    border-radius: 6px; padding: 8px 10px; color: {t['ink2']}; }}
QLabel#note {{ color: {t['ink2']}; }}
QLabel#error {{ color: {t['bad_ink']}; background: {t['bad_wash']};
    border-radius: 6px; padding: 6px 10px; }}
QFrame#prov {{ border-top: 1px dashed {t['line']}; }}
QLabel#runId {{ background: {t['panel2']}; border: 1px solid {t['line']};
    border-radius: 4px; padding: 1px 6px; font-family: monospace; }}
QTabWidget::pane {{ border: 0; }}
QTabBar::tab {{ background: transparent; color: {t['ink2']}; padding: 6px 12px;
    border: 0; }}
QTabBar::tab:selected {{ color: {t['ink']}; border-bottom: 2px solid {t['ink']}; }}
QTableWidget {{ background: {t['panel']}; alternate-background-color: {t['panel2']};
    gridline-color: {t['line2']}; border: 1px solid {t['line']}; border-radius: 6px; }}
QHeaderView::section {{ background: {t['panel2']}; color: {t['muted']}; border: 0;
    border-bottom: 1px solid {t['line']}; padding: 4px 8px; }}
QScrollArea {{ border: 0; }}
QListWidget {{ background: {t['panel']}; border: 1px solid {t['line']};
    border-radius: 6px; }}
QListWidget::item:selected {{ background: {t['accent_wash']}; color: {t['ink']}; }}
QTextBrowser {{ background: {t['panel']}; border: 1px solid {t['line']};
    border-radius: 6px; padding: 8px; }}
QMenu {{ background: {t['panel']}; color: {t['ink']}; border: 1px solid {t['line']}; }}
QMenu::item:selected {{ background: {t['accent_wash']}; }}
QToolTip {{ background: {t['panel']}; color: {t['ink']}; border: 1px solid {t['line']}; }}
"""


def palette(theme: str):
    """A QPalette from the same tokens, for what the style sheet does not
    reach: native dialogs, menus, item views' defaults."""
    from PySide6.QtGui import QColor, QPalette
    t = TOKENS[theme]
    p = QPalette()
    R = QPalette.ColorRole
    for role, key in ((R.Window, "bg"), (R.WindowText, "ink"),
                      (R.Base, "panel"), (R.AlternateBase, "panel2"),
                      (R.Text, "ink"), (R.Button, "panel2"),
                      (R.ButtonText, "ink"), (R.ToolTipBase, "panel"),
                      (R.ToolTipText, "ink"), (R.Highlight, "accent"),
                      (R.HighlightedText, "accent_ink"),
                      (R.PlaceholderText, "muted"), (R.Mid, "line"),
                      (R.Midlight, "line2"), (R.Light, "panel"),
                      (R.Dark, "line"), (R.Shadow, "line")):
        p.setColor(role, QColor(t[key]))
    p.setColor(QPalette.ColorGroup.Disabled, R.Text, QColor(t["muted"]))
    p.setColor(QPalette.ColorGroup.Disabled, R.ButtonText, QColor(t["muted"]))
    return p
