# WiFi 7 PA + DPD 完整 AI 辅助研发流程

> 定位:面向 RFIC/Analog IC 团队的工程研发流程,覆盖从 CMOS/SOI PA 设计 →
> 电路仿真 → 行为建模 → AI 建模 → DPD → FPGA/ASIC 部署 → WiFi 系统验证。

## 0. 总体架构

WiFi 7(802.11be)的核心挑战:

- 320 MHz 超宽带
- 4096-QAM(极高线性度要求)
- Multi-Link Operation (MLO)
- 高峰均功率比(PAPR ~10-12 dB)的 OFDM
- 低功耗 CMOS/SOI PA

**传统流程**:PA 设计 → Spectre RF 仿真 → 流片 → 测量 → DPD 补偿。
问题:周期长、PA 非线性难以提前评估、DPD 依赖后端调参。

**AI 增强流程**:

```
          Device Simulation
                |
                v
        Transistor-level PA
          (Cadence Spectre)
                |
                v
        PA Behavioral Model
                |
        +---------------+
        |               |
        v               v
   Classical DPD     Neural DPD
   GMP / MP          AI Model
        |               |
        +-------+-------+
                |
                v
          WiFi 7 System
        EVM / ACLR / Mask
                |
                v
        Silicon Optimization
```

本仓库 Phase 1 用 Python 实现了图中 "PA Behavioral Model → Classical DPD →
System Metrics" 的完整基线链路,晶体管级仿真暂以虚拟 `ReferencePA` 代替。

## 1. PA 设计阶段(Analog/RFIC)

### 1.1 WiFi 7 PA 典型指标

| 指标 | 目标 |
|------|------|
| Frequency | 2.4 / 5 / 6 GHz |
| Bandwidth | 160 / 320 MHz |
| Output Power | 15~25 dBm |
| PAE | 25~40% |
| EVM | < -45 dB(4096-QAM MCS) |
| Gain | 25~35 dB |

### 1.2 PA 架构选型

- **CMOS Class AB**:集成度高、成本低;线性度差,依赖 DPD。
- **SOI PA**:用于手机 WiFi FEM;高隔离、高效率。
- **Doherty PA**(WiFi 7 开始增多):Main PA + Peak PA 并联,back-off
  效率显著提升,但 AM-AM/AM-PM 特性更复杂,对 DPD 要求更高。

## 2. 晶体管级仿真

工具:Cadence Spectre RF(主)、Keysight ADS、AWR。

| 仿真 | 目的 | 输出 |
|------|------|------|
| DC | 偏置点、静态电流 | bias point / current |
| S 参数 | 小信号特性 | S11、S21、Gain、Stability |
| Harmonic Balance | 静态非线性 | AM-AM、AM-PM、增益压缩、相位旋转 |
| **Envelope** | **宽带动态非线性** | **失真后的 IQ 序列 —— AI 建模的数据来源** |

Envelope 仿真必须以 802.11be OFDM 波形激励(由本框架
`scripts/generate_dataset.py` 或 MATLAB 生成),输出失真 IQ。

## 3. PA 行为模型

目标:把"晶体管级 PA + 10 小时 Envelope 仿真"替换为"Python 模型 + 毫秒级预测"。

数据流:

```
padpd OFDM waveform (或 MATLAB)
        |
        v
Cadence Envelope Simulation     ← Phase 1 暂用 ReferencePA 代替
        |
        v
IQ input/output dataset (IQDataset)
        |
        v
模型训练(GMP baseline / 神经网络)
```

数据规模建议:10M~100M 样本,320 MHz 带宽,1024/4096-QAM。

## 4. 经典模型 Baseline(必须先建立)

| 模型 | 实现 | 用途 |
|------|------|------|
| Saleh | `padpd.pa.SalehPA` | AM-AM/AM-PM 无记忆模型,早期验证 |
| Memory Polynomial | `padpd.pa.MemoryPolynomialModel` | 工业基础,阶数 5~9、记忆 3~10 |
| **GMP** | `padpd.pa.GMPModel` | **工业 DPD 黄金 baseline**,增加 lag/lead 交叉项,精度高、FPGA 友好 |
| DDR-Volterra | `padpd.pa.DDRVolterraModel` | 动态偏差缩减 Volterra(Zhu 2006),按动态阶数 r 系统截断,r=1 参数效率高于 GMP |

四者都是 Volterra 级数的剪枝特例:MP 保留对角项,GMP 加手选 lag/lead 交叉项,
DDR 按"动态阶数 r=非零延迟因子数"系统截断(r=1 为工作马,r=2 更精细),
完整 Volterra 因参数指数爆炸不可用。全部为线性参数模型,用最小二乘闭式解。

**原则:所有 AI 模型必须和 GMP 在同一数据、同一指标下对比。**

Phase 1 实测(160 MHz / 1024-QAM / ReferencePA,验证集 NMSE):
MP(阶 7、记忆 4)-52.2 dB;GMP(52 系数)**-57.8 dB**。

Phase 1.5 真实测量数据实测(OpenDPD 数据集,~500 实参数预算,测试集 NMSE):

| 数据集 | MP-500 | GMP-510 | DDR r=1(140系数) | OpenDPD GRU 代理 |
|--------|--------|---------|-------------------|------------------|
| DPA_200MHz(Doherty) | -35.0 dB | -33.7 dB | **-34.0 dB** | — |
| DPA_160MHz(Doherty) | -38.3 dB | **-39.2 dB** | -39.2 dB | -38.4 dB(2066 参数) |
| APA_200MHz(GaN) | -37.1 dB | -35.5 dB | **-37.0 dB** | -43.5 dB(1911 参数) |

DDR 观察:**r=1 用 140 复系数(GMP 的 55%)追平或略超 GMP-510**——参数
效率更高;但 **r=2(441 系数)在这些数据量下过拟合**(DPA_200 降到 -30.6),
恰好印证 DDR"记忆是弱动态、高阶动态项冗余"的核心论点。这几个数据集记忆
跨度短(F=50 与 F=200 神经训练无差异亦证明),DDR 相对 GMP 净收益有限。

工程要点(踩坑记录):高阶多项式基条件数可达 1e7+,系数向量靠列间精细
抵消工作——评估时若记忆抽头零填充(直接喂 test 段)会产生巨幅边界瞬态,
污染整段指标。解决:①拟合可加相对岭正则(`fit(x, y, regularization=1e-9)`);
②评估时用前一段数据做记忆预热上下文(见 `scripts/run_opendpd_baseline.py`)。
另:线性参数模型必须用 LS 闭式解,OpenDPD 实测 LS 比 SGD 训练同一 GMP
好 9 dB+ ACLR。

## 5. AI PA 建模(Phase 2 重点)

- **LSTM**:捕获热记忆、偏置网络记忆效应。
- **GRU / DGRU**:参数比 LSTM 少约 30%、速度更快,适合 WiFi 芯片;
  OpenDPD 已提供参考实现。
- **1D-CNN**:硬件友好,适合 ASIC。
- **Transformer**(前沿研究):WiFi 7 的 320 MHz + 高阶 QAM 使记忆效应
  增强,attention 结构是研究方向。

所有神经模型将实现与 `PAModel` 相同的 `fit/__call__` 接口,直接复用本框架
的指标与 DPD 流程。

## 6. DPD 设计流程

### 6.1 间接学习架构(ILA,工业经典)

实现:`padpd.dpd.ILAPredistorter`,两种使用方式:

```
闭环迭代(fit):有可驱动的 PA(模型/仿真/台架)时
1. u = x 驱动 PA,得 y
2. 拟合后逆模型:y/G → u(G 为目标线性增益)
3. 把后逆模型复制到 PA 前作为预失真器,u = DPD(x),迭代 2~3 次

数据驱动单次辨识(fit_measured):只有一份实测 (x, y) 数据时
直接拟合 y/G → x 作为预失真器,与 OpenDPD 经典 benchmark 协议一致
```

目标增益 G 默认为 LS 标量;可显式传入其他口径(如 OpenDPD 的峰值比
`target_gain_opendpd`)。预失真器基函数族可换:`model_factory` 接受任意
`PAModel`(GMP / DDR-Volterra / MP 等)。

### 6.1b 经典 DPD 基函数对比(ILA-GMP vs ILA-DDR)

`scripts/compare_ila_dpd.py`:同一 ILA 协议、同一神经代理评估,只换基函数
族。真实数据实测(ACLR_AVG dBc,OpenDPD 口径):

| 数据集 | ILA-GMP-510(255) | **ILA-DDR r=1(140)** | ILA-DDR r=2(441) |
|--------|------------------|----------------------|------------------|
| DPA_200MHz | -47.5 | **-49.1** | -48.5 |
| DPA_160MHz | -50.2 | **-51.6** | -52.1 |
| APA_200MHz(GaN) | -38.6 | **-47.1** | -48.9 |

**结论**:(1) DDR r=1 用 55% 参数在三个数据集上全面超过 GMP,GaN PA 上
**领先 8.5 dB**——参数效率优势在 DPD 里充分兑现。(2) 与正向建模的反差
(§4:DDR 建模只追平 GMP、r=2 过拟合)说明:ILA 拟合的是后逆(目标是
平滑的预失真信号,条件数好),DDR 交叉项在此充分发挥。**"建模准" ≠
"做 DPD 好",必须分开评估。**(3) 绝对值受神经代理精度(APA -31.6 dB)
限制,但相对比较公平(同代理同协议)。

### 6.2 评价指标

EVM、ACLR、Spectral Mask(`padpd.metrics`)。Phase 1 实测:DPD 后
EVM -19.0 → **-57.4 dB**,ACLR -31 → **-55 dBc**,mask FAIL → PASS。

### 6.3 Neural DPD(Phase 2)

`Input IQ → Neural Network → Predistorted IQ → PA → Linear output`,
损失函数通常为 `|y_target - y_out|^2`。

### 6.4 工程注意:可逆性、工作点与 CFR

DPD 只能线性化到 PA 最大输出为止。OFDM 峰值超过 AM-AM 拐点时 ILA 发散
(本框架 `ReferencePA` 在 `drive ≥ 0.18` 时可复现该现象)。工业解法是在
DPD 前加 **CFR 削峰**(`padpd.cfr.cfr_clip_filter`,迭代削峰滤波 ICF):
用有界的带内 EVM 代价换取数 dB PAPR,使整个包络回到 PA 可逆区。

实测(160 MHz / 1024-QAM / drive=0.18,`run_baseline_demo.py` 输出):

| 链路 | EVM | ACLR(上邻道) | Mask |
|------|-----|--------------|------|
| PA(无 DPD) | -18.3 dB | -28.8 dBc | FAIL |
| DPD(无 CFR) | -27.7 dB(峰值不可逆,受限) | -31.7 dBc | FAIL |
| **CFR(8 dB)+ DPD** | **-36.9 dB** | **-56.3 dBc** | **PASS** |

规律:DPD 收敛后残余 EVM ≈ CFR 自身代价(本例 -37.6 dB),即线性化
已完全,瓶颈转移到削峰失真——这是 CFR 目标 PAPR 的选取依据(教科书式
的 EVM–效率权衡)。复现:
`python scripts/run_baseline_demo.py --drive 0.18 --cfr-papr 8`。
峰值统计用 CCDF 曲线(`padpd.metrics.ccdf`)观察,不止看单点 PAPR。

## 7. AI 训练平台

PyTorch(主)/ TensorFlow,数据格式 numpy/HDF5。部署链:

```
Spectre output → Python Dataset → PyTorch Training → ONNX → FPGA/ASIC
```

## 8. FPGA/ASIC 部署(Phase 3)

最大挑战是实时性:320 MHz 带宽要求 > 640 MSPS 处理速率。
优化技术:量化(FP32→INT16)、剪枝(减 MAC)、知识蒸馏
(大 Transformer teacher → 小 GRU student)。

## 9. 验证指标

- **EVM**:WiFi 7 4096-QAM 要求 < -45 dB 量级(比 WiFi 6 更严)。
- **Spectral Mask**:带外泄漏检查(本框架为 802.11ax/be 风格简化模板)。
- **ACLR**:邻道泄漏比。

## 10. 推荐开源工具链

| 领域 | 工具 | 链接 |
|------|------|------|
| PA/DPD 建模 ⭐ | OpenDPD | https://github.com/lab-emi/OpenDPD |
| DSP | GNU Radio | https://github.com/gnuradio/gnuradio |
| RF 分析 | scikit-rf | https://github.com/scikit-rf/scikit-rf |
| AI | PyTorch | https://github.com/pytorch/pytorch |

### 10.1 OpenDPD 对标结论(Phase 1.5 检视)

已完成对 OpenDPD 的整体检视并纳入其关键规范。本仓库与 OpenDPD 的分工:

- **已纳入**:数据集格式(spec.json 元数据 + 两种 CSV 布局,
  `load_opendpd_dataset`)、其指标口径的精确复刻
  (`padpd.metrics.opendpd_compat`,与其原版代码数值一致到 1e-9)、
  ~500 实参数的 MP/GMP 基准配置(`padpd.pa.presets`)、数据驱动单次
  ILA 协议(`fit_measured`)。
- **保留自己的实现**:星座域 EVM(OpenDPD 的 EVM 是谱域近似,其 README
  自认不精确;两套并存,横向对比用其口径、工程验收用星座 EVM)、
  802.11 风格 ACLR/Mask(其 ACLR 参考是最强带内子信道,面向多载波 LTE)。
- **两套指标不可混比**:OpenDPD ACLR 的参考功率是最强带内子信道(非总
  带内功率)、邻道积分宽度是一个子信道;数值上与 3GPP/802.11 口径差异
  可达数 dB。

真实数据 DPD 复现结果(GMP-510 数据驱动 ILA + GMP-510 代理评估,
OpenDPD 口径):

| 数据集 | 无 DPD ACLR | DPD 后 ACLR / EVM(谱) | OpenDPD 发表 GMP-QR | 其神经最优(~500 参数) |
|--------|------------|----------------------|--------------------|--------------------|
| DPA_200MHz | -30.6 | **-48.7 / -46.7** | — | — |
| DPA_160MHz | -34.5 | **-52.8 / -54.0** | -54.0 / -51.1 | -56.8 / -54.0 |
| APA_200MHz | -27.7 | -26.2 / **-38.4** | -38.8 / -38.5 | -53.4 / -49.1 |

解读:DPA_160MHz 上与发表值高度一致(ACLR 差 1.2 dB,EVM 更好 3 dB),
协议复现成功。APA_200MHz(强非线性 GaN PA)上 EVM 与发表值精确吻合,
但 ACLR 受**评估代理保真度**限制(我们用 GMP-510 代理 NMSE -35.5 dB,
其用 GRU 代理 -43.5 dB;实验证明代理 NMSE 每提升 3 dB,ACLR 读数改善
约 6 dB)——这是 Phase 2 引入神经 PA 代理最直接的立项依据。

## 11. 团队组织建议(AI for RFIC PA 团队)

| 组 | 职责 | 对应本仓库 |
|----|------|-----------|
| Group 1: PA Design | CMOS/SOI PA、Doherty、Layout | (EDA 侧) |
| Group 2: Behavior Modeling | Spectre 数据、GMP、Neural model | `padpd.pa`、`padpd.data` |
| Group 3: DPD Algorithm | GMP DPD、Neural DPD、Transformer | `padpd.dpd`、`padpd.metrics` |
| Group 4: Implementation | FPGA、ASIC、DSP accelerator | Phase 3 |

## 12. 最终目标:AI Native PA Design

```
AI-generated PA architecture
          |
Transistor simulation
          |
Differentiable PA Model
          |
Neural DPD co-design
          |
WiFi 7 Silicon
```

即 **PA 设计 + DPD 设计联合优化**,而不是"先设计 PA,再补救线性度"。
详见 `03_roadmap.md` Phase 4。
