import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import services  # noqa: E402

ui.page_setup("数据管理", "🗂️")
state = ui.get_state()
ui.note("加载实测/仿真 PA 数据(输入输出 IQ 对),预览并注册为数据源,"
        "供 PA 建模与 DPD 页面使用。支持 OpenDPD 数据集目录、"
        "Cadence Envelope CSV、MATLAB .mat、IQDataset .npz。")

tab_dir, tab_up = st.tabs(["📁 OpenDPD 数据集目录", "⬆️ 上传文件"])

with tab_dir:
    default = "/home/user/OpenDPD/datasets"
    root = st.text_input("OpenDPD datasets 目录", default)
    rootp = Path(root)
    if rootp.is_dir():
        names = sorted(p.name for p in rootp.iterdir()
                       if (p / "spec.json").exists())
        choice = st.selectbox("选择数据集", names) if names else None
        if choice and st.button("加载数据集", type="primary"):
            with st.spinner("加载中…"):
                src = services.load_source("opendpd", str(rootp / choice))
                state.sources[src["name"]] = src
            st.success(f"已注册数据源:{src['name']}")
    else:
        st.warning("目录不存在。可 git clone lab-emi/OpenDPD 获取公开数据集。")

with tab_up:
    kind = st.radio("文件类型", ["cadence", "mat", "npz"], horizontal=True,
                    format_func={"cadence": "Cadence CSV (time,i_in,q_in,"
                                            "i_out,q_out)",
                                 "mat": "MATLAB .mat (x,y,fs)",
                                 "npz": "IQDataset .npz"}.get)
    up = st.file_uploader("选择文件", type=["csv", "mat", "npz"])
    fs_override = None
    if kind == "npz":
        pass
    auto_align = st.toggle("自动延迟对齐 (align_delay)", value=False,
                           help="实测/仿真数据常有输入输出定时偏差,"
                                "用互相关自动估计并消除整数+分数延迟")
    if up and st.button("加载文件", type="primary"):
        suffix = Path(up.name).suffix
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=suffix) as f:
            f.write(up.getvalue())
            tmp = f.name
        try:
            src = services.load_source(kind, tmp, fs_override, auto_align)
            src["name"] = up.name
            state.sources[up.name] = src
            st.success(f"已注册数据源:{up.name}")
            if src.get("align_info"):
                st.info(f"对齐:整数延迟 {src['align_info']['lag']},"
                        f"总延迟 {src['align_info']['lag_total']:.2f} 采样")
        except Exception as e:  # surface load errors to the user
            st.error(f"加载失败:{e}")

st.divider()
st.subheader("已注册数据源")
if not state.sources:
    st.caption("尚无数据源。加载数据集,或在 PA 建模页直接使用合成 "
               "ReferencePA。")
else:
    sel = st.selectbox("预览", list(state.sources))
    src = state.sources[sel]
    prev = services.source_preview(src)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("采样率", f"{src['fs']/1e6:.2f} MSPS")
    c2.metric("train / val / test",
              f"{prev['n_train']:,} / {prev['n_val']:,} / "
              f"{prev['n_test']:,}")
    spec = src.get("spec") or {}
    c3.metric("主带宽", f"{(src.get('bw') or 0)/1e6:.0f} MHz"
              if src.get("bw") else "—")
    c4.metric("调制 / 子信道",
              f"{spec.get('modulation','—')} / {spec.get('n_sub_ch','—')}")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.fig_psd(
            {"PA 输入": (prev["freq"], prev["psd_in"]),
             "PA 输出": (prev["freq"], prev["psd_out"])}),
            use_container_width=True)
    with col2:
        st.plotly_chart(charts.fig_amam(prev["amam"]),
                        use_container_width=True)

    if st.button("移除该数据源"):
        del state.sources[sel]
        st.rerun()
