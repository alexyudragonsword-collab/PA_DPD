"""Tests for the built-in bilingual user manual."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gui_core import manual  # noqa: E402

CJK = re.compile(r"[一-鿿]")


def test_all_chapters_exist_in_both_languages():
    for cid in manual.chapter_ids():
        for lang in ("zh", "en"):
            p = manual.MANUAL_DIR / lang / f"{cid}.md"
            assert p.exists(), f"missing {lang}/{cid}.md"
            assert len(p.read_text(encoding="utf-8")) > 200


def test_titles_resolve_for_both_languages():
    for cid in manual.chapter_ids():
        assert manual.chapter_title(cid, "zh")
        t_en = manual.chapter_title(cid, "en")
        assert t_en and not CJK.search(t_en)


def test_english_chapters_contain_no_chinese():
    for cid in manual.chapter_ids():
        text = manual.load(cid, "en")
        leaks = CJK.findall(text)
        assert not leaks, f"{cid}: {len(leaks)} CJK chars leaked"


def test_all_image_references_exist_and_match_across_languages():
    for cid in manual.chapter_ids():
        refs = {}
        for lang in ("zh", "en"):
            refs[lang] = manual.image_refs(manual.load(cid, lang))
            for rel in refs[lang]:
                assert (manual.MANUAL_DIR / rel).exists(), \
                    f"{lang}/{cid}: missing {rel}"
        assert refs["zh"] == refs["en"], f"{cid}: image refs differ"


def test_split_segments_lifts_images():
    md = ("# T\n\ntext one\n\n![cap](assets/pipeline.png)\n\ntext two\n")
    segs = manual.split_segments(md)
    kinds = [s[0] for s in segs]
    assert kinds == ["md", "img", "md"]
    assert segs[1][2] == "cap"
    assert segs[1][1].endswith("pipeline.png")
    assert Path(segs[1][1]).is_absolute()


def test_every_chapter_has_at_least_some_structure():
    for cid in manual.chapter_ids():
        md = manual.load(cid, "zh")
        assert md.lstrip().startswith("# "), f"{cid}: missing H1"


def test_load_unknown_chapter_raises():
    import pytest
    with pytest.raises(KeyError):
        manual.load("99_nope", "zh")
