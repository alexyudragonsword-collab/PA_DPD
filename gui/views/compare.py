import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from gui import charts, ui

ui.page_setup(ui.tr("结果比较"), "⚖️")
state = ui.get_state()
ui.note(ui.tr("跨实验对比注册表中的 run(建模 / DPD / 部署)。"
              "注册表持久化在 gui_runs/,Web 版与桌面版共享。"))

runs = state.runstore.list()
if not runs:
    st.info(ui.tr("注册表为空——先在 PA 建模或 DPD 实验室页运行实验。"))
    st.stop()

kind = st.radio(ui.tr("类型筛选"),
                [ui.tr("全部"), "pa_model", "dpd", "deploy"],
                horizontal=True)
if kind != ui.tr("全部"):
    runs = [r for r in runs if r.kind == kind]
if not runs:
    st.info(ui.tr("该类型下暂无 run。"))
    st.stop()

rows = []
for r in runs:
    row = {ui.tr("选择"): False, ui.tr("时间"): r.when,
           ui.tr("名称"): r.name, ui.tr("类型"): r.kind}
    for k, v in r.metrics.items():
        row[k] = round(v, 2) if isinstance(v, float) else v
    row["_id"] = r.run_id
    rows.append(row)

_all_cols = {c for row in rows for c in row}
edited = st.data_editor(rows, use_container_width=True, hide_index=True,
                        disabled=[c for c in _all_cols
                                  if c != ui.tr("选择")],
                        column_config={"_id": None})
picked = [r for r, e in zip(runs, edited, strict=True)
          if e[ui.tr("选择")]]

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if picked and st.button(
            ui.tr("🗑️ 删除选中 ({n})").format(n=len(picked))):
        for r in picked:
            state.runstore.delete(r.run_id)
        st.rerun()
with col2:
    st.download_button(
        ui.tr("⬇️ 导出全部为 JSON"),
        json.dumps([{"name": r.name, "kind": r.kind, "config": r.config,
                     "metrics": r.metrics, "time": r.when}
                    for r in runs], indent=1, ensure_ascii=False,
                   default=str),
        file_name="padpd_runs.json")

if len(picked) >= 2:
    st.divider()
    st.subheader(ui.tr("对比({n} 项)").format(n=len(picked)))
    names = [r.name if len(r.name) < 36 else r.name[:33] + "…"
             for r in picked]
    metric_keys = sorted({k for r in picked for k, v in r.metrics.items()
                          if isinstance(v, (int, float))})
    chosen = st.multiselect(ui.tr("对比指标"), metric_keys,
                            default=[k for k in ("nmse_db", "evm_db",
                                                 "aclr_high_dbc")
                                     if k in metric_keys])
    if chosen:
        series = {k: [r.metrics.get(k) for r in picked] for k in chosen}
        st.plotly_chart(charts.fig_metric_bars(names, series),
                        use_container_width=True)
    with st.expander(ui.tr("配置明细")):
        st.json({r.name: r.config for r in picked})
elif picked:
    st.caption(ui.tr("再选一项即可出对比图。"))
