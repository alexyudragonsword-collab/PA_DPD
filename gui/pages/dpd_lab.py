import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import Run, services  # noqa: E402

ui.page_setup("DPD 实验室", "🎛️")
state = ui.get_state()
ui.note("训练并评估数字预失真:**ILA**(经典最小二乘,基函数可选 GMP/DDR/MP)"
        "或 **DLA**(神经直接学习,需神经代理)。合成源用星座 EVM + WiFi "
        "Mask;OpenDPD 源自动切换其发表口径。实测源的评估需选择 PA 代理模型。")

with st.sidebar:
    st.subheader("数据源")
    opts = ["合成 ReferencePA"] + list(state.sources)
    src_name = st.selectbox("选择", opts)
    if src_name == "合成 ReferencePA":
        bw = st.select_slider("带宽 (MHz)", [20, 40, 80, 160, 320], 160) * 1e6
        qam = st.select_slider("QAM", [256, 1024, 4096], 1024)
        drive = st.slider("PA drive", 0.08, 0.24, 0.14, 0.01)
        cfr_on = st.toggle("CFR 削峰")
        cfr = st.slider("CFR 目标 PAPR (dB)", 5.0, 10.0, 8.0, 0.5,
                        disabled=not cfr_on)
        key = f"dpdsynth_{bw}_{qam}_{drive}_{cfr if cfr_on else None}"
        if key not in st.session_state:
            with st.spinner("准备合成数据源…"):
                st.session_state[key] = services.make_synthetic_source(
                    bw, qam, symbols=8, drive=drive,
                    cfr_papr_db=cfr if cfr_on else None)
        src = st.session_state[key]
    else:
        src = state.sources[src_name]

    st.subheader("DPD 方案")
    algo = st.radio("算法", ["ILA(经典)", "DLA(神经)"], horizontal=True)
    models = ui.model_options()
    if algo == "ILA(经典)":
        basis = st.selectbox("基函数族", ["GMP-510 (OpenDPD)",
                                          "DDR-140 (preset)",
                                          "MP-500 (OpenDPD)",
                                          "GMP", "DDR", "MP"])
        surrogate_name = None
        if src["kind"] != "synthetic":
            surrogate_name = st.selectbox(
                "评估代理(实测源必选)",
                list(models) or ["<先在 PA 建模页拟合一个模型>"])
    else:
        neural = {k: v for k, v in models.items()
                  if v["meta"]["config"].get("family") == "neural"}
        surrogate_name = st.selectbox(
            "可微 PA 代理(必选)",
            list(neural) or ["<先在 PA 建模页训练一个神经模型>"])
        epochs = st.slider("DPD epochs", 5, 100, 20)
        hidden = st.slider("DPD hidden", 4, 24, 8)

go = st.sidebar.button("🚀 运行 DPD", type="primary",
                       use_container_width=True)

if go:
    models = ui.model_options()
    try:
        if algo == "ILA(经典)":
            surrogate = (models[surrogate_name]["model"]
                         if surrogate_name in models else None)
            with st.spinner("ILA 辨识与评估中…"):
                out = services.run_dpd_ila(src, basis=basis,
                                           surrogate=surrogate)
            label = f"ILA-{basis}"
            cfg = {"algo": "ILA", "basis": basis, "source": src["name"]}
        else:
            if surrogate_name not in models:
                st.error("DLA 需要一个神经 PA 代理,请先在 PA 建模页训练。")
                st.stop()
            prog = st.progress(0.0, "DLA 训练中…")

            def cb(h):
                prog.progress(min(1.0, (h["epoch"] + 1) / epochs),
                              f"epoch {h['epoch']+1}/{epochs} · "
                              f"val {h['val_metric']:.2f} dB")

            out = services.run_dpd_dla(src, models[surrogate_name]["model"],
                                       hidden=hidden, epochs=epochs,
                                       on_epoch=cb)
            prog.empty()
            label = f"DLA-DGRU-H{hidden}"
            cfg = {"algo": "DLA", "hidden": hidden, "epochs": epochs,
                   "surrogate": surrogate_name, "source": src["name"]}
        st.session_state["last_dpd"] = {"out": out, "label": label,
                                        "src_name": src["name"]}
        m = out["metrics"]
        state.runstore.add(Run(
            name=f"{label} @ {src['name']}", kind="dpd", config=cfg,
            metrics={"evm_db": m["DPD"]["evm_db"],
                     "evm_before_db": m["no DPD"]["evm_db"],
                     "aclr_high_dbc": m["DPD"]["aclr_high"],
                     "aclr_before_dbc": m["no DPD"]["aclr_high"],
                     "convention": out["convention"]}))
    except Exception as e:
        st.error(f"运行失败:{e}")

last = st.session_state.get("last_dpd")
if last:
    out, m = last["out"], last["out"]["metrics"]
    st.subheader(f"结果:{last['label']} @ {last['src_name']}")
    conv = {"constellation": "星座域 EVM(padpd 原生)",
            "opendpd": "OpenDPD 口径(谱域)",
            "nmse-vs-linear": "NMSE vs 线性目标"}[out["convention"]]
    st.markdown(ui.badge(conv), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("EVM(无 DPD)", f"{m['no DPD']['evm_db']:.1f} dB")
    c2.metric("EVM(DPD 后)", f"{m['DPD']['evm_db']:.1f} dB",
              f"{m['DPD']['evm_db']-m['no DPD']['evm_db']:+.1f} dB")
    if m["DPD"]["aclr_high"] is not None:
        c3.metric("ACLR(无 DPD)", f"{m['no DPD']['aclr_high']:.1f} dBc")
        c4.metric("ACLR(DPD 后)", f"{m['DPD']['aclr_high']:.1f} dBc",
                  f"{m['DPD']['aclr_high']-m['no DPD']['aclr_high']:+.1f}")
    if m["DPD"]["mask"] != "-":
        st.markdown(
            ui.badge(f"Mask 无DPD: {m['no DPD']['mask']}",
                     "ok" if m['no DPD']['mask'] == "PASS" else "fail")
            + ui.badge(f"Mask DPD后: {m['DPD']['mask']}",
                       "ok" if m['DPD']['mask'] == "PASS" else "fail"),
            unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📶 PSD 前后对比", "✳️ 星座前后对比"])
    with tab1:
        curves = {"无 DPD": out["y_before"], "DPD 后": out["y_after"]}
        st.plotly_chart(charts.fig_psd(
            services.psd_pair(curves, out["fs"]), mask=out.get("mask")),
            use_container_width=True)
    with tab2:
        if out.get("wf") is not None:
            pts = {
                "无 DPD": services.constellation_points(
                    out["y_before"], out["wf"], out["gain"]),
                "DPD 后": services.constellation_points(
                    out["y_after"], out["wf"], out["gain"])}
            st.plotly_chart(charts.fig_constellation(pts),
                            use_container_width=True)
        else:
            st.caption("实测多载波源无星座解调(其信号含 CP/多载波结构),"
                       "请以 PSD 与谱域指标为准。")
else:
    st.info("在左侧配置数据源与 DPD 方案,点击「运行 DPD」。")
