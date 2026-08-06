"""Shared i18n for both GUIs.

Keys are the original Chinese UI strings; ``tr(s, "en")`` looks up the
English translation and falls back to the key itself, so untranslated
strings degrade gracefully to Chinese instead of crashing.

Parameterised messages use ``str.format`` placeholders in both the key
and the translation, e.g. ``tr("已注册:{name}").format(name=...)``.
"""

from __future__ import annotations

LANGS = ("zh", "en")

_EN = {
    # ---- brand / navigation ----------------------------------------
    "padpd 工作台": "padpd Workbench",
    "padpd — WiFi 7 PA + DPD 工作台": "padpd — WiFi 7 PA + DPD Workbench",
    "WiFi 7 PA + DPD AI 辅助研发工作台":
        "WiFi 7 PA + DPD AI-assisted R&D workbench",
    "WiFi 7 PA + DPD 工作台": "WiFi 7 PA + DPD workbench",
    "总览": "Overview",
    "波形工作台": "Waveform Studio",
    "数据管理": "Data Manager",
    "PA 建模": "PA Modeling",
    "DPD 实验室": "DPD Lab",
    "结果比较": "Compare Runs",
    "部署": "Deployment",
    "联合设计": "Co-Design",
    "语言": "Language",
    "主题": "Theme",
    "用户手册": "User Manual",
    "目录": "Contents",
    "章节": "Chapter",
    "内置双语用户手册:整合快速入门、工作流、逐页操作指南、"
    "数据接口、算法速览、性能基准、部署打包与 FAQ;"
    "语言随侧栏切换。工程级细节见仓库 docs/ 目录。":
        "Built-in bilingual user manual: quick start, workflow, "
        "page-by-page guide, data interfaces, algorithms, benchmarks, "
        "deployment & FAQ. Language follows the sidebar switch; "
        "engineering details live in the repo's docs/ directory.",
    "内置双语用户手册:快速入门、工作流、逐页指南、数据接口、"
    "算法速览、性能基准、部署打包与 FAQ;语言随侧栏切换,"
    "工程级细节见仓库 docs/ 目录。":
        "Built-in bilingual user manual: quick start, workflow, "
        "page-by-page guide, data interfaces, algorithms, benchmarks, "
        "deployment & FAQ. Language follows the sidebar switch; "
        "engineering details live in the repo's docs/ directory.",
    "深色": "Dark",
    "浅色": "Light",
    "中文": "中文",
    # ---- home -------------------------------------------------------
    "padpd 工作台总览": "padpd Workbench Overview",
    "WiFi 7(802.11be)PA 行为建模与数字预失真的完整研发平台:":
        "A complete R&D platform for WiFi 7 (802.11be) PA behavioral "
        "modeling and digital predistortion: ",
    "经典(Saleh/MP/GMP/DDR)与神经(GRU/DGRU/TCN)模型、":
        "classical (Saleh/MP/GMP/DDR) and neural (GRU/DGRU/TCN) models, ",
    "ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。":
        "ILA/DLA predistortion, CFR, fixed-point deployment and PA/DPD "
        "co-design.",
    "WiFi 7(802.11be)PA 行为建模与数字预失真研发平台:经典与神经":
        "WiFi 7 (802.11be) PA behavioral modeling & DPD platform: "
        "classical and neural ",
    "模型、ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。":
        "models, ILA/DLA predistortion, CFR, fixed-point deployment and "
        "PA/DPD co-design.",
    "代表性成果(实测)": "Representative results (measured)",
    "合成链路 DPD 后 EVM": "Synthetic-link EVM after DPD",
    "TCN vs GMP(真实数据)": "TCN vs GMP (measured data)",
    "TCN vs GMP(真实数据 NMSE)": "TCN vs GMP (measured NMSE)",
    "超经典基线": "beats classical baseline",
    "+1.2 dB 超经典基线": "+1.2 dB over classical baseline",
    "过 -52 验收线": "clears the -52 acceptance line",
    "APA 代理重评": "APA surrogate re-eval",
    "APA 代理重评 ACLR": "APA surrogate re-eval ACLR",
    "≈发表值 -38.80": "≈ published -38.80",
    "环境自检": "Environment self-check",
    "✅ PyTorch {v}(神经建模可用)":
        "✅ PyTorch {v} (neural modeling available)",
    "⚠️ PyTorch 未安装(神经功能不可用)":
        "⚠️ PyTorch not installed (neural features unavailable)",
    " 神经建模可用": " neural modeling available",
    " 神经页面不可用": " neural pages unavailable",
    "PyTorch 未安装": "PyTorch not installed",
    "✅ OpenDPD 数据集:{path}": "✅ OpenDPD datasets: {path}",
    "ℹ️ OpenDPD 未找到(可在数据页指定)":
        "ℹ️ OpenDPD not found (set the path on the Data page)",
    "OpenDPD 未找到": "OpenDPD not found",
    " 可在数据页手动指定": " set the path on the Data page",
    "OpenDPD × {n} 数据集": "OpenDPD × {n} datasets",
    "模型 checkpoint × {n}": "model checkpoints × {n}",
    "实验 run × {n}": "runs × {n}",
    "工作流": "Workflow",
    "最近实验": "Recent runs",
    "时间": "Time",
    "名称": "Name",
    "类型": "Kind",
    "指标": "Metrics",
    # ---- waveform ---------------------------------------------------
    "生成 802.11be 风格 OFDM 基带波形,查看 PSD / CCDF / 星座与 PAPR;":
        "Generate an 802.11be-style OFDM baseband waveform and inspect "
        "PSD / CCDF / constellation / PAPR; ",
    "可选 CFR 削峰对比;结果可下载为 IQDataset (.npz) 供外部使用。":
        "optional CFR clipping comparison; download as IQDataset (.npz).",
    "生成 802.11be 风格 OFDM 基带波形;PSD / CCDF / 星座 / 时域;":
        "Generate an 802.11be-style OFDM baseband waveform; PSD / CCDF / "
        "constellation / time domain; ",
    "可选 CFR 削峰对比;可导出 IQDataset (.npz)。":
        "optional CFR comparison; export as IQDataset (.npz).",
    "波形参数": "Waveform parameters",
    "信道带宽 (MHz)": "Channel bandwidth (MHz)",
    "带宽 (MHz)": "Bandwidth (MHz)",
    "带宽(MHz)": "Bandwidth (MHz)",
    "QAM 阶数": "QAM order",
    "OFDM 符号数": "OFDM symbols",
    "符号数": "Symbols",
    "随机种子": "Random seed",
    "种子": "Seed",
    "启用 CFR 削峰": "Enable CFR clipping",
    "CFR 削峰": "CFR clipping",
    "CFR 目标 PAPR (dB)": "CFR target PAPR (dB)",
    "生成波形": "Generate",
    "生成波形…": "Generating waveform…",
    "采样率": "Sample rate",
    "FFT / 有效子载波": "FFT / active subcarriers",
    "{n}× 过采样": "{n}× oversampling",
    "CFR 后 PAPR": "PAPR after CFR",
    "CFR 后 PAPR / EVM 代价": "PAPR after CFR / EVM cost",
    "EVM 代价 {evm:.1f} dB": "EVM cost {evm:.1f} dB",
    "样本数": "Samples",
    "原始波形": "Original",
    "CFR 后": "After CFR",
    "发送星座": "TX constellation",
    "功率谱密度 (PSD)": "Power spectral density (PSD)",
    "CCDF 峰值统计": "CCDF peak statistics",
    "星座": "Constellation",
    "星座图": "Constellation",
    "时域": "Time domain",
    "时域包络(前 %d 采样)": "Time-domain envelope (first %d samples)",
    "⬇️ 下载波形 IQDataset (.npz)": "⬇️ Download IQDataset (.npz)",
    "导出 .npz": "Export .npz",
    "导出波形": "Export waveform",
    "提示:要把该波形送入虚拟 PA 生成建模数据,请前往 ":
        "Tip: to drive the virtual PA with this waveform, go to ",
    "频率 (MHz)": "Frequency (MHz)",
    "高于平均功率 (dB)": "dB above average power",
    "时间 (µs)": "Time (µs)",
    "增益": "Gain",
    "相移": "Phase shift",
    "相移 (°)": "Phase shift (°)",
    "发射 Mask": "Spectral mask",
    "无 DPD": "no DPD",
    "DPD 后": "with DPD",
    "PA 输入": "PA input",
    "PA 输出": "PA output",
    "实测输出": "Measured output",
    "实测 PA 输出": "Measured PA output",
    "模型预测": "Model prediction",
    "训练曲线": "Training curve",
    "优化轨迹": "Optimization trajectory",
    "梯度步": "Gradient step",
    # ---- data -------------------------------------------------------
    "加载实测/仿真 PA 数据(输入输出 IQ 对),预览并注册为数据源,":
        "Load measured/simulated PA data (input/output IQ pairs), preview "
        "and register as a data source ",
    "供 PA 建模与 DPD 页面使用。支持 OpenDPD 数据集目录、":
        "for the modeling and DPD pages. Supports OpenDPD dataset dirs, ",
    "Cadence CSV、MATLAB .mat、IQDataset .npz;可选自动延迟对齐。":
        "Cadence CSV, MATLAB .mat, IQDataset .npz; optional auto delay "
        "alignment.",
    "加载实测/仿真 PA 数据并注册为数据源:OpenDPD 数据集目录、":
        "Load measured/simulated PA data and register it as a source: "
        "OpenDPD dataset dirs, ",
    "📁 OpenDPD 数据集目录": "📁 OpenDPD dataset directory",
    "⬆️ 上传文件": "⬆️ Upload file",
    "OpenDPD datasets 目录": "OpenDPD datasets directory",
    "OpenDPD 目录": "OpenDPD directory",
    "扫描目录": "Scan",
    "浏览…": "Browse…",
    "选择 OpenDPD 的 datasets 目录":
        "Select the OpenDPD datasets directory",
    "扫描到 {n} 个数据集": "Found {n} datasets",
    "该目录下没有 OpenDPD 数据集(缺 spec.json)":
        "No OpenDPD datasets here (no spec.json found)",
    "目录不存在:{path}": "Directory does not exist: {path}",
    "选择数据集": "Dataset",
    "加载数据集": "Load dataset",
    "加载文件": "Load file",
    "加载": "Load",
    "加载中…": "Loading…",
    "加载失败:{e}": "Load failed: {e}",
    "❌ 加载失败:{e}": "❌ Load failed: {e}",
    "目录不存在。可 git clone lab-emi/OpenDPD 获取公开数据集。":
        "Directory not found. git clone lab-emi/OpenDPD for the public "
        "datasets.",
    "文件类型": "File type",
    "选择文件": "Choose file",
    "打开文件 (CSV/.mat/.npz)…": "Open file (CSV/.mat/.npz)…",
    "打开数据文件": "Open data file",
    "数据 (*.csv *.mat *.npz);;全部 (*)":
        "Data (*.csv *.mat *.npz);;All (*)",
    "自动延迟对齐": "Auto delay alignment",
    "自动延迟对齐 (align_delay)": "Auto delay alignment (align_delay)",
    "实测/仿真数据常有输入输出定时偏差,":
        "Measured/simulated data often has an input/output timing offset; ",
    "用互相关自动估计并消除整数+分数延迟":
        "cross-correlation estimates and removes integer+fractional delay",
    "已注册数据源": "Registered sources",
    "已注册数据源:{name}": "Registered source: {name}",
    "对齐:延迟 {lag:.2f} 采样": "Aligned: delay {lag:.2f} samples",
    "✅ 已注册:{name}": "✅ Registered: {name}",
    "移除": "Remove",
    "移除该数据源": "Remove this source",
    # ---- two-tone memory diagnostics -------------------------------
    "〰️ 双音记忆诊断": "〰️ Two-tone memory",
    "双音记忆诊断": "Two-tone memory diagnostics",
    "双音 IM3": "Two-tone IM3",
    "双音 IM3 vs 音间距": "Two-tone IM3 vs spacing",
    "下边带 IM3": "Lower IM3",
    "上边带 IM3": "Upper IM3",
    "音间距 (MHz)": "Tone spacing (MHz)",
    "载入双音扫音间距的 IM3 表(电路仿真或实测),用记忆强度预判 DPD 该预留多少记忆资源;"
    "系数仍用实测数据训练。CSV 列:spacing_hz, im3_lower_dbc, im3_upper_dbc"
    "[, im5_avg_dbc]。":
        "Load a two-tone IM3-vs-spacing table (circuit sim or bench); the "
        "memory strength sizes how much DPD memory to reserve — the "
        "coefficients are still trained on measured data. CSV columns: "
        "spacing_hz, im3_lower_dbc, im3_upper_dbc[, im5_avg_dbc].",
    "载入双音扫音间距的 IM3 表(电路仿真或实测),用记忆强度预判 DPD 该预留多少记忆;"
    "系数仍用实测训练。":
        "Load a two-tone IM3-vs-spacing table (circuit sim or bench); the "
        "memory strength sizes how much DPD memory to reserve. The "
        "coefficients are still trained on measured data.",
    "载入示例(examples/two_tone_example.csv)":
        "Load example (examples/two_tone_example.csv)",
    "载入示例": "Load example",
    "载入双音 IM3 表 (CSV)…": "Load two-tone IM3 table (CSV)…",
    "载入双音 IM3 表": "Load two-tone IM3 table",
    "上传双音 IM3 表 CSV": "Upload two-tone IM3 table CSV",
    "CSV (*.csv);;全部 (*)": "CSV (*.csv);;All (*)",
    "记忆强度": "Memory strength",
    "建议记忆深度": "Suggested memory depth",
    "GMP 交叉项": "GMP cross terms",
    "估算系数量": "Est. coefficients",
    "需要": "yes",
    "不需要": "no",
    "疑似": "suspected",
    "无": "none",
    "间距spread {spread:.1f} dB · 峰值不对称 {asym:.1f} dB · 热记忆:{th}":
        "spacing spread {spread:.1f} dB · peak asymmetry {asym:.1f} dB · "
        "thermal: {th}",
    "记忆强度 {ms:.1f} dB → 建议记忆深度 {d}、交叉项 {cx}(约 {nc} 系数);"
    "热记忆 {th}。系数仍用实测训练。":
        "Memory strength {ms:.1f} dB → reserve memory depth {d}, cross "
        "terms {cx} (~{nc} coeffs); thermal memory {th}. Coefficients are "
        "still trained on measured data.",
    # ---- adaptive / online DPD (drift tracking) --------------------
    "🔁 自适应 / 在线 DPD(漂移跟踪)":
        "🔁 Adaptive / online DPD (drift tracking)",
    "自适应 / 在线 DPD(漂移跟踪)":
        "Adaptive / online DPD (drift tracking)",
    "自适应(漂移)": "Adaptive (drift)",
    "在会漂移(温度/供电/老化)的合成 PA 上跑在线自适应 DPD,与一次性冻结的批处理 "
    "DPD 逐块比较 EVM,演示现场跟踪价值。三种方法(rls/whitened/apa)见手册 5.7。":
        "Run an online adaptive DPD on a synthetic PA that drifts "
        "(temperature/supply/aging) and compare its per-block EVM against a "
        "once-frozen batch DPD, showing the field value of adaptation. The "
        "three methods (rls/whitened/apa) are covered in manual 5.7.",
    "在会漂移的合成 PA 上比较自适应 vs 冻结批处理 DPD 的逐块 EVM。":
        "Compare adaptive vs frozen batch DPD per-block EVM on a synthetic "
        "drifting PA.",
    "自适应方法": "Adaptive method",
    "方法": "Method",
    "APA 投影阶:K=1 即 NLMS,K 越大越接近 RLS(仅 method=apa 生效)":
        "APA projection order: K=1 is NLMS, larger K approaches RLS "
        "(only affects method=apa)",
    "有任务正在运行,请等待完成后再切换语言/主题。":
        "A task is still running; wait for it to finish before switching "
        "language/theme.",
    "有任务正在运行,确定要退出吗?":
        "A task is still running. Quit anyway?",
    "带宽越大采样率越高,自适应每块的计算越慢(80 MHz 为演示默认)":
        "Wider bandwidth means a higher sample rate, so each adaptation "
        "block computes more slowly (80 MHz is the demo default)",
    "块数(冷 → 热)": "Blocks (cold → hot)",
    "块数": "Blocks",
    "漂移强度": "Drift span",
    "漂移": "Drift",
    "运行自适应 DPD": "Run adaptive DPD",
    "自适应跟踪中…": "Adapting…",
    "EVM(冻结,满漂移)": "EVM (frozen, full drift)",
    "EVM(自适应,满漂移)": "EVM (adaptive, full drift)",
    "自适应领先": "Adaptive lead",
    "漂移跟踪:每块 EVM": "Drift tracking: per-block EVM",
    "冻结批处理 DPD": "Frozen batch DPD",
    "自适应 {m}": "Adaptive {m}",
    "块(冷 → 热)": "Block (cold → hot)",
    "满漂移 EVM:冻结 {f:.1f} dB → 自适应 {m} {a:.1f} dB(领先 {g:.1f} dB)":
        "Full-drift EVM: frozen {f:.1f} dB → adaptive {m} {a:.1f} dB "
        "(lead {g:.1f} dB)",
    "满漂移 EVM:冻结 {f:.1f} dB → 自适应 {m} {a:.1f} dB(领先 {g:.1f} dB);"
    "已注册为 run。":
        "Full-drift EVM: frozen {f:.1f} dB → adaptive {m} {a:.1f} dB "
        "(lead {g:.1f} dB); registered as a run.",
    "已注册为 run(kind=dpd),可在结果比较页与批处理 DPD 并排对比。":
        "Registered as a run (kind=dpd); compare it against batch DPD on "
        "the Compare Runs page.",
    "train / val / test": "train / val / test",
    "主带宽": "Main bandwidth",
    "调制 / 子信道": "Modulation / sub-channels",
    "对齐:整数延迟 {lag},总延迟 {total:.2f} 采样":
        "Aligned: integer lag {lag}, total delay {total:.2f} samples",
    "结果:{name}": "Result: {name}",
    "运行失败:{e}": "Run failed: {e}",
    "已保存 {fname}": "Saved {fname}",
    "预览": "Preview",
    "尚无数据源。加载数据集,或在 PA 建模页直接使用合成 ":
        "No sources yet. Load a dataset, or use the synthetic ",
    "数据源。": "source directly on the PA Modeling page.",
    # ---- modeling ---------------------------------------------------
    "用经典(LS 闭式解)或神经(梯度训练)模型拟合 PA 行为。":
        "Fit PA behavior with classical (closed-form LS) or neural "
        "(gradient-trained) models. ",
    "拟合好的模型可注册为 DPD 评估代理、进入部署页定点分析。":
        "Fitted models become DPD evaluation surrogates and feed the "
        "Deployment page.",
    "经典(LS 闭式解)或神经(SGD)模型拟合 PA 行为;拟合好的模型":
        "Fit PA behavior with classical (closed-form LS) or neural (SGD) "
        "models; fitted models ",
    "可作为 DPD 评估代理并进入部署页。":
        "serve as DPD evaluation surrogates and feed the Deployment page.",
    "数据源": "Data source",
    "合成 ReferencePA": "Synthetic ReferencePA",
    "PA 工作点 (drive)": "PA operating point (drive)",
    "PA 工作点 drive": "PA operating point (drive)",
    "模型族": "Model family",
    "经典 (LS)": "Classical (LS)",
    "神经 (SGD)": "Neural (SGD)",
    "经典": "Classical",
    "类型": "Type",
    "非线性阶数": "Nonlinear order",
    "阶数": "Order",
    "记忆深度": "Memory depth",
    "记忆": "Memory",
    "🚀 拟合模型": "🚀 Fit model",
    "拟合模型": "Fit model",
    "最小二乘拟合中…": "Least-squares fitting…",
    "神经训练中…": "Neural training…",
    "准备合成数据源…": "Preparing synthetic source…",
    "测试 NMSE": "Test NMSE",
    "参数量": "Parameters",
    "保存中…": "Saving…",
    "PSD:实测 vs 预测": "PSD: measured vs predicted",
    "AM-AM / AM-PM(预测)": "AM-AM / AM-PM (predicted)",
    "保存": "Save",
    "checkpoint 文件名": "Checkpoint filename",
    "💾 保存 checkpoint": "💾 Save checkpoint",
    "保存 checkpoint…": "Save checkpoint…",
    "保存模型": "Save model",
    "已保存 {fname}": "Saved {fname}",
    "💾 已保存 {path}": "💾 Saved {path}",
    "在左侧选择数据源与模型,点击「拟合模型」。":
        "Pick a source and model on the left, then click \"Fit model\".",
    "本会话模型注册表": "Session model registry",
    "模型": "Model",
    "参数": "Params",
    "✅ {name} 已注册": "✅ {name} registered",
    "配置": "Configuration",
    "配置明细": "Configuration detail",
    # ---- dpd --------------------------------------------------------
    "训练并评估数字预失真:**ILA**(经典最小二乘,基函数可选 GMP/DDR/MP)":
        "Train and evaluate digital predistortion: **ILA** (classical "
        "least-squares over GMP/DDR/MP bases) ",
    "或 **DLA**(神经直接学习,需神经代理)。合成源用星座 EVM + WiFi ":
        "or **DLA** (neural direct learning, needs a neural surrogate). "
        "Synthetic sources use constellation EVM + the WiFi ",
    "Mask;OpenDPD 源自动切换其发表口径。实测源的评估需选择 PA 代理模型。":
        "mask; OpenDPD sources switch to their published conventions. "
        "Measured sources need a PA surrogate for evaluation.",
    "ILA(经典 LS,基函数 GMP/DDR/MP)或 DLA(神经直接学习,需神经":
        "ILA (classical LS over GMP/DDR/MP bases) or DLA (neural direct "
        "learning, needs a neural ",
    "代理);合成源用星座 EVM+Mask,OpenDPD 源自动用其口径;":
        "surrogate); synthetic sources use constellation EVM + mask, "
        "OpenDPD sources use their conventions; ",
    "实测源评估需选 PA 代理。":
        "measured sources need a PA surrogate.",
    "DPD 方案": "DPD scheme",
    "算法": "Algorithm",
    "ILA(经典)": "ILA (classical)",
    "DLA(神经)": "DLA (neural)",
    "基函数族": "Basis family",
    "基函数": "Basis",
    "代理": "Surrogate",
    "可微 PA 代理(必选)": "Differentiable PA surrogate (required)",
    "评估代理(实测源必选)": "Evaluation surrogate (required for measured)",
    "<先在 PA 建模页拟合一个模型>": "<fit a model on PA Modeling first>",
    "<先在 PA 建模页训练一个神经模型>":
        "<train a neural model on PA Modeling first>",
    "<先在建模页拟合模型>": "<fit a model on PA Modeling first>",
    "<无模型>": "<no models>",
    "先在 📈 PA 建模页拟合至少一个模型。":
        "Fit at least one model on the 📈 PA Modeling page first.",
    "先在建模页拟合模型": "Fit a model on the PA Modeling page first",
    "🚀 运行 DPD": "🚀 Run DPD",
    "运行 DPD": "Run DPD",
    "ILA 辨识与评估中…": "ILA identification and evaluation…",
    "DLA 训练中…": "DLA training…",
    "DLA 需要一个神经 PA 代理,请先在 PA 建模页训练。":
        "DLA needs a neural PA surrogate; train one on PA Modeling first.",
    "❌ DLA 需要先在建模页训练神经代理":
        "❌ DLA needs a neural surrogate — train one on PA Modeling first",
    "在左侧配置数据源与 DPD 方案,点击「运行 DPD」。":
        "Configure the source and DPD scheme on the left, then click "
        "\"Run DPD\".",
    "运行失败:{e}": "Run failed: {e}",
    "EVM(无 DPD)": "EVM (no DPD)",
    "EVM(DPD 后)": "EVM (with DPD)",
    "ACLR(无 DPD)": "ACLR (no DPD)",
    "ACLR(DPD 后)": "ACLR (with DPD)",
    "星座域 EVM(padpd 原生)": "Constellation EVM (padpd native)",
    "OpenDPD 口径(谱域)": "OpenDPD convention (spectral)",
    "NMSE vs 线性目标": "NMSE vs linear target",
    "📶 PSD 前后对比": "📶 PSD before/after",
    "PSD 前后对比": "PSD before/after",
    "✳️ 星座前后对比": "✳️ Constellation before/after",
    "星座前后对比": "Constellation before/after",
    "✳️ 星座": "✳️ Constellation",
    "〰️ 时域": "〰️ Time domain",
    "实测多载波源无星座解调(其信号含 CP/多载波结构),":
        "Measured multi-carrier sources have no constellation demod "
        "(CP/multi-carrier structure); ",
    "请以 PSD 与谱域指标为准。":
        "rely on PSD and spectral metrics instead.",
    "✅ {label} 完成({conv} 口径),已注册 run":
        "✅ {label} done ({conv} convention), run registered",
    # ---- compare ----------------------------------------------------
    "跨实验对比注册表中的 run(建模 / DPD / 部署)。注册表持久化在 ":
        "Compare registered runs across experiments (modeling / DPD / "
        "deployment). The registry persists in ",
    "gui_runs/,Web 版与桌面版共享。":
        "gui_runs/, shared between the web and desktop GUIs.",
    "勾选 run 进行对比;注册表持久化于 gui_runs/,与 Web 版共享。":
        "Tick runs to compare; the registry persists in gui_runs/, shared "
        "with the web GUI.",
    "注册表为空——先在 PA 建模或 DPD 实验室页运行实验。":
        "Registry is empty — run an experiment on PA Modeling or DPD Lab "
        "first.",
    "类型筛选": "Filter by kind",
    "全部": "All",
    "选择": "Select",
    "对比选中": "Compare selected",
    "删除选中": "Delete selected",
    "🗑️ 删除选中 ({n})": "🗑️ Delete selected ({n})",
    "⬇️ 导出全部为 JSON": "⬇️ Export all as JSON",
    "导出 JSON…": "Export JSON…",
    "刷新": "Refresh",
    "对比指标": "Metrics to compare",
    "指标对比": "Metric comparison",
    "再选一项即可出对比图。": "Select one more run to draw the chart.",
    "至少勾选 2 项": "Tick at least 2 runs",
    "对比 {n} 项": "Comparing {n} runs",
    "对比({n} 项)": "Comparison ({n} runs)",
    "导出": "Export",
    # ---- deploy -----------------------------------------------------
    "对拟合好的模型做定点位宽扫描(bit-true)与硬件成本估计,":
        "Bit-true fixed-point bit-width sweep and hardware cost estimate "
        "for fitted models; ",
    "导出 FPGA/ASIC 交接产物:整数系数 JSON、参考向量 CSV、":
        "export FPGA/ASIC hand-off artifacts: integer-coefficient JSON, "
        "reference-vector CSV, ",
    "神经模型 ONNX。经典模型免训练直接量化(PTQ);神经模型权重+激活 PTQ。":
        "neural ONNX. Classical models quantize directly (PTQ); neural "
        "models get weight+activation PTQ.",
    "定点位宽扫描(bit-true)+ 硬件成本估计;导出 FPGA/ASIC 交接":
        "Bit-true bit-width sweep + hardware cost estimate; export "
        "FPGA/ASIC hand-off ",
    "产物:整数系数 JSON、参考向量 CSV、神经模型 ONNX。":
        "artifacts: integer-coefficient JSON, reference-vector CSV, "
        "neural ONNX.",
    "对象": "Target",
    "模型(可多选对比)": "Models (multi-select to compare)",
    "模型(勾选)": "Models (tick)",
    "位宽": "Bit widths",
    "评估数据源": "Evaluation source",
    "<拟合时的源>": "<source used at fit>",
    "🚀 位宽扫描": "🚀 Bit-width sweep",
    "位宽扫描": "Bit-width sweep",
    "位宽 vs 精度": "Bit width vs accuracy",
    "定点位宽 vs 精度": "Fixed-point bit width vs accuracy",
    "扫描中…": "Sweeping…",
    "MAC/样本": "MAC/sample",
    "请先勾选至少一个模型和位宽":
        "Tick at least one model and one bit width first",
    "✅ 扫描完成({n} 模型),已注册 run":
        "✅ Sweep done ({n} models), runs registered",
    "导出交接产物": "Export hand-off artifacts",
    "系数位宽": "Coefficient bit width",
    "📦 生成产物": "📦 Generate artifacts",
    "生成产物到目录…": "Generate artifacts to directory…",
    "选择导出目录": "Choose export directory",
    "导出中…": "Exporting…",
    "❌ 导出失败:{e}": "❌ Export failed: {e}",
    "ONNX 数值验证 ": "ONNX numerical check ",
    "ONNX 数值验证": "ONNX numerical check",
    "RTL bit-true 验证": "RTL bit-true check",
    "RTL bit-true 验证通过": "RTL bit-true check passed",
    "RTL bit-true 验证跳过": "RTL bit-true check skipped",
    "✅ 通过": "✅ passed",
    "通过": "passed",
    "跳过": "skipped",
    # ---- codesign ---------------------------------------------------
    "PA/DPD 联合设计": "PA/DPD Co-Design",
    "PA/DPD 联合设计权衡": "PA/DPD co-design trade-off",
    "AI-Native 流程:PA 工作点与 DPD 复杂度联合优化,而非":
        "AI-native flow: jointly optimize the PA operating point and DPD "
        "complexity, instead of ",
    "。左:离散 Pareto 扫描(稳健);":
        ". Left: discrete Pareto sweep (robust); ",
    "右:可微梯度寻优(快速定位,逼近可逆壁垒时会振荡)。":
        "right: differentiable gradient search (fast, oscillates near the "
        "invertibility wall).",
    "AI-Native 流程:PA 工作点与 DPD 复杂度联合优化。离散 Pareto ":
        "AI-native flow: jointly optimize PA operating point and DPD "
        "complexity. Discrete Pareto ",
    "扫描(稳健)与可微梯度寻优(内层闭式 LS-DPD + 外层梯度)。":
        "sweep (robust) and differentiable gradient search (inner "
        "closed-form LS-DPD + outer gradient).",
    "📊 离散 Pareto 扫描": "📊 Discrete Pareto sweep",
    "离散 Pareto 扫描": "Discrete Pareto sweep",
    "∇ 可微梯度寻优": "∇ Differentiable gradient search",
    "可微梯度寻优": "Differentiable gradient search",
    "DPD 系数预算": "DPD coefficient budget",
    "运行扫描": "Run sweep",
    "运行扫描(约 1 分钟)": "Run sweep (~1 min)",
    "扫描 7 个工作点(每点含 DPD 阶梯搜索)…":
        "Sweeping 7 operating points (with DPD ladder search each)…",
    "顺序设计(先冲效率)": "Sequential design (efficiency-first)",
    "联合设计(预算内最高效率)": "Co-design (best efficiency in budget)",
    "可行": "feasible",
    "撞墙:不可逆/超预算": "hits the wall: non-invertible / over budget",
    "预算内无可行点": "no feasible point within budget",
    "drive {drive:.2f} · {cost} 系数 · ": "drive {drive:.2f} · {cost} coeffs · ",
    "drive {drive:.2f} · {cost} 系数": "drive {drive:.2f} · {cost} coeffs",
    "EVM 无DPD": "EVM no DPD",
    "DPD 系数": "DPD coeffs",
    "DPD 达标代价 (系数)": "DPD cost to meet spec (coeffs)",
    "PAE 代理 (%)": "PAE proxy (%)",
    "漏极效率 (%)": "Drain efficiency (%)",
    "✅ 扫描完成({n} 个工作点)":
        "✅ Sweep done ({n} operating points)",
    "初始 drive(保守)": "Initial drive (conservative)",
    "初始 drive": "Initial drive",
    "梯度步数": "Gradient steps",
    "运行梯度寻优": "Run gradient search",
    "内层 LS-DPD + 外层梯度优化中…":
        "Inner LS-DPD + outer gradient optimizing…",
    "此功能需要 PyTorch。": "This feature requires PyTorch.",
    "保守设计(固定 drive)": "Conservative design (fixed drive)",
    "梯度联合优化": "Gradient co-optimization",
    "✅ 梯度寻优完成": "✅ Gradient search done",
    "❌ {e}(需要 PyTorch)": "❌ {e} (requires PyTorch)",
    # ---- merged from Qt page report -------------------------------
    "WiFi 7(802.11be)PA 行为建模与数字预失真研发平台:经典与神经模型、ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。":
        "R&D platform for WiFi 7 (802.11be) PA behavioral modeling and digital predistortion: classical and neural models, ILA/DLA predistortion, CFR, fixed-point deployment, and PA/DPD co-design.",
    "生成 802.11be 风格 OFDM 基带波形;PSD / CCDF / 星座 / 时域;可选 CFR 削峰对比;可导出 IQDataset (.npz)。":
        "Generate 802.11be-style OFDM baseband waveforms; PSD / CCDF / constellation / time domain; optional CFR clipping comparison; export as IQDataset (.npz).",
    "加载实测/仿真 PA 数据并注册为数据源:OpenDPD 数据集目录、Cadence CSV、MATLAB .mat、IQDataset .npz;可选自动延迟对齐。":
        "Load measured/simulated PA data and register it as a source: OpenDPD dataset directory, Cadence CSV, MATLAB .mat, IQDataset .npz; optional automatic delay alignment.",
    "经典(LS 闭式解)或神经(SGD)模型拟合 PA 行为;拟合好的模型可作为 DPD 评估代理并进入部署页。":
        "Fit PA behavior with classical (closed-form LS) or neural (SGD) models; fitted models can serve as DPD evaluation surrogates and feed the Deployment page.",
    "ILA(经典 LS,基函数 GMP/DDR/MP)或 DLA(神经直接学习,需神经代理);合成源用星座 EVM+Mask,OpenDPD 源自动用其口径;实测源评估需选 PA 代理。":
        "ILA (classical LS with GMP/DDR/MP basis) or DLA (neural direct learning, requires a neural surrogate); synthetic sources use constellation EVM + mask, OpenDPD sources automatically use their own convention; measured sources need a PA surrogate for evaluation.",
    "定点位宽扫描(bit-true)+ 硬件成本估计;导出 FPGA/ASIC 交接产物:整数系数 JSON、参考向量 CSV、神经模型 ONNX。":
        "Fixed-point bit-width sweep (bit-true) + hardware cost estimates; export FPGA/ASIC hand-off artifacts: integer coefficient JSON, reference vector CSV, neural model ONNX.",
    "ONNX 数值验证":
        "ONNX numerical verification",
    "AI-Native 流程:PA 工作点与 DPD 复杂度联合优化。离散 Pareto 扫描(稳健)与可微梯度寻优(内层闭式 LS-DPD + 外层梯度)。":
        "AI-native flow: joint optimization of the PA operating point and DPD complexity. Discrete Pareto sweep (robust) and differentiable gradient search (inner closed-form LS-DPD + outer gradient).",
    "drive {drive:.2f} · {cost} 系数 · EVM {evm:.1f} dB":
        "drive {drive:.2f} · {cost} coeffs · EVM {evm:.1f} dB",
    # ---- merged from web page report ------------------------------
    "WiFi 7(802.11be)PA 行为建模与数字预失真的完整研发平台:经典(Saleh/MP/GMP/DDR)与神经(GRU/DGRU/TCN)模型、ILA/DLA 预失真、CFR、定点部署与 PA/DPD 联合设计。":
        "Complete R&D platform for WiFi 7 (802.11be) PA behavioral modeling and digital predistortion: classical (Saleh/MP/GMP/DDR) and neural (GRU/DGRU/TCN) models, ILA/DLA predistortion, CFR, fixed-point deployment, and PA/DPD co-design.",
    "\n| 步骤 | 页面 | 内容 |\n|---|---|---|\n| 1 | 🌊 波形工作台 | 生成 802.11be 风格 OFDM(可选 CFR 削峰),导出数据集 |\n| 2 | 🗂️ 数据管理 | 加载 OpenDPD / Cadence / MATLAB / .npz 实测数据,延迟对齐 |\n| 3 | 📈 PA 建模 | 经典 LS 或神经训练拟合 PA,NMSE 评估 |\n| 4 | 🎛️ DPD 实验室 | ILA / DLA 预失真,EVM·ACLR·Mask 前后对比 |\n| 5 | ⚖️ 结果比较 | 跨实验指标对比(与桌面版共享注册表) |\n| 6 | 🚀 部署 | 定点位宽扫描,导出 ONNX / 整数系数 / 参考向量 |\n| 7 | 🧭 联合设计 | PA 工作点 × DPD 复杂度联合权衡 |\n":
        "\n| Step | Page | What it does |\n|---|---|---|\n| 1 | 🌊 Waveform Workbench | Generate 802.11be-style OFDM (optional CFR clipping), export datasets |\n| 2 | 🗂️ Data Management | Load OpenDPD / Cadence / MATLAB / .npz measured data, delay alignment |\n| 3 | 📈 PA Modeling | Fit the PA with classical LS or neural training, NMSE evaluation |\n| 4 | 🎛️ DPD Lab | ILA / DLA predistortion, EVM·ACLR·mask before/after comparison |\n| 5 | ⚖️ Result Comparison | Cross-experiment metric comparison (registry shared with the desktop app) |\n| 6 | 🚀 Deploy | Fixed-point bit-width sweep, export ONNX / integer coefficients / reference vectors |\n| 7 | 🧭 Co-Design | Joint PA operating-point × DPD complexity trade-off |\n",
    "神经建模可用":
        "neural modeling available",
    "可在数据页手动指定":
        "can be set manually on the Data page",
    "神经页面不可用":
        "neural pages unavailable",
    "生成 802.11be 风格 OFDM 基带波形,查看 PSD / CCDF / 星座与 PAPR;可选 CFR 削峰对比;结果可下载为 IQDataset (.npz) 供外部使用。":
        "Generate 802.11be-style OFDM baseband waveforms and inspect PSD / CCDF / constellation and PAPR; optionally compare CFR clipping; download the result as an IQDataset (.npz) for external use.",
    "提示:要把该波形送入虚拟 PA 生成建模数据,请前往 **📈 PA 建模** 页选择\"合成 ReferencePA\"数据源。":
        "Tip: to feed this waveform through the virtual PA and generate modeling data, go to the **📈 PA Modeling** page and choose the \"Synthetic ReferencePA\" data source.",
    "EVM 代价 {evm} dB":
        "EVM cost {evm} dB",
    "时域包络(前 {n} 采样)":
        "Time-domain envelope (first {n} samples)",
    "加载实测/仿真 PA 数据(输入输出 IQ 对),预览并注册为数据源,供 PA 建模与 DPD 页面使用。支持 OpenDPD 数据集目录、Cadence Envelope CSV、MATLAB .mat、IQDataset .npz。":
        "Load measured/simulated PA data (input/output IQ pairs), preview it, and register it as a data source for the PA Modeling and DPD pages. Supports OpenDPD dataset directories, Cadence Envelope CSV, MATLAB .mat, and IQDataset .npz.",
    "尚无数据源。加载数据集,或在 PA 建模页直接使用合成 ReferencePA。":
        "No data sources yet. Load a dataset, or use the synthetic ReferencePA directly on the PA Modeling page.",
    "实测/仿真数据常有输入输出定时偏差,用互相关自动估计并消除整数+分数延迟":
        "Measured/simulated data often has input-output timing offset; cross-correlation automatically estimates and removes the integer+fractional delay",
    "对齐:整数延迟 {lag},总延迟 {total} 采样":
        "Alignment: integer delay {lag}, total delay {total} samples",
    "用经典(LS 闭式解)或神经(梯度训练)模型拟合 PA 行为。拟合好的模型可注册为 DPD 评估代理、进入部署页定点分析。":
        "Fit PA behavior with classical (LS closed-form) or neural (gradient-trained) models. Fitted models can be registered as DPD evaluation surrogates and taken to the Deploy page for fixed-point analysis.",
    "训练并评估数字预失真:**ILA**(经典最小二乘,基函数可选 GMP/DDR/MP)或 **DLA**(神经直接学习,需神经代理)。合成源用星座 EVM + WiFi Mask;OpenDPD 源自动切换其发表口径。实测源的评估需选择 PA 代理模型。":
        "Train and evaluate digital predistortion: **ILA** (classical least squares, selectable GMP/DDR/MP basis) or **DLA** (neural direct learning, requires a neural surrogate). Synthetic sources use constellation EVM + WiFi mask; OpenDPD sources automatically switch to their published conventions. Evaluating measured sources requires selecting a PA surrogate model.",
    "实测多载波源无星座解调(其信号含 CP/多载波结构),请以 PSD 与谱域指标为准。":
        "Measured multi-carrier sources have no constellation demodulation (the signal contains CP / multi-carrier structure); rely on the PSD and spectral-domain metrics.",
    "Mask 无DPD: {v}":
        "Mask no DPD: {v}",
    "Mask DPD后: {v}":
        "Mask with DPD: {v}",
    "跨实验对比注册表中的 run(建模 / DPD / 部署)。注册表持久化在 gui_runs/,Web 版与桌面版共享。":
        "Compare registered runs across experiments (modeling / DPD / deployment). The registry persists in gui_runs/ and is shared between the Web and desktop versions.",
    "对拟合好的模型做定点位宽扫描(bit-true)与硬件成本估计,导出 FPGA/ASIC 交接产物:整数系数 JSON、参考向量 CSV、神经模型 ONNX。经典模型免训练直接量化(PTQ);神经模型权重+激活 PTQ。":
        "Run fixed-point bit-width sweeps (bit-true) and hardware cost estimates on fitted models, and export FPGA/ASIC handoff artifacts: integer-coefficient JSON, reference-vector CSV, neural-model ONNX. Classical models are quantized directly without training (PTQ); neural models get weight+activation PTQ.",
    "ONNX 数值验证 通过":
        "ONNX numerical verification passed",
    "ONNX 数值验证 跳过":
        "ONNX numerical verification skipped",
    "AI-Native 流程:PA 工作点与 DPD 复杂度联合优化,而非\"先设计 PA 再补救线性度\"。左:离散 Pareto 扫描(稳健);右:可微梯度寻优(快速定位,逼近可逆壁垒时会振荡)。":
        "AI-native flow: jointly optimize the PA operating point and DPD complexity, rather than \"design the PA first, then patch up linearity\". Left: discrete Pareto sweep (robust); right: differentiable gradient search (fast to locate, may oscillate near the invertibility barrier).",
    "drive {drive} · {cost} 系数 · EVM {evm}":
        "drive {drive} · {cost} coeffs · EVM {evm}",
}


def tr(s: str, lang: str = "zh") -> str:
    """Translate a Chinese UI string; unknown strings pass through."""
    if lang == "en":
        return _EN.get(s, s)
    return s
