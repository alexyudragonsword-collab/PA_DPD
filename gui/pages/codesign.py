import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402

ui.page_setup(ui.tr("PA/DPD 联合设计"), "🧭")
ui.get_state()
ui.note(ui.tr("AI-Native 流程:PA 工作点与 DPD 复杂度联合优化,而非"
              "\"先设计 PA 再补救线性度\"。左:离散 Pareto 扫描(稳健);"
              "右:可微梯度寻优(快速定位,逼近可逆壁垒时会振荡)。"))

tab1, tab2 = st.tabs([ui.tr("📊 离散 Pareto 扫描"),
                      ui.tr("∇ 可微梯度寻优")])

with tab1:
    c1, c2, c3 = st.columns(3)
    evm_spec = c1.slider("EVM spec (dB)", -50, -30, -40, key="spec1")
    budget = c2.slider(ui.tr("DPD 系数预算"), 20, 200, 90)
    bw = c3.select_slider(ui.tr("带宽 (MHz)"), [20, 80, 160], 80,
                          key="bw1") * 1e6
    if st.button(ui.tr("运行扫描"), type="primary"):
        from padpd.codesign import codesign_sweep
        from padpd.waveform import OFDMConfig, generate_ofdm
        with st.spinner(ui.tr("扫描 7 个工作点(每点含 DPD 阶梯搜索)…")):
            cfg = OFDMConfig(bandwidth_hz=bw, qam_order=1024,
                             n_symbols=6, seed=0)
            tr = generate_ofdm(cfg)
            va = generate_ofdm(OFDMConfig(bandwidth_hz=bw, qam_order=1024,
                                          n_symbols=6, seed=1))
            rows = codesign_sweep([0.08, 0.10, 0.12, 0.14, 0.17, 0.20, 0.24],
                                  tr.x, va.x, va, evm_spec,
                                  cfg.sample_rate_hz, bw)
        st.session_state["cod_rows"] = (rows, budget, evm_spec)

    if "cod_rows" in st.session_state:
        rows, budget, evm_spec = st.session_state["cod_rows"]
        st.plotly_chart(charts.fig_codesign(rows, budget),
                        use_container_width=True)
        feasible = [r for r in rows
                    if r["feasible"] and r["dpd_cost"] <= budget]
        seq = max(rows, key=lambda r: r["pae"])
        c1, c2 = st.columns(2)
        c1.metric(ui.tr("顺序设计(先冲效率)"),
                  f"PAE {100*seq['pae']:.1f}%",
                  ui.tr("可行")
                  if seq["feasible"] and seq["dpd_cost"] <= budget
                  else ui.tr("撞墙:不可逆/超预算"), delta_color="off")
        if feasible:
            co = max(feasible, key=lambda r: r["pae"])
            c2.metric(ui.tr("联合设计(预算内最高效率)"),
                      f"PAE {100*co['pae']:.1f}%",
                      ui.tr("drive {drive} · {cost} 系数 · EVM {evm}")
                      .format(drive=f"{co['drive']:.2f}",
                              cost=co["dpd_cost"],
                              evm=f"{co['evm_dpd']:.1f}"),
                      delta_color="off")
        st.dataframe([{"drive": r["drive"], "PAE %": f"{100*r['pae']:.1f}",
                       ui.tr("EVM 无DPD"): f"{r['evm_nodpd']:.1f}",
                       ui.tr("DPD 系数"): r["dpd_cost"],
                       "EVM DPD": f"{r['evm_dpd']:.1f}",
                       ui.tr("可行"): "✅" if r["feasible"] else "❌"}
                      for r in rows],
                     use_container_width=True, hide_index=True)

with tab2:
    c1, c2, c3 = st.columns(3)
    spec2 = c1.slider("EVM spec (dB)", -50, -30, -38, key="spec2")
    drive0 = c2.slider(ui.tr("初始 drive(保守)"), 0.06, 0.14, 0.08, 0.01)
    steps = c3.slider(ui.tr("梯度步数"), 50, 300, 150)
    if st.button(ui.tr("运行梯度寻优"), type="primary"):
        try:
            from padpd.codesign_torch import joint_codesign
            from padpd.waveform import OFDMConfig, generate_ofdm
            with st.spinner(ui.tr("内层 LS-DPD + 外层梯度优化中…")):
                x = generate_ofdm(OFDMConfig(bandwidth_hz=80e6,
                                             qam_order=256, n_symbols=4,
                                             seed=0)).x
                base = joint_codesign(x, drive_init=drive0,
                                      evm_spec_db=spec2,
                                      learnable_drive=False)
                co = joint_codesign(x, drive_init=drive0, evm_spec_db=spec2,
                                    lambda_eff=3.0, steps=steps)
            st.session_state["cod_grad"] = (base, co, spec2)
        except ImportError:
            st.error(ui.tr("此功能需要 PyTorch。"))

    if "cod_grad" in st.session_state:
        base, co, spec2 = st.session_state["cod_grad"]
        c1, c2 = st.columns(2)
        c1.metric(ui.tr("保守设计(固定 drive)"),
                  f"PAE {100*base['efficiency']:.1f}%",
                  f"EVM {base['evm_db']:.1f} dB", delta_color="off")
        c2.metric(ui.tr("梯度联合优化"),
                  f"PAE {100*co['efficiency']:.1f}%",
                  f"drive→{co['drive']:.3f} · EVM {co['evm_db']:.1f} dB",
                  delta_color="off")
        import plotly.graph_objects as go
        h = co["history"]
        fig = charts._fig(ui.tr("优化轨迹"))
        fig.add_trace(go.Scatter(y=h["drive"], name="drive",
                                 line=dict(color=charts.PALETTE[1])))
        fig.add_trace(go.Scatter(y=h["evm_db"], name="EVM (dB)", yaxis="y2",
                                 line=dict(color=charts.PALETTE[0])))
        fig.update_layout(
            yaxis=dict(title="drive"),
            yaxis2=dict(title="EVM (dB)", overlaying="y", side="right",
                        gridcolor="#232c42"))
        fig.add_hline(y=spec2, line=dict(dash="dot"),
                      annotation_text="EVM spec", yref="y2")
        st.plotly_chart(fig, use_container_width=True)
