"""Tests for the shared GUI i18n dictionary and preference store."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import re

from gui_core import i18n
from gui_core.prefs import DEFAULTS, load_prefs, save_prefs

CJK = re.compile(r"[一-鿿]")


def test_tr_identity_for_zh():
    assert i18n.tr("波形工作台", "zh") == "波形工作台"


def test_tr_translates_known_key():
    assert i18n.tr("波形工作台", "en") == "Waveform Studio"


def test_tr_falls_back_on_unknown_key():
    assert i18n.tr("不存在的字符串xyz", "en") == "不存在的字符串xyz"


def test_dict_values_nonempty_and_mostly_english():
    leaks = []
    for k, v in i18n._EN.items():
        assert isinstance(v, str) and v.strip(), f"empty value for {k!r}"
        if CJK.search(v) and v != k:  # identity entries like 中文 are fine
            leaks.append(k)
    assert not leaks, f"Chinese leaked into EN values: {leaks[:5]}"


def test_format_placeholders_survive_translation():
    for k, v in i18n._EN.items():
        ph_k = set(re.findall(r"\{(\w+)[^}]*\}", k))
        ph_v = set(re.findall(r"\{(\w+)[^}]*\}", v))
        if ph_k and "." not in k and "[" not in k:
            assert ph_k == ph_v, (
                f"placeholder mismatch for {k!r}: {ph_k} vs {ph_v}")


def test_prefs_roundtrip(tmp_path):
    p = tmp_path / "prefs.json"
    assert load_prefs(p) == DEFAULTS  # missing file → defaults
    save_prefs({"lang": "en", "theme": "light"}, p)
    assert load_prefs(p) == {"lang": "en", "theme": "light"}


def test_prefs_rejects_garbage(tmp_path):
    p = tmp_path / "prefs.json"
    p.write_text('{"lang": "fr", "theme": 42}', encoding="utf-8")
    assert load_prefs(p) == DEFAULTS
    p.write_text("not json", encoding="utf-8")
    assert load_prefs(p) == DEFAULTS


def test_page_sources_only_use_known_keys():
    """Every Chinese literal wrapped in tr(...) must be a dictionary key.

    Untranslated keys silently fall back to Chinese in the English UI,
    so catch them here instead of in a screenshot review.
    """
    import ast
    missing = set()
    for f in list((ROOT / "gui" / "views").glob("*.py")) + \
            list((ROOT / "gui_qt" / "pages").glob("*.py")) + \
            [ROOT / "gui" / "app.py", ROOT / "gui" / "charts.py",
             ROOT / "gui_qt" / "figs.py", ROOT / "gui_qt" / "main.py"]:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.id if isinstance(fn, ast.Name)
                    else fn.attr if isinstance(fn, ast.Attribute) else "")
            if name != "tr" or not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                key = arg.value
                if CJK.search(key) and key not in i18n._EN:
                    missing.add(key)
    assert not missing, (
        f"{len(missing)} tr() keys missing from i18n dict, e.g. "
        f"{sorted(missing)[:8]}")
