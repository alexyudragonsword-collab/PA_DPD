import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import ui  # noqa: E402

ui.page_setup("padpd 工作台总览", "🏠")
state = ui.get_state()

ui.note("WiFi 7(802.11be)PA 行为建模与数字预失真的完整研发平台:"
        "经典(Saleh/MP/GMP/DDR)与神经(GRU/DGRU/TCN)模型、"
        "ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。")

# -- key published numbers (from docs/05_performance_summary.md) ---------
st.subheader("代表性成果(实测)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("合成链路 DPD 后 EVM", "-57.4 dB", "160 MHz / 1024-QAM")
c2.metric("TCN vs GMP(真实数据 NMSE)", "-34.9 dB", "+1.2 dB 超经典基线")
c3.metric("DPA_160 DLA DPD ACLR", "-53.1 dBc", "过 -52 验收线")
c4.metric("APA 代理重评 ACLR", "-38.56 dBc", "≈发表值 -38.80")

st.divider()

# -- environment self-check ----------------------------------------------
st.subheader("环境自检")
col1, col2, col3 = st.columns(3)

with col1:
    try:
        import torch
        st.markdown(ui.badge("PyTorch " + torch.__version__, "ok")
                    + " 神经建模可用", unsafe_allow_html=True)
    except ImportError:
        st.markdown(ui.badge("PyTorch 未安装", "fail")
                    + " 神经页面不可用", unsafe_allow_html=True)

with col2:
    opendpd = Path("/home/user/OpenDPD/datasets")
    alt = Path("../OpenDPD/datasets")
    found = opendpd if opendpd.is_dir() else (alt if alt.is_dir() else None)
    if found:
        n = len([p for p in found.iterdir() if (p / "spec.json").exists()])
        st.markdown(ui.badge(f"OpenDPD × {n} 数据集", "ok")
                    + f" {found}", unsafe_allow_html=True)
    else:
        st.markdown(ui.badge("OpenDPD 未找到", "info")
                    + " 可在数据页手动指定", unsafe_allow_html=True)

with col3:
    models = list(Path("models").glob("*")) if Path("models").is_dir() else []
    runs = state.runstore.list()
    st.markdown(ui.badge(f"模型 checkpoint × {len(models)}", "info")
                + ui.badge(f"实验 run × {len(runs)}", "info"),
                unsafe_allow_html=True)

st.divider()

# -- workflow guide ------------------------------------------------------
st.subheader("工作流")
st.markdown("""
| 步骤 | 页面 | 内容 |
|---|---|---|
| 1 | 🌊 波形工作台 | 生成 802.11be 风格 OFDM(可选 CFR 削峰),导出数据集 |
| 2 | 🗂️ 数据管理 | 加载 OpenDPD / Cadence / MATLAB / .npz 实测数据,延迟对齐 |
| 3 | 📈 PA 建模 | 经典 LS 或神经训练拟合 PA,NMSE 评估 |
| 4 | 🎛️ DPD 实验室 | ILA / DLA 预失真,EVM·ACLR·Mask 前后对比 |
| 5 | ⚖️ 结果比较 | 跨实验指标对比(与桌面版共享注册表) |
| 6 | 🚀 部署 | 定点位宽扫描,导出 ONNX / 整数系数 / 参考向量 |
| 7 | 🧭 联合设计 | PA 工作点 × DPD 复杂度联合权衡 |
""")

recent = state.runstore.list()[:5]
if recent:
    st.subheader("最近实验")
    st.dataframe(
        [{"时间": r.when, "名称": r.name, "类型": r.kind,
          **{k: (f"{v:.2f}" if isinstance(v, float) else v)
             for k, v in list(r.metrics.items())[:3]}}
         for r in recent],
        use_container_width=True, hide_index=True)
