"""padpd Web 工作台入口.

启动:  streamlit run gui/app.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st  # noqa: E402

from gui import ui  # noqa: E402

ui.apply_theme()

_icon = ROOT / "gui_qt" / "assets" / "padpd.png"   # shared with desktop app
st.set_page_config(page_title=ui.tr("padpd 工作台"),
                   page_icon=str(_icon) if _icon.exists() else "📡",
                   layout="wide", initial_sidebar_state="expanded")

pages = [
    st.Page("views/home.py", title=ui.tr("总览"), icon="🏠", default=True),
    st.Page("views/waveform.py", title=ui.tr("波形工作台"), icon="🌊"),
    st.Page("views/data.py", title=ui.tr("数据管理"), icon="🗂️"),
    st.Page("views/pa_modeling.py", title=ui.tr("PA 建模"), icon="📈"),
    st.Page("views/dpd_lab.py", title=ui.tr("DPD 实验室"), icon="🎛️"),
    st.Page("views/compare.py", title=ui.tr("结果比较"), icon="⚖️"),
    st.Page("views/deploy.py", title=ui.tr("部署"), icon="🚀"),
    st.Page("views/codesign.py", title=ui.tr("联合设计"), icon="🧭"),
    st.Page("views/manual.py", title=ui.tr("用户手册"), icon="📖"),
]

with st.sidebar:
    st.markdown(
        '<p class="brand-title">📡 padpd</p>'
        f'<p class="brand-sub">{ui.tr("WiFi 7 PA + DPD AI 辅助研发工作台")}'
        "</p>",
        unsafe_allow_html=True)
    st.divider()

nav = st.navigation(pages)
nav.run()

# language / theme switchers at the bottom of the sidebar
with st.sidebar:
    st.divider()
    c1, c2 = st.columns(2)
    lang_labels = {"zh": "中文", "en": "English"}
    theme_labels = {"dark": ui.tr("深色"), "light": ui.tr("浅色")}
    lang = c1.selectbox("Language", list(lang_labels),
                        index=list(lang_labels).index(ui.cur_lang()),
                        format_func=lang_labels.get, key="ui_lang")
    theme = c2.selectbox(ui.tr("主题"), list(theme_labels),
                         index=list(theme_labels).index(ui.cur_theme()),
                         format_func=theme_labels.get, key="ui_theme")
    if lang != ui.cur_lang() or theme != ui.cur_theme():
        ui.set_pref("lang", lang)
        ui.set_pref("theme", theme)
        ui.apply_theme()
        st.rerun()
