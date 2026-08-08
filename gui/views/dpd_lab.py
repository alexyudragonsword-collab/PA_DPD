import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import Run, services  # noqa: E402

ui.page_setup(ui.tr("DPD 实验室"), "🎛️")
state = ui.get_state()
ui.note(ui.tr("训练并评估数字预失真:**ILA**(经典最小二乘,基函数可选 "
              "GMP/DDR/MP)或 **DLA**(神经直接学习,需神经代理)。"
              "合成源用星座 EVM + WiFi Mask;OpenDPD 源自动切换其发表口径。"
              "实测源的评估需选择 PA 代理模型。"))

with st.sidebar:
    st.subheader(ui.tr("数据源"))
    opts = [ui.tr("合成 ReferencePA")] + list(state.sources)
    src_name = st.selectbox(ui.tr("选择"), opts)
    if src_name == ui.tr("合成 ReferencePA"):
        bw = st.select_slider(ui.tr("带宽 (MHz)"),
                              [20, 40, 80, 160, 320], 160) * 1e6
        qam = st.select_slider("QAM", [256, 1024, 4096], 1024)
        drive = st.slider("PA drive", 0.08, 0.24, 0.14, 0.01)
        cfr_on = st.toggle(ui.tr("CFR 削峰"))
        cfr = st.slider(ui.tr("CFR 目标 PAPR (dB)"), 5.0, 10.0, 8.0, 0.5,
                        disabled=not cfr_on)
        with st.spinner(ui.tr("准备合成数据源…")):
            src = services.cached_synthetic_source(
                bw, qam, symbols=8, drive=drive,
                cfr_papr_db=cfr if cfr_on else None)
    else:
        src = state.sources[src_name]

    st.subheader(ui.tr("DPD 方案"))
    algo = st.radio(ui.tr("算法"),
                    [ui.tr("ILA(经典)"), ui.tr("DLA(神经)")],
                    horizontal=True)
    models = ui.model_options()
    if algo == ui.tr("ILA(经典)"):
        basis = st.selectbox(ui.tr("基函数族"), ["GMP-510 (OpenDPD)",
                                                 "DDR-140 (preset)",
                                                 "MP-500 (OpenDPD)",
                                                 "GMP", "DDR", "MP",
                                                 "Spline-MP (K8,M4)",
                                                 "Spline-GMP (K8)",
                                                 "Spline-MP"])
        surrogate_name = None
        if src["kind"] != "synthetic":
            surrogate_name = st.selectbox(
                ui.tr("评估代理(实测源必选)"),
                list(models) or [ui.tr("<先在 PA 建模页拟合一个模型>")])
    else:
        neural = {k: v for k, v in models.items()
                  if v["meta"]["config"].get("family") == "neural"}
        surrogate_name = st.selectbox(
            ui.tr("可微 PA 代理(必选)"),
            list(neural) or [ui.tr("<先在 PA 建模页训练一个神经模型>")])
        epochs = st.slider("DPD epochs", 5, 100, 20)
        hidden = st.slider("DPD hidden", 4, 24, 8)

go = st.sidebar.button(ui.tr("🚀 运行 DPD"), type="primary",
                       use_container_width=True)

if go:
    models = ui.model_options()
    try:
        if algo == ui.tr("ILA(经典)"):
            surrogate = (models[surrogate_name]["model"]
                         if surrogate_name in models else None)
            with st.spinner(ui.tr("ILA 辨识与评估中…")):
                out = services.run_dpd_ila(src, basis=basis,
                                           surrogate=surrogate)
            label = f"ILA-{basis}"
            cfg = {"algo": "ILA", "basis": basis, "source": src["name"]}
        else:
            if surrogate_name not in models:
                st.error(ui.tr("DLA 需要一个神经 PA 代理,"
                               "请先在 PA 建模页训练。"))
                st.stop()
            prog = st.progress(0.0, ui.tr("DLA 训练中…"))

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
        st.error(ui.tr("运行失败:{e}").format(e=e))

last = st.session_state.get("last_dpd")
if last:
    out, m = last["out"], last["out"]["metrics"]
    st.subheader(ui.tr("结果:{name}").format(
        name=f"{last['label']} @ {last['src_name']}"))
    conv = {"constellation": ui.tr("星座域 EVM(padpd 原生)"),
            "opendpd": ui.tr("OpenDPD 口径(谱域)"),
            "nmse-vs-linear": ui.tr("NMSE vs 线性目标")}[out["convention"]]
    st.markdown(ui.badge(conv), unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(ui.tr("EVM(无 DPD)"), f"{m['no DPD']['evm_db']:.1f} dB")
    c2.metric(ui.tr("EVM(DPD 后)"), f"{m['DPD']['evm_db']:.1f} dB",
              f"{m['DPD']['evm_db']-m['no DPD']['evm_db']:+.1f} dB")
    if m["DPD"]["aclr_high"] is not None:
        c3.metric(ui.tr("ACLR(无 DPD)"),
                  f"{m['no DPD']['aclr_high']:.1f} dBc")
        c4.metric(ui.tr("ACLR(DPD 后)"),
                  f"{m['DPD']['aclr_high']:.1f} dBc",
                  f"{m['DPD']['aclr_high']-m['no DPD']['aclr_high']:+.1f}")
    if m["DPD"]["mask"] != "-":
        st.markdown(
            ui.badge(ui.tr("Mask 无DPD: {v}").format(v=m['no DPD']['mask']),
                     "ok" if m['no DPD']['mask'] == "PASS" else "fail")
            + ui.badge(ui.tr("Mask DPD后: {v}").format(v=m['DPD']['mask']),
                       "ok" if m['DPD']['mask'] == "PASS" else "fail"),
            unsafe_allow_html=True)

    tab1, tab2 = st.tabs([ui.tr("📶 PSD 前后对比"),
                          ui.tr("✳️ 星座前后对比")])
    with tab1:
        curves = {ui.tr("无 DPD"): out["y_before"],
                  ui.tr("DPD 后"): out["y_after"]}
        st.plotly_chart(charts.fig_psd(
            services.psd_pair(curves, out["fs"]), mask=out.get("mask")),
            use_container_width=True)
    with tab2:
        if out.get("wf") is not None:
            pts = {
                ui.tr("无 DPD"): services.constellation_points(
                    out["y_before"], out["wf"], out["gain"]),
                ui.tr("DPD 后"): services.constellation_points(
                    out["y_after"], out["wf"], out["gain"])}
            st.plotly_chart(charts.fig_constellation(pts),
                            use_container_width=True)
        else:
            st.caption(ui.tr("实测多载波源无星座解调"
                             "(其信号含 CP/多载波结构),"
                             "请以 PSD 与谱域指标为准。"))
else:
    st.info(ui.tr("在左侧配置数据源与 DPD 方案,点击「运行 DPD」。"))

st.divider()
with st.expander(ui.tr("🔁 自适应 / 在线 DPD(漂移跟踪)"), expanded=False):
    st.caption(ui.tr("在会漂移(温度/供电/老化)的合成 PA 上跑在线自适应 "
                     "DPD,与一次性冻结的批处理 DPD 逐块比较 EVM,演示现场"
                     "跟踪价值。三种方法(rls/whitened/apa)见手册 5.7。"))
    ac1, ac2, ac3, ac4, ac5, ac6, ac7, ac8 = st.columns(8)
    method = ac1.selectbox(ui.tr("自适应方法"),
                           list(services.ADAPTIVE_METHODS))
    ad_basis = ac7.selectbox(ui.tr("基底"), list(services.ADAPTIVE_BASES))
    ad_dut = ac8.selectbox(ui.tr("虚拟 DUT"), list(services.ADAPTIVE_DUTS))
    ad_bw = ac2.select_slider(ui.tr("带宽 (MHz)"), [20, 40, 80, 160, 320],
                              80, help=ui.tr("带宽越大采样率越高,自适应每块"
                                             "的计算越慢(80 MHz 为演示默认)"))
    n_blocks = ac3.slider(ui.tr("块数(冷 → 热)"), 4, 16, 10)
    drift_span = ac4.slider(ui.tr("漂移强度"), 0.01, 0.05, 0.02, 0.005)
    forget = ac5.slider("forget (RLS)", 0.50, 0.99, 0.60, 0.01)
    apa_k = ac6.slider("APA K", 1, 8, 4, 1,
                       help=ui.tr("APA 投影阶:K=1 即 NLMS,K 越大越接近 "
                                  "RLS(仅 method=apa 生效)"))
    if st.button(ui.tr("运行自适应 DPD"), type="primary"):
        with st.spinner(ui.tr("自适应跟踪中…")):
            res = services.run_adaptive_dpd(
                method=method, n_blocks=n_blocks, drift_span=drift_span,
                forget=forget, apa_k=apa_k, bw=ad_bw * 1e6,
                basis=ad_basis, dut=ad_dut)
        st.session_state["last_adaptive"] = res
        a_name, a_cfg, a_metrics = services.adaptive_run_record(res)
        state.runstore.add(Run(name=a_name, kind="dpd", config=a_cfg,
                               metrics=a_metrics))
    ares = st.session_state.get("last_adaptive")
    if ares:
        m1, m2, m3 = st.columns(3)
        m1.metric(ui.tr("EVM(冻结,满漂移)"),
                  f"{ares['final_frozen']:.1f} dB")
        m2.metric(ui.tr("EVM(自适应,满漂移)"),
                  f"{ares['final_adaptive']:.1f} dB",
                  f"{ares['final_adaptive'] - ares['final_frozen']:+.1f} dB")
        m3.metric(ui.tr("自适应领先"), f"{ares['gap_db']:.1f} dB")
        st.plotly_chart(charts.fig_adaptive_evm(ares),
                        use_container_width=True)
        st.caption(ui.tr("已注册为 run(kind=dpd),可在结果比较页与批处理 "
                         "DPD 并排对比。"))

with st.expander(ui.tr("🧲 前端三环:QMC + 观测去嵌 + 自适应 DPD"),
                 expanded=False):
    st.caption(ui.tr("漂移 PA + TX 前端(镜像/LO 泄漏)+ 污染环回(时延/"
                     "CFO/相噪/RX IQ/纹波/噪声):对比原始环回自适应"
                     "(失效)、仅去嵌(钉在 IRR)与三环联合(QMC 收编"
                     "镜像/DC,DPD 保持纯相位等变基)。见手册 5.9。"))
    tc1, tc2, tc3, tc4 = st.columns(4)
    tl_blocks = tc1.slider(ui.tr("块数(冷 → 热)"), 4, 16, 10,
                           key="tl_blocks")
    tl_span = tc2.slider(ui.tr("漂移强度"), 0.0, 0.05, 0.02, 0.005,
                         key="tl_span")
    tl_lo = tc3.slider(ui.tr("LO 泄漏 (dBc)"), -60.0, -20.0, -35.0, 1.0)
    tl_iq = tc4.slider(ui.tr("IQ 失衡 (dB)"), 0.0, 1.0, 0.3, 0.1,
                       help=ui.tr("相位失衡按 10x 联动(0.3 dB ≈ 3°,"
                                  "IRR ≈ 30 dB)"))
    if st.button(ui.tr("运行三环演示"), type="primary"):
        with st.spinner(ui.tr("三环联合运行中…")):
            res3 = services.run_three_loop_demo(
                n_blocks=tl_blocks, drift_span=tl_span, gain_db=tl_iq,
                phase_deg=10.0 * tl_iq, lo_leakage_dbc=tl_lo)
        st.session_state["last_three_loop"] = res3
        t_name, t_cfg, t_metrics = services.three_loop_run_record(res3)
        state.runstore.add(Run(name=t_name, kind="dpd", config=t_cfg,
                               metrics=t_metrics))
    tres = st.session_state.get("last_three_loop")
    if tres:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(ui.tr("EVM(原始环回)"), f"{tres['final_raw']:.1f} dB")
        m2.metric(ui.tr("EVM(仅去嵌)"), f"{tres['final_deembed']:.1f} dB")
        m3.metric(ui.tr("EVM(三环)"), f"{tres['final_full']:.1f} dB",
                  f"{tres['final_full'] - tres['final_deembed']:+.1f} dB")
        m4.metric(ui.tr("镜像残差"), f"{tres['final_image_dbc']:.1f} dBc")
        st.plotly_chart(charts.fig_three_loop(tres),
                        use_container_width=True)
        st.caption(ui.tr("已注册为 run(kind=dpd)。"))
