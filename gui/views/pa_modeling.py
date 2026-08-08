import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import Run, services  # noqa: E402
from padpd.metrics.amam import am_am_am_pm  # noqa: E402

ui.page_setup(ui.tr("PA 建模"), "📈")
state = ui.get_state()
ui.note(ui.tr("用经典(LS 闭式解)或神经(梯度训练)模型拟合 PA 行为。"
              "拟合好的模型可注册为 DPD 评估代理、进入部署页定点分析。"))

# -- data source ---------------------------------------------------------
with st.sidebar:
    st.subheader(ui.tr("数据源"))
    opts = [ui.tr("合成 ReferencePA")] + list(state.sources)
    src_name = st.selectbox(ui.tr("选择"), opts)
    if src_name == ui.tr("合成 ReferencePA"):
        bw = st.select_slider(ui.tr("带宽 (MHz)"), [20, 40, 80, 160], 80) * 1e6
        qam = st.select_slider("QAM", [256, 1024, 4096], 1024)
        drive = st.slider(ui.tr("PA 工作点 drive"), 0.06, 0.24, 0.14, 0.01)
        frontend = st.selectbox(
            ui.tr("TX 前端损伤"), list(services.FRONTEND_DUTS),
            help=ui.tr("iq=镜像(0.3 dB/3°,IRR≈30 dB),+lo=LO 泄漏 "
                       "-35 dBc,+cim3=counter-IM3 -32 dBc;配套模型选 "
                       "Spline-MP-WL / Spline-MP-CIM3(手册 5.9)"))
        src = services.cached_synthetic_source(bw, qam, symbols=8,
                                               drive=drive,
                                               frontend=frontend)
    else:
        src = state.sources[src_name]

    st.subheader(ui.tr("模型"))
    family = st.radio(ui.tr("模型族"),
                      [ui.tr("经典 (LS)"), ui.tr("神经 (SGD)")],
                      horizontal=True)
    if family == ui.tr("经典 (LS)"):
        mtype = st.selectbox(ui.tr("类型"), list(services.CLASSICAL_MODELS))
        order = st.slider(ui.tr("非线性阶数"), 3, 9, 5,
                          disabled="(" in mtype,
                          help=ui.tr("Spline-MP:阶数滑条 = 节点数"))
        memory = st.slider(ui.tr("记忆深度"), 1, 30, 4, disabled="(" in mtype)
    else:
        backbone = st.selectbox("backbone", ["dgru", "gru", "tcn"])
        hidden = st.slider("hidden size", 4, 32, 8)
        epochs = st.slider("epochs", 5, 100, 20)

run_fit = st.sidebar.button(ui.tr("🚀 拟合模型"), type="primary",
                            use_container_width=True)

if run_fit:
    if family == ui.tr("经典 (LS)"):
        with st.spinner(ui.tr("最小二乘拟合中…")):
            res = services.fit_classical(
                src, mtype, {"order": order, "memory": memory})
        label = f"{mtype} o{order} m{memory}" if "(" not in mtype else mtype
        cfg = {"family": "classical", "type": mtype,
               "order": order, "memory": memory}
    else:
        prog = st.progress(0.0, ui.tr("神经训练中…"))
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
    st.subheader(ui.tr("结果:{name}").format(name=last["name"]))
    c1, c2, c3 = st.columns(3)
    c1.metric(ui.tr("测试 NMSE"), f"{res['metrics']['nmse_db']:.2f} dB")
    c2.metric(ui.tr("参数量"), f"{res['metrics']['n_coeffs']:,}")
    c3.metric(ui.tr("数据源"), last["src_name"])

    col1, col2 = st.columns(2)
    n = min(len(res["x_eval"]), 40000)
    with col1:
        st.plotly_chart(charts.fig_psd(services.psd_pair(
            {ui.tr("实测 PA 输出"): res["y_eval"][:n],
             ui.tr("模型预测"): res["pred"][:n]}, last["fs"])),
            use_container_width=True)
    with col2:
        st.plotly_chart(charts.fig_amam(
            am_am_am_pm(res["x_eval"][:n], res["pred"][:n])),
            use_container_width=True)

    st.subheader(ui.tr("保存"))
    from gui_core.paths import user_data_dir
    _stem = f"gui_{last['name'].split(' @')[0].replace(' ', '_')}"
    col1, col2 = st.columns(2)
    with col1:
        fname = st.text_input(
            ui.tr("checkpoint 文件名"),
            str(user_data_dir() / "models" / _stem)
            + (".pt" if last["cfg"]["family"] == "neural" else ".npz"))
    with col2:
        st.write("")
        st.write("")
        if st.button(ui.tr("💾 保存 checkpoint")):
            Path(fname).parent.mkdir(parents=True, exist_ok=True)
            res["model"].save(fname)
            st.success(ui.tr("已保存 {fname}").format(fname=fname))
else:
    st.info(ui.tr("在左侧选择数据源与模型,点击「拟合模型」。"))

if ui.model_options():
    st.divider()
    st.subheader(ui.tr("本会话模型注册表"))
    st.dataframe([{ui.tr("模型"): k, "NMSE (dB)":
                   f"{v['meta']['metrics']['nmse_db']:.2f}",
                   ui.tr("参数"): v['meta']['metrics']['n_coeffs'],
                   ui.tr("数据源"): v['meta']['source']}
                  for k, v in ui.model_options().items()],
                 use_container_width=True, hide_index=True)
