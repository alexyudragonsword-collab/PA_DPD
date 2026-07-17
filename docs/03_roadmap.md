# 分阶段路线图

## Phase 1:经典 Baseline 全链路 ✅(当前)

- [x] 802.11be 风格 OFDM 波形(20~320 MHz、16~4096-QAM、RC 加窗)
- [x] 经典 PA 行为模型:Saleh、MP、GMP(LS 拟合)
- [x] 虚拟 DUT `ReferencePA`(Wiener-Hammerstein,含记忆 + 压缩 + AM-PM)
- [x] ILA-GMP DPD
- [x] 指标:EVM(scalar/per-tone 均衡)、ACLR、PSD + 802.11 风格 Mask、AM-AM/AM-PM
- [x] 数据层:IQDataset + Cadence CSV / MATLAB .mat / OpenDPD 加载器
- [x] 端到端 demo:EVM -19.0 → -57.4 dB,ACLR -31 → -55 dBc,mask PASS

**基准数字(160 MHz / 1024-QAM / ReferencePA)**:GMP 验证 NMSE -57.8 dB
(52 系数)。这是 Phase 2 所有神经模型必须超越的线。

## Phase 2:神经 PA 建模 + Neural DPD

目标:在相同数据/指标下超过 GMP baseline,并接入真实数据。

- [ ] 引入 PyTorch;`PAModel` 接口的 `TorchPAModel` 适配基类
- [ ] GRU / LSTM / DGRU PA 行为模型(对标 OpenDPD 参考实现)
- [ ] Neural DPD:直接学习架构(DLA)与 ILA 两种训练方式
- [ ] OpenDPD 公开 DPA 数据集复现:与其论文指标对齐
- [ ] Cadence Envelope 真实数据接入(替换 ReferencePA)
- [ ] 1D-CNN 变体(面向 ASIC);Transformer 探索(320 MHz 记忆效应)
- [ ] CFR(削峰)模块,解决深压缩工作点的可逆性问题

验收:神经模型 NMSE 优于 GMP ≥ 3 dB;Neural DPD 在 320 MHz/4096-QAM
下 EVM < -47 dB。

## Phase 3:量化与 FPGA/ASIC 部署

目标:满足 320 MHz(> 640 MSPS)实时性。

- [ ] PyTorch → ONNX 导出链
- [ ] INT16/INT8 量化感知训练,定点仿真比对(bit-true 模型)
- [ ] 剪枝(降 MAC)、知识蒸馏(Transformer teacher → GRU student)
- [ ] FPGA 原型(HLS 或 RTL),与 Python 定点模型逐样本比对
- [ ] SDR/GNU Radio 台架闭环验证

验收:定点实现与浮点 EVM 差 < 1 dB;吞吐 ≥ 640 MSPS。

## Phase 4:AI Native PA 联合设计

目标:PA 设计 + DPD 联合优化,而非"先设计 PA 再补救线性度"。

- [ ] 可微 PA 模型(神经代理模型,对设计参数可求导)
- [ ] PA 参数 ↔ DPD 复杂度联合寻优(效率 vs 线性度 vs DPD 代价)
- [ ] AI 生成 PA 架构候选 → Spectre 自动仿真回环
- [ ] WiFi 7 全系统(MLO、多信道)级联评估

## 里程碑依赖

```
Phase 1 (baseline)
   └─→ Phase 2 (neural, 真实数据)
          └─→ Phase 3 (部署)
          └─→ Phase 4 (联合设计,可与 Phase 3 并行)
```
