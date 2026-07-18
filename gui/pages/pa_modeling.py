import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import Run, services  # noqa: E402
from padpd.metrics.amam import am_am_am_pm  # noqa: E402

ui.page_setup("PA 建模", "📈")
state = ui.get_state()
ui.note("用经典(LS 闭式解)或神经(梯度训练)模型拟合 PA 行为。"
        "拟合好的模型可注册为 DPD 评估代理、进入部署页定点分析。")

# -- data source ---------------------------------------------------------
with st.sidebar:
    st.subheader("数据源")
    opts = ["合成 ReferencePA"] + list(state.sources)
    src_name = st.selectbox("选择", opts)
    if src_name == "合成 ReferencePA":
        bw = st.select_slider("带宽 (MHz)", [20, 40, 80, 160], 80) * 1e6
        qam = st.select_slider("QAM", [256, 1024, 4096], 1024)
        drive = st.slider("PA 工作点 drive", 0.06, 0.24, 0.14, 0.01)
        key = f"synth_{bw}_{qam}_{drive}"
        if key not in st.session_state:
            st.session_state[key] = services.make_synthetic_source(
                bw, qam, symbols=8, drive=drive)
        src = st.session_state[key]
    else:
        src = state.sources[src_name]

    st.subheader("模型")
    family = st.radio("模型族", ["经典 (LS)", "神经 (SGD)"], horizontal=True)
    if family == "经典 (LS)":
        mtype = st.selectbox("类型", list(services.CLASSICAL_MODELS))
        order = st.slider("非线性阶数", 3, 9, 5,
                          disabled="(" in mtype)
        memory = st.slider("记忆深度", 1, 30, 4, disabled="(" in mtype)
    else:
        backbone = st.selectbox("backbone", ["dgru", "gru", "tcn"])
        hidden = st.slider("hidden size", 4, 32, 8)
        epochs = st.slider("epochs", 5, 100, 20)

run_fit = st.sidebar.button("🚀 拟合模型", type="primary",
                            use_container_width=True)

if run_fit:
    if family == "经典 (LS)":
        with st.spinner("最小二乘拟合中…"):
            res = services.fit_classical(
                src, mtype, {"order": order, "memory": memory})
        label = f"{mtype} o{order} m{memory}" if "(" not in mtype else mtype
        cfg = {"family": "classical", "type": mtype,
               "order": order, "memory": memory}
    else:
        prog = st.progress(0.0, "神经训练中…")
        chart_ph = st.empty()
        hist = []

        def cb(h):
            hist.append(h)
            prog.progress(min(1.0, (h["epoch"] + 1) / epochs),
                          f"epoch {h['epoch']+1}/{epochs} · "
                          f"val NMSE {h['val_nmse_db']:.2f} dB")
            if (h["epoch"] + 1) % 2 == 0:
                chart_ph.plotly_chart(charts.fig_train_curve(hist),
                                      use_container_width=True)

        res = services.fit_neural(src, backbone=backbone, hidden=hidden,
                                  epochs=epochs, on_epoch=cb)
        prog.empty()
        chart_ph.empty()
        label = f"{backbone.upper()}-H{hidden} e{epochs}"
        cfg = {"family": "neural", "backbone": backbone,
               "hidden": hidden, "epochs": epochs}

    model_name = f"{label} @ {src['name']}"
    ui.register_model(model_name, res["model"],
                      {"config": cfg, "source": src["name"],
                       "metrics": res["metrics"]})
    st.session_state["last_fit"] = {"res": res, "name": model_name,
                                    "cfg": cfg, "src_name": src["name"],
                                    "fs": src["fs"]}
    state.runstore.add(Run(name=model_name, kind="pa_model", config=cfg,
                           metrics=res["metrics"]))

# -- results -------------------------------------------------------------
last = st.session_state.get("last_fit")
if last:
    res = last["res"]
    st.subheader(f"结果:{last['name']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("测试 NMSE", f"{res['metrics']['nmse_db']:.2f} dB")
    c2.metric("参数量", f"{res['metrics']['n_coeffs']:,}")
    c3.metric("数据源", last["src_name"])

    col1, col2 = st.columns(2)
    n = min(len(res["x_eval"]), 40000)
    with col1:
        st.plotly_chart(charts.fig_psd(services.psd_pair(
            {"实测 PA 输出": res["y_eval"][:n],
             "模型预测": res["pred"][:n]}, last["fs"])),
            use_container_width=True)
    with col2:
        st.plotly_chart(charts.fig_amam(
            am_am_am_pm(res["x_eval"][:n], res["pred"][:n])),
            use_container_width=True)

    st.subheader("保存")
    col1, col2 = st.columns(2)
    with col1:
        fname = st.text_input(
            "checkpoint 文件名",
            f"models/gui_{last['name'].split(' @')[0].replace(' ', '_')}"
            + (".pt" if last["cfg"]["family"] == "neural" else ".npz"))
    with col2:
        st.write("")
        st.write("")
        if st.button("💾 保存 checkpoint"):
            Path(fname).parent.mkdir(parents=True, exist_ok=True)
            res["model"].save(fname)
            st.success(f"已保存 {fname}")
else:
    st.info("在左侧选择数据源与模型,点击「拟合模型」。")

if ui.model_options():
    st.divider()
    st.subheader("本会话模型注册表")
    st.dataframe([{"模型": k, "NMSE (dB)":
                   f"{v['meta']['metrics']['nmse_db']:.2f}",
                   "参数": v['meta']['metrics']['n_coeffs'],
                   "数据源": v['meta']['source']}
                  for k, v in ui.model_options().items()],
                 use_container_width=True, hide_index=True)
