"""Built-in bilingual user manual: chapter registry + loaders.

Content lives in ``manual/{zh,en}/*.md`` with shared images in
``manual/assets``. Both GUIs render the same Markdown source; this
module only locates and slices it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL_DIR = ROOT / "manual"

# (chapter_id, {lang: title}) — order defines the table of contents
CHAPTERS = [
    ("01_intro", {"zh": "产品简介与快速入门",
                  "en": "Introduction & Quick Start"}),
    ("02_workflow", {"zh": "研发工作流全景",
                     "en": "The R&D Workflow"}),
    ("03_pages", {"zh": "功能页操作指南",
                  "en": "Page-by-Page Guide"}),
    ("04_data", {"zh": "数据接入", "en": "Data Interfaces"}),
    ("05_models", {"zh": "模型与算法速览",
                   "en": "Models & Algorithms"}),
    ("06_benchmarks", {"zh": "性能基准", "en": "Performance Benchmarks"}),
    ("07_deploy", {"zh": "部署与打包", "en": "Deployment & Packaging"}),
    ("08_faq", {"zh": "FAQ 与路线图", "en": "FAQ & Roadmap"}),
]


def chapter_ids() -> list[str]:
    return [cid for cid, _ in CHAPTERS]


def chapter_title(chapter_id: str, lang: str = "zh") -> str:
    for cid, titles in CHAPTERS:
        if cid == chapter_id:
            return titles.get(lang) or titles["zh"]
    raise KeyError(chapter_id)


def load(chapter_id: str, lang: str = "zh") -> str:
    """Return the chapter's Markdown; missing English falls back to zh."""
    if chapter_id not in chapter_ids():
        raise KeyError(chapter_id)
    for use in ([lang, "zh"] if lang != "zh" else ["zh"]):
        p = MANUAL_DIR / use / f"{chapter_id}.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(chapter_id)


_IMG = re.compile(r"^!\[([^\]]*)\]\((assets/[^)]+)\)\s*$")


def split_segments(md: str) -> list[tuple]:
    """Slice Markdown into ("md", text) and ("img", abs_path, caption).

    Streamlit's st.markdown cannot reference local image files, so
    standalone image lines are lifted out for st.image; everything else
    stays as Markdown blocks.
    """
    segments: list[tuple] = []
    buf: list[str] = []

    def flush():
        text = "\n".join(buf).strip()
        if text:
            segments.append(("md", text))
        buf.clear()

    for line in md.splitlines():
        m = _IMG.match(line.strip())
        if m:
            flush()
            segments.append(("img", str(MANUAL_DIR / m.group(2)),
                             m.group(1)))
        else:
            buf.append(line)
    flush()
    return segments


def image_refs(md: str) -> list[str]:
    """All assets/... paths referenced by a chapter (for tests)."""
    return re.findall(r"!\[[^\]]*\]\((assets/[^)]+)\)", md)
