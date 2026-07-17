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

**原则:所有 AI 模型必须和 GMP 在同一数据、同一指标下对比。**

Phase 1 实测(160 MHz / 1024-QAM / ReferencePA,验证集 NMSE):
MP(阶 7、记忆 4)-52.2 dB;GMP(52 系数)**-57.8 dB**。

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

实现:`padpd.dpd.ILAPredistorter`。

```
1. u = x 驱动 PA,得 y
2. 拟合后逆模型:y/G → u(G 为目标线性增益)
3. 把后逆模型复制到 PA 前作为预失真器,u = DPD(x),迭代 2~3 次
```

### 6.2 评价指标

EVM、ACLR、Spectral Mask(`padpd.metrics`)。Phase 1 实测:DPD 后
EVM -19.0 → **-57.4 dB**,ACLR -31 → **-55 dBc**,mask FAIL → PASS。

### 6.3 Neural DPD(Phase 2)

`Input IQ → Neural Network → Predistorted IQ → PA → Linear output`,
损失函数通常为 `|y_target - y_out|^2`。

### 6.4 工程注意:可逆性与工作点

DPD 只能线性化到 PA 最大输出为止。OFDM 峰值超过 AM-AM 拐点时 ILA 发散
(本框架 `ReferencePA` 在 `drive ≥ 0.22` 时可复现该现象)。真实系统需要
CFR(削峰)或足够 back-off 配合。

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
