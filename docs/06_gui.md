# 06 · 图形界面(双版本:Web 工作台 + 桌面版)

工程提供两个功能同构的 GUI,通过 GUI 即可使用全部功能:波形生成、数据
加载、PA 建模、DPD 实验、结果比较、定点部署导出、PA/DPD 联合设计。

| | 方案 A:Web 工作台 | 方案 B:桌面版 |
|---|---|---|
| 技术栈 | Streamlit + Plotly(交互缩放/hover) | PySide6 + matplotlib |
| 目录 | `gui/` | `gui_qt/` |
| 启动 | `streamlit run gui/app.py` | `python -m gui_qt.main` |
| 依赖 | `pip install -e .[gui]` | `pip install -e .[gui-qt]` |
| 定位 | 团队共享/远程访问/快速迭代 | 单机应用,可打包成免安装 exe |
| exe 打包 | 不做(见 `packaging/README_packaging.md`) | PyInstaller,`packaging/` 一键构建 |

两版共享同一套**框架无关服务层 `gui_core/`**(全部计算逻辑)与同一个
**实验注册表 `gui_runs/`**——在 Web 版跑的实验,桌面版的"结果比较"页
能看到,反之亦然;算法零重复,行为一致。

```
gui_core/
  services.py   # 计算服务:make_waveform / load_source(OpenDPD 目录、
                #   Cadence CSV、MATLAB .mat、IQDataset .npz,可选自动
                #   延迟对齐)/ fit_classical / fit_neural(on_epoch 进度
                #   回调)/ run_dpd_ila / run_dpd_dla / bitwidth_sweep /
                #   export_artifacts / constellation_points
  runstore.py   # RunStore:实验注册表,gui_runs/*.json 持久化
```

## 八个功能页(两版同构)

1. **总览**:代表性成果卡片(实测数字)、环境自检(torch/OpenDPD
   数据集/checkpoint/run 计数)、最近实验表。
2. **波形工作台**:带宽 20–320 MHz / 16–4096-QAM / 符号数 / 种子 →
   PAPR 指标卡 + PSD / CCDF / 星座 / 时域四图;可选 CFR 削峰对比
   (PAPR 与 EVM 代价并列);导出 IQDataset `.npz`。
3. **数据管理**:扫描 OpenDPD 数据集目录 / 打开 Cadence CSV、`.mat`、
   `.npz`;可选自动延迟对齐;spec 卡 + PSD / AM-AM 预览;注册为数据源
   供建模与 DPD 页使用。
4. **PA 建模**:数据源选合成 ReferencePA(可调 drive)或已注册实测源;
   经典 LS(MP/GMP/DDR 及 OpenDPD ~500 参数 preset)秒级闭式解,神经
   (GRU/DGRU/TCN)带逐 epoch 进度与实时验证 NMSE;NMSE/参数量指标卡
   + 实测 vs 预测 PSD + AM-AM/AM-PM;保存 checkpoint;注册模型与 run。
5. **DPD 实验室**:ILA(基函数 GMP-510/DDR-140/MP-500 或自定义)与
   DLA(神经直接学习,需先训练神经代理);合成源用星座 EVM + 发射
   Mask 口径,OpenDPD 源自动用其论文口径;前后 EVM/ACLR 指标卡 +
   PSD/星座前后对比;注册 run。
6. **结果比较**:全部 run 的表格(勾选/删除/导出 JSON),多选指标
   分组柱状对比(NMSE/EVM/ACLR)。
7. **部署**:模型多选 → 定点位宽扫描(W16–W8,bit-true)曲线与
   MAC/GMAC 成本表;导出交接产物:整数系数 JSON + 参考向量 CSV
   (经典/定点)与 ONNX(神经,含数值验证)。
8. **联合设计**:离散 Pareto 扫描(7 工作点 × DPD 阶梯搜索,可行域
   与预算线可视化,顺序设计 vs 联合设计对比卡)与可微梯度寻优
   (内层闭式 LS-DPD + 外层梯度,drive/EVM 轨迹图)。

## Web 版(Streamlit)

```bash
pip install -e .[gui]        # streamlit + plotly
streamlit run gui/app.py     # 浏览器打开 http://localhost:8501
```

- 深色工程主题(`.streamlit/config.toml` + `gui/ui.py` 全局 CSS),
  Plotly 图表统一深色模板(`gui/charts.py`)。
- 长任务(神经训练/DLA)有进度条与实时训练曲线。
- 测试:`tests/test_gui_web.py` 用 Streamlit AppTest 冒烟全部 8 页并
  端到端跑一次经典建模。

## 桌面版(PySide6)

```bash
pip install -e .[gui-qt]     # pyside6(matplotlib 已是主依赖)
python -m gui_qt.main
```

- 左侧导航 + 页面栈,QSS 深色主题(`gui_qt/style.qss`)与 Web 版
  视觉语言一致;图表为 matplotlib Qt canvas(`gui_qt/figs.py` 深色
  模板,自动选择系统中文字体)。
- 长任务跑在 `QThread`(`gui_qt/common.py: FnWorker`),UI 不卡顿,
  异常回传到界面而非崩溃。
- 无显示器环境用 `QT_QPA_PLATFORM=offscreen` 可运行(CI 冒烟即如此);
  测试:`tests/test_gui_qt.py`。

## 打包成 Windows exe

见 `packaging/README_packaging.md`。要点:PyInstaller 不能跨平台,
Windows exe 必须在 Windows 上跑 `packaging/build_windows.bat`
(`--no-torch` 得 ~400 MB 精简版,经典功能全可用;完整版含 torch)。
本仓库已在 Linux 用同一份 spec 完成 onedir 构建与启动冒烟。

## 已知边界

- 神经训练在 GUI 里默认小参数(epochs ≤ 100、hidden ≤ 32),复现
  论文级结果请用 `scripts/train_neural_pa.py` 等命令行脚本(支持
  完整 OpenDPD 训练配方)。
- DLA 与梯度联合设计需要 PyTorch;未安装时界面给出明确提示。
- Web 版上传大文件受 Streamlit 默认 200 MB 限制(可在
  `.streamlit/config.toml` 调整)。
