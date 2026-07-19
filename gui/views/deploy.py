import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import Run, services  # noqa: E402

ui.page_setup(ui.tr("部署"), "🚀")
state = ui.get_state()
ui.note(ui.tr("对拟合好的模型做定点位宽扫描(bit-true)与硬件成本估计,"
              "导出 FPGA/ASIC 交接产物:整数系数 JSON、参考向量 CSV、"
              "神经模型 ONNX。经典模型免训练直接量化(PTQ);"
              "神经模型权重+激活 PTQ。"))

models = ui.model_options()
if not models:
    st.info(ui.tr("先在 📈 PA 建模页拟合至少一个模型。"))
    st.stop()

with st.sidebar:
    st.subheader(ui.tr("对象"))
    picked = st.multiselect(ui.tr("模型(可多选对比)"), list(models),
                            default=list(models)[:1])
    bits = st.multiselect(ui.tr("位宽"), [16, 14, 12, 10, 8],
                          default=[16, 12, 8])
    src_name = st.selectbox(
        ui.tr("评估数据源"),
        [ui.tr("<拟合时的源>")] + list(state.sources))

run = st.sidebar.button(ui.tr("🚀 位宽扫描"), type="primary",
                        use_container_width=True)

if run and picked and bits:
    sweeps = {}
    prog = st.progress(0.0)
    for i, name in enumerate(picked):
        entry = models[name]
        src = (services.eval_source_for(entry["meta"], state.sources)
               if src_name == ui.tr("<拟合时的源>")
               else state.sources[src_name])
        sweeps[name.split(" @")[0]] = services.bitwidth_sweep(
            entry["model"], src, bits=tuple(sorted(bits, reverse=True)))
        prog.progress((i + 1) / len(picked))
    prog.empty()
    st.session_state["deploy_sweeps"] = sweeps
    for label, s in sweeps.items():
        state.runstore.add(Run(name=f"deploy {label}", kind="deploy",
                               config={"bits": bits},
                               metrics={"float_nmse_db": s["float"],
                                        **{f"w{b}_nmse_db": v
                                           for b, v in s["bits"].items()}}))

sweeps = st.session_state.get("deploy_sweeps")
if sweeps:
    st.subheader(ui.tr("位宽 vs 精度"))
    st.plotly_chart(charts.fig_bitwidth(sweeps), use_container_width=True)
    rows = []
    for label, s in sweeps.items():
        row = {ui.tr("模型"): label, "float": f"{s['float']:.2f}"}
        row.update({f"W{b}": f"{v:.2f}" for b, v in s["bits"].items()})
        if s.get("macs"):
            row[ui.tr("MAC/样本")] = s["macs"]["real_macs_per_sample"]
            row["GMAC/s"] = f"{s['macs']['real_gmac_per_s']:.0f}"
        rows.append(row)
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.divider()
st.subheader(ui.tr("导出交接产物"))
col1, col2 = st.columns(2)
with col1:
    exp_model = st.selectbox(ui.tr("模型"), list(models), key="exp_model")
    w_bits = st.select_slider(ui.tr("系数位宽"), [16, 14, 12, 10, 8], 16)
with col2:
    st.write("")
    if st.button(ui.tr("📦 生成产物"), use_container_width=True):
        entry = models[exp_model]
        src = services.eval_source_for(entry["meta"], state.sources)
        out_dir = f"deploy_export/gui_{exp_model.split(' @')[0].replace(' ', '_')}"
        with st.spinner(ui.tr("导出中…")):
            paths = services.export_artifacts(entry["model"], src, out_dir,
                                              w_bits=w_bits)
        st.session_state["deploy_paths"] = paths

paths = st.session_state.get("deploy_paths")
if paths:
    cols = st.columns(len([k for k in paths if not k.endswith("verified")]))
    i = 0
    for key, p in paths.items():
        if key.endswith("verified"):
            continue
        with cols[i]:
            data = open(p, "rb").read()
            st.download_button(f"⬇️ {key} ({Path(p).name})", data,
                               file_name=Path(p).name, key=f"dl_{key}")
        i += 1
    if "onnx_verified" in paths:
        st.markdown(ui.badge(
            ui.tr("ONNX 数值验证 通过") if paths["onnx_verified"]
            else ui.tr("ONNX 数值验证 跳过"),
            "ok" if paths["onnx_verified"] else "info"),
            unsafe_allow_html=True)
    if paths.get("rtl_verified") is not None:
        st.markdown(ui.badge(
            ui.tr("RTL bit-true 验证通过") if paths["rtl_verified"]
            else ui.tr("RTL bit-true 验证跳过"),
            "ok" if paths["rtl_verified"] else "info"),
            unsafe_allow_html=True)
