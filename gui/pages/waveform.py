import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from gui import charts, ui  # noqa: E402
from gui_core import services  # noqa: E402

ui.page_setup("波形工作台", "🌊")
ui.get_state()
ui.note("生成 802.11be 风格 OFDM 基带波形,查看 PSD / CCDF / 星座与 PAPR;"
        "可选 CFR 削峰对比;结果可下载为 IQDataset (.npz) 供外部使用。")

with st.sidebar:
    st.subheader("波形参数")
    bw = st.select_slider("信道带宽 (MHz)", [20, 40, 80, 160, 320], 80) * 1e6
    qam = st.select_slider("QAM 阶数", [16, 64, 256, 1024, 4096], 1024)
    symbols = st.slider("OFDM 符号数", 2, 40, 8)
    seed = st.number_input("随机种子", 0, 9999, 0)
    use_cfr = st.toggle("启用 CFR 削峰")
    cfr_papr = st.slider("CFR 目标 PAPR (dB)", 5.0, 10.0, 8.0, 0.5,
                         disabled=not use_cfr)


@st.cache_data(show_spinner="生成波形…")
def _gen(bw, qam, symbols, seed, cfr):
    w = services.make_waveform(bw, qam, symbols, seed, cfr)
    return w


w = _gen(bw, qam, symbols, int(seed), cfr_papr if use_cfr else None)
wf, fs = w["wf"], w["fs"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("采样率", f"{fs/1e6:.0f} MSPS", f"{wf.config.oversampling}× 过采样")
c2.metric("FFT / 有效子载波", f"{wf.config.fft_size} / {wf.config.n_active}")
c3.metric("PAPR", f"{w['papr_db']:.2f} dB")
if w["papr_cfr_db"] is not None:
    c4.metric("CFR 后 PAPR", f"{w['papr_cfr_db']:.2f} dB",
              f"EVM 代价 {w['cfr_evm_db']:.1f} dB", delta_color="off")
else:
    c4.metric("样本数", f"{len(w['x']):,}")

sig = {"原始波形": w["x"]}
if w["x_cfr"] is not None:
    sig["CFR 后"] = w["x_cfr"]

tab_psd, tab_ccdf, tab_const, tab_time = st.tabs(
    ["📶 PSD", "📉 CCDF", "✳️ 星座", "〰️ 时域"])

with tab_psd:
    st.plotly_chart(charts.fig_psd(services.psd_pair(sig, fs)),
                    use_container_width=True)
with tab_ccdf:
    st.plotly_chart(charts.fig_ccdf(services.ccdf_curves(sig)),
                    use_container_width=True)
with tab_const:
    st.plotly_chart(
        charts.fig_constellation({"发送星座": wf.tx_symbols.ravel()}),
        use_container_width=True)
with tab_time:
    import plotly.graph_objects as go
    n = min(2000, len(w["x"]))
    fig = charts._fig("时域包络(前 %d 采样)" % n)
    t = np.arange(n) / fs * 1e6
    for label, x in sig.items():
        fig.add_trace(go.Scatter(x=t, y=np.abs(x[:n]), name=label,
                                 mode="lines", line=dict(width=1)))
    fig.update_xaxes(title="时间 (µs)")
    fig.update_yaxes(title="|x|")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("导出")
col1, col2 = st.columns(2)
with col1:
    from padpd.data import IQDataset
    x_out = w["x_cfr"] if w["x_cfr"] is not None else w["x"]
    buf = io.BytesIO()
    np.savez_compressed(buf, x=x_out, y=x_out, sample_rate_hz=fs,
                        meta=np.array(repr({"source": "gui-waveform"})))
    st.download_button("⬇️ 下载波形 IQDataset (.npz)", buf.getvalue(),
                       file_name=f"waveform_{int(bw/1e6)}MHz_{qam}QAM.npz")
with col2:
    ui.note("提示:要把该波形送入虚拟 PA 生成建模数据,请前往 "
            "**📈 PA 建模** 页选择\"合成 ReferencePA\"数据源。")
