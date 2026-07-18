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

st.set_page_config(page_title="padpd 工作台", page_icon="📡",
                   layout="wide", initial_sidebar_state="expanded")

pages = [
    st.Page("pages/home.py", title="总览", icon="🏠", default=True),
    st.Page("pages/waveform.py", title="波形工作台", icon="🌊"),
    st.Page("pages/data.py", title="数据管理", icon="🗂️"),
    st.Page("pages/pa_modeling.py", title="PA 建模", icon="📈"),
    st.Page("pages/dpd_lab.py", title="DPD 实验室", icon="🎛️"),
    st.Page("pages/compare.py", title="结果比较", icon="⚖️"),
    st.Page("pages/deploy.py", title="部署", icon="🚀"),
    st.Page("pages/codesign.py", title="联合设计", icon="🧭"),
]

with st.sidebar:
    st.markdown(
        '<p class="brand-title">📡 padpd</p>'
        '<p class="brand-sub">WiFi 7 PA + DPD AI 辅助研发工作台</p>',
        unsafe_allow_html=True)
    st.divider()

nav = st.navigation(pages)
nav.run()
