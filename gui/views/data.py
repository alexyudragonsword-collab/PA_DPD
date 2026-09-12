import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from gui import charts, ui
from gui_core import services

ui.page_setup(ui.tr("数据管理"), "🗂️")
state = ui.get_state()
ui.note(ui.tr("加载实测/仿真 PA 数据(输入输出 IQ 对),预览并注册为数据源,"
              "供 PA 建模与 DPD 页面使用。支持 OpenDPD 数据集目录、"
              "Cadence Envelope CSV、MATLAB .mat、IQDataset .npz。"))

tab_dir, tab_up, tab_tt = st.tabs([ui.tr("📁 OpenDPD 数据集目录"),
                                   ui.tr("⬆️ 上传文件"),
                                   ui.tr("〰️ 双音记忆诊断")])

with tab_dir:
    default = services.default_opendpd_dir()
    root = st.text_input(ui.tr("OpenDPD datasets 目录"), default)
    rootp = Path(root)
    if rootp.is_dir():
        names = sorted(p.name for p in rootp.iterdir()
                       if (p / "spec.json").exists())
        choice = st.selectbox(ui.tr("选择数据集"), names) if names else None
        if choice and st.button(ui.tr("加载数据集"), type="primary"):
            with st.spinner(ui.tr("加载中…")):
                src = services.load_source("opendpd", str(rootp / choice))
                state.sources[src["name"]] = src
            st.success(ui.tr("已注册数据源:{name}").format(name=src["name"]))
    else:
        st.warning(ui.tr("目录不存在。可 git clone lab-emi/OpenDPD "
                         "获取公开数据集。"))

with tab_up:
    kind = st.radio(ui.tr("文件类型"), ["cadence", "mat", "npz"],
                    horizontal=True,
                    format_func={"cadence": "Cadence CSV (time,i_in,q_in,"
                                            "i_out,q_out)",
                                 "mat": "MATLAB .mat (x,y,fs)",
                                 "npz": "IQDataset .npz"}.get)
    up = st.file_uploader(ui.tr("选择文件"), type=["csv", "mat", "npz"])
    fs_override = None
    if kind == "npz":
        st.caption(ui.tr("npz 同时支持完整实测源容器(可含 burst/step/"
                         "cal_rx/atten/多工况采集组,见手册第 4 章)。"))
        if st.button(ui.tr("载入完整源示例"
                           "(examples/complete_source_demo.npz)")):
            src = services.load_source("npz",
                                       services.EXAMPLE_COMPLETE_NPZ)
            state.sources[src["name"]] = src
            st.success(ui.tr("已注册数据源:{name}").format(
                name=src["name"]))
    auto_align = st.toggle(ui.tr("自动延迟对齐 (align_delay)"), value=False,
                           help=ui.tr("实测/仿真数据常有输入输出定时偏差,"
                                      "用互相关自动估计并消除整数+分数延迟"))
    if up and st.button(ui.tr("加载文件"), type="primary"):
        suffix = Path(up.name).suffix
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=suffix) as f:
            f.write(up.getvalue())
            tmp = f.name
        try:
            src = services.load_source(kind, tmp, fs_override, auto_align)
            src["name"] = up.name
            state.sources[up.name] = src
            st.success(ui.tr("已注册数据源:{name}").format(name=up.name))
            if src.get("align_info"):
                st.info(ui.tr("对齐:整数延迟 {lag},总延迟 {total} 采样")
                        .format(lag=src["align_info"]["lag"],
                                total=f"{src['align_info']['lag_total']:.2f}"))
        # surface load errors to the user
        except Exception as e:  # noqa: BLE001
            st.error(ui.tr("加载失败:{e}").format(e=e))

with tab_tt:
    st.caption(ui.tr("载入双音扫音间距的 IM3 表(电路仿真或实测),用记忆强度"
                     "预判 DPD 该预留多少记忆资源;系数仍用实测数据训练。"
                     "CSV 列:spacing_hz, im3_lower_dbc, im3_upper_dbc"
                     "[, im5_avg_dbc]。"))
    res = None
    if st.button(ui.tr("载入示例(examples/two_tone_example.csv)")):
        res = services.analyze_two_tone_csv(services.EXAMPLE_TWO_TONE_CSV)
    tt_up = st.file_uploader(ui.tr("上传双音 IM3 表 CSV"), type=["csv"],
                             key="tt_csv")
    if tt_up is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            f.write(tt_up.getvalue())
            tt_tmp = f.name
        try:
            res = services.analyze_two_tone_csv(tt_tmp)
        except Exception as e:  # noqa: BLE001
            st.error(ui.tr("加载失败:{e}").format(e=e))
    if res is not None:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(ui.tr("记忆强度"), f"{res['memory_strength_db']:.1f} dB")
        m2.metric(ui.tr("建议记忆深度"), str(res["memory_depth"]))
        m3.metric(ui.tr("GMP 交叉项"),
                  ui.tr("需要") if res["use_cross_terms"] else ui.tr("不需要"))
        m4.metric(ui.tr("估算系数量"), str(res["est_coeffs"]))
        st.caption(ui.tr("间距spread {spread:.1f} dB · 峰值不对称 "
                         "{asym:.1f} dB · 热记忆:{th}").format(
            spread=res["im3_spread_db"], asym=res["im3_asym_db"],
            th=ui.tr("疑似") if res["thermal_suspected"] else ui.tr("无")))
        st.plotly_chart(charts.fig_two_tone(res), use_container_width=True)
        st.info(res["rationale"])

st.divider()
st.subheader(ui.tr("已注册数据源"))
if not state.sources:
    st.caption(ui.tr("尚无数据源。加载数据集,或在 PA 建模页直接使用合成 "
                     "ReferencePA。"))
else:
    sel = st.selectbox(ui.tr("预览"), list(state.sources))
    src = state.sources[sel]
    prev = services.source_preview(src)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(ui.tr("采样率"), f"{src['fs']/1e6:.2f} MSPS")
    c2.metric("train / val / test",
              f"{prev['n_train']:,} / {prev['n_val']:,} / "
              f"{prev['n_test']:,}")
    spec = src.get("spec") or {}
    c3.metric(ui.tr("主带宽"), f"{(src.get('bw') or 0)/1e6:.0f} MHz"
              if src.get("bw") else "—")
    c4.metric(ui.tr("调制 / 子信道"),
              f"{spec.get('modulation','—')} / {spec.get('n_sub_ch','—')}")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.fig_psd(
            {ui.tr("PA 输入"): (prev["freq"], prev["psd_in"]),
             ui.tr("PA 输出"): (prev["freq"], prev["psd_out"])}),
            use_container_width=True)
    with col2:
        st.plotly_chart(charts.fig_amam(prev["amam"]),
                        use_container_width=True)

    if src.get("extras"):
        names = {"burst": ui.tr("突发"), "step": ui.tr("阶跃探针"),
                 "cal_rx": ui.tr("旁路标定"), "atten": ui.tr("衰减步进"),
                 "operating_points": ui.tr("多工况")}
        rows = services.source_extras_rows(src)
        st.markdown(ui.tr("**完整源采集组**:") + " · ".join(
            ("✅ " if r["present"] else "✖ ") + names[r["group"]]
            for r in rows))
        if st.button(ui.tr("运行完整源工具"),
                     help=ui.tr("对当前源可用的采集组一键跑:τ 辨识、"
                                "状态样条对比、RX 去嵌标定、跨工况调度器")):
            with st.spinner(ui.tr("完整源工具运行中…")):
                cx = services.consume_source_extras(src)
            st.session_state["last_extras"] = cx
        cx = st.session_state.get("last_extras")
        if cx:
            e1, e2, e3, e4 = st.columns(4)
            gm = cx.get("gain_mod")
            if gm and gm["significant"]:
                e1.metric(ui.tr("辨识 τ (µs)"),
                          " / ".join(f"{t:.1f}"
                                     for t in gm["taus_heat_us"]))
            stf = cx.get("state_fit")
            if stf:
                e2.metric(ui.tr("状态样条收益"),
                          f"+{stf['state_gain_db']:.1f} dB",
                          f"{stf['nmse_plain_db']:.1f} → "
                          f"{stf['nmse_state_db']:.1f} dB")
            de = cx.get("deembed")
            if de:
                e3.metric(ui.tr("RX 标定"),
                          f"IRR {de['rx_irr_db']:.1f} dB",
                          f"IM3 {de['rx_im3_dbc']:.1f} dBc")
            sc = cx.get("scheduler")
            if sc:
                e4.metric(ui.tr("跨工况调度"),
                          ui.tr("{n} 工况点").format(
                              n=len(sc["conditions"])),
                          " / ".join(f"{v:.0f}"
                                     for v in sc["nmse_per_point_db"]))
            errs = [v for k, v in cx.items() if k.endswith("_error")]
            if errs:
                st.warning("; ".join(errs))

    if st.button(ui.tr("移除该数据源")):
        del state.sources[sel]
        st.rerun()
