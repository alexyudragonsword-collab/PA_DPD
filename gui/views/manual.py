import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from gui import ui
from gui_core import manual

ui.page_setup("用户手册", "📖")
ui.note(ui.tr("内置双语用户手册:整合快速入门、工作流、逐页操作指南、"
              "数据接口、算法速览、性能基准、部署打包与 FAQ;"
              "语言随侧栏切换。工程级细节见仓库 docs/ 目录。"))

lang = ui.cur_lang()
labels = {cid: manual.chapter_title(cid, lang)
          for cid in manual.chapter_ids()}

with st.sidebar:
    st.subheader(ui.tr("目录"))
    chapter = st.radio(ui.tr("章节"), manual.chapter_ids(),
                       format_func=labels.get, label_visibility="collapsed")

for seg in manual.split_segments(manual.load(chapter, lang)):
    if seg[0] == "md":
        st.markdown(seg[1])
    else:
        _, path, caption = seg
        st.image(path, caption=caption or None, use_container_width=True)

idx = manual.chapter_ids().index(chapter)
st.divider()
cols = st.columns([1, 3, 1])
if idx > 0:
    cols[0].caption("⬅ " + labels[manual.chapter_ids()[idx - 1]])
if idx < len(manual.chapter_ids()) - 1:
    cols[2].caption(labels[manual.chapter_ids()[idx + 1]] + " ➡")
