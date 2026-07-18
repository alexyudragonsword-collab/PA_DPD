from PySide6.QtWidgets import (QHBoxLayout, QListWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from gui_core import manual
from gui_qt import common
from gui_qt.common import page_scaffold, tr
from gui_qt.themes import QT_TOKENS


def _manual_css(theme: str) -> str:
    t = QT_TOKENS[theme]
    return f"""
    body {{ color: {t['fg']}; font-size: 13.5px; }}
    h1 {{ font-size: 21px; color: {t['fg']}; }}
    h2 {{ font-size: 16px; color: {t['fg']};
          border-bottom: 1px solid {t['border']}; }}
    h3 {{ font-size: 14px; color: {t['fg']}; }}
    p, li {{ line-height: 148%; }}
    a {{ color: {t['blue']}; }}
    code {{ background: {t['card']}; color: {t['accent']};
            font-family: 'Consolas','DejaVu Sans Mono',monospace; }}
    pre {{ background: {t['card']}; border: 1px solid {t['border']};
           padding: 8px; }}
    table {{ border-collapse: collapse; }}
    th {{ background: {t['card']}; color: {t['muted']};
          border: 1px solid {t['border']}; padding: 4px 10px; }}
    td {{ border: 1px solid {t['border']}; padding: 4px 10px; }}
    img {{ margin: 8px 0; }}
    blockquote {{ border-left: 3px solid {t['blue']};
                  background: {t['note_bg']}; padding: 4px 10px;
                  color: {t['note_fg']}; }}
    """


def _to_html(md_text: str) -> str | None:
    try:
        import markdown
    except ImportError:
        return None
    body = markdown.markdown(
        md_text, extensions=["tables", "fenced_code", "sane_lists"])
    # scale screenshots to a readable width inside the browser pane
    return body.replace("<img ", '<img width="820" ')


class ManualPage(QWidget):
    def __init__(self):
        super().__init__()
        page, lay = page_scaffold(
            tr("用户手册"),
            tr("内置双语用户手册:快速入门、工作流、逐页指南、数据接口、"
               "算法速览、性能基准、部署打包与 FAQ;语言随侧栏切换,"
               "工程级细节见仓库 docs/ 目录。"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        row = QHBoxLayout()
        self.toc = QListWidget()
        self.toc.setMaximumWidth(230)
        lang = common.PREFS["lang"]
        for cid in manual.chapter_ids():
            self.toc.addItem(manual.chapter_title(cid, lang))
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setSearchPaths([str(manual.MANUAL_DIR)])
        row.addWidget(self.toc)
        row.addWidget(self.view, 1)
        holder = QWidget()
        holder.setLayout(row)
        lay.addWidget(holder, 1)

        self.toc.currentRowChanged.connect(self._show)
        self.toc.setCurrentRow(0)

    def _show(self, row: int):
        if row < 0:
            return
        cid = manual.chapter_ids()[row]
        md_text = manual.load(cid, common.PREFS["lang"])
        html = _to_html(md_text)
        if html is None:  # graceful fallback without the markdown package
            self.view.setMarkdown(md_text)
            return
        self.view.document().setDefaultStyleSheet(
            _manual_css(common.PREFS["theme"]))
        self.view.setHtml(html)
        self.view.verticalScrollBar().setValue(0)
