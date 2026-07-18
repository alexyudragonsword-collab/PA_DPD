# 3. 功能页操作指南

本章逐页说明"输入什么、点什么、看什么"。两版 GUI 页面同构,截图以
桌面版为主;Web 版控件多在左侧边栏,操作一致。

## 3.1 总览

打开即见:代表性成果指标卡(均为实测数字)、环境自检(PyTorch 是否
可用、OpenDPD 数据集路径、已存 checkpoint 与 run 数量)、最近实验表。
用它确认环境就绪,并快速回顾最近的实验。

![总览页](assets/qt_home.png)

## 3.2 波形工作台

生成 802.11be 风格 OFDM 基带波形。

- **输入**:带宽(20–320 MHz)、QAM 阶数(16–4096)、OFDM 符号数、
  随机种子;可选 **CFR 削峰**及目标 PAPR(dB)。
- **操作**:点"生成波形";需要落盘时点"导出 .npz"。
- **输出**:采样率 / FFT 与有效子载波 / PAPR 指标卡(开 CFR 时还
  给出削峰后 PAPR 与 EVM 代价);PSD、CCDF、发送星座、时域包络四个
  图页。开 CFR 时 PSD/CCDF 同图叠加削峰前后曲线。

![波形工作台:CFR 前后 PSD 对比](assets/qt_waveform.png)

导出的 `.npz` 为 IQDataset 格式,可在数据管理页重新载入,或供外部
工具链使用。

## 3.3 数据管理

把实测/仿真数据注册为"数据源",供建模与 DPD 页选用。

- **OpenDPD 目录**:填 datasets 路径 → "扫描目录" → 选数据集 →
  "加载数据集"。spec 元数据(采样率、带宽、调制)自动解析。
- **打开文件**:Cadence CSV / MATLAB `.mat` / IQDataset `.npz`,按
  后缀自动识别;可勾选**自动延迟对齐**(互相关估计整数+分数延迟并
  校正,详见第 4 章)。
- **预览**:采样率、train/val/test 样本数、主带宽、调制指标卡 +
  PSD 与 AM-AM/AM-PM 预览图,用于快速检查数据质量与对齐情况。

![数据管理:加载 OpenDPD DPA_200MHz 实测数据](assets/qt_data.png)

## 3.4 PA 建模

- **数据源**:"合成 ReferencePA"(可调 drive 工作点)或已注册实测源。
- **经典 (LS)**:类型选 MP / GMP / DDR 或 OpenDPD ~500 参数 preset
  (MP-500 / GMP-510 / DDR-140),可调阶数与记忆;闭式解秒级完成。
- **神经 (SGD)**:backbone(GRU / DGRU / TCN)、hidden、epochs;训练
  跑在后台线程,进度条实时显示验证 NMSE。GUI 默认小参数用于交互
  实验;论文级训练请用 `scripts/train_neural_pa.py`。
- **输出**:测试 NMSE 与参数量指标卡、实测 vs 预测 PSD、预测
  AM-AM/AM-PM;"保存 checkpoint"落盘模型;拟合结果自动注册为模型
  (供 DPD/部署页使用)与 run(供比较页)。

![PA 建模:GMP-510 拟合结果](assets/qt_modeling.png)

## 3.5 DPD 实验室

- **算法**:**ILA(经典)**——基函数选 GMP-510 / DDR-140 / MP-500 或
  自定义,最小二乘辨识,合成源闭环迭代、实测源数据驱动;
  **DLA(神经)**——需先在建模页训练一个神经代理,预失真器与冻结
  代理级联梯度直训。
- **评估口径自动切换**:合成源用星座 EVM + 802.11 发射 Mask;OpenDPD
  源自动用其发表口径(谱域 EVM / ACLR_AVG);其他实测源需选择 PA
  代理模型评估。
- **输出**:DPD 前后 EVM 与 ACLR 四张指标卡(附 Mask PASS/FAIL
  徽章)、PSD 前后对比、星座前后对比;结果注册为 run。

![DPD 实验室:ILA-GMP,EVM -19 → -59.8 dB,Mask FAIL → PASS](assets/qt_dpd.png)

## 3.6 结果比较

所有 run(建模 / DPD / 部署)的注册表视图:勾选若干条 → "对比选中"
生成分组柱状图(NMSE / EVM / ACLR);可删除、导出 JSON。注册表持久化
于 `gui_runs/`,Web 版与桌面版共享。

![结果比较:跨实验指标对比](assets/qt_compare.png)

## 3.7 部署

- **位宽扫描**:勾选模型与位宽(W16–W8)→ 扫描曲线 + 表格(含每
  样本 MAC 与 GMAC/s 估计),虚线为浮点基线。量化在 bit-true 定点
  仿真中完成。
- **导出交接产物**:选模型与系数位宽 → 生成整数系数 JSON、bit-true
  参考向量 CSV(供 RTL 逐样本比对);神经模型另导出 ONNX(含数值
  验证)。

![部署:位宽 vs 精度扫描](assets/qt_deploy.png)

## 3.8 联合设计

- **离散 Pareto 扫描**:给定 EVM spec 与 DPD 系数预算,扫描 7 个 PA
  工作点,每点做 DPD 复杂度阶梯搜索;图中红色区域为不可行(不可逆)
  工作点,对比"顺序设计"与"联合设计"两张卡。
- **可微梯度寻优**:内层闭式 LS-DPD + 外层对 drive 求梯度,自动把
  保守工作点推到 spec 边界附近,轨迹图展示 drive 与 EVM 演化
  (需 PyTorch)。

![联合设计:Pareto 扫描与可行域](assets/qt_codesign.png)
