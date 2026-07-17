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

## Phase 1.5:OpenDPD 对标检视与补齐 ✅

- [x] OpenDPD 数据集加载(`load_opendpd_dataset`:spec.json、split/single CSV)
- [x] `IQDataset` 三分切分(train/val/test,0.6/0.2/0.2 连续)
- [x] 时间对齐工具 `align_delay`(xcorr 整数延迟 + LS 复增益)
- [x] OpenDPD 指标口径复刻(`opendpd_compat`,与原版数值一致到 1e-9)
- [x] ~500 实参数基准配置(`mp_opendpd_500` / `gmp_opendpd_510`)
- [x] MP/GMP 拟合岭正则选项 + 评估记忆预热(修掉高条件数边界瞬态)
- [x] 数据驱动单次 ILA(`fit_measured`,OpenDPD benchmark 协议)
- [x] 三个真实数据集 baseline 数字(见 00_overview §10.1)

**真实数据基准(Phase 2 必须超越的线)**:DPA_160MHz 上 GMP-510
PA 建模 NMSE -39.2 dB、DPD 后 ACLR -52.8 / EVM(谱) -54.0。

## Phase 2:神经 PA 建模 + Neural DPD

目标:在相同数据/指标下超过 GMP baseline。以 OpenDPD 实证过的配方为
起点(Phase 1.5 检视结论):

- [ ] 引入 PyTorch;`PAModel` 接口的 `TorchPAModel` 适配基类
- [ ] 特征工程按 OpenDPD 实证配方:6 通道 `[I, Q, |x|, |x|³, cosφ, sinφ]`
      (注意是 |x|³ 不是 |x|²;原始 I/Q 不做均值/方差归一化)
- [ ] 训练方式:滑窗 frame(frame_length≈200、stride=1)+ BPTT,
      AdamW,MSE 损失,按验证集指标选 best model
      (PA 模型选 NMSE,DPD 选 ACLR_AVG)
- [ ] GRU / DGRU PA 行为模型;目标:APA_200MHz NMSE ≤ -43.5 dB
      (OpenDPD GRU-H23 水平),给 DPD 评估提供可信代理——
      Phase 1.5 已证明 GMP 代理在强非线性 PA 上不够用
- [ ] Neural DPD 用 **DLA(直接学习)**:冻结 PA 代理,梯度穿透 BPTT
      训练前置 DPD,目标 `G·x`(G = 峰值幅度比,`target_gain_opendpd`);
      注意 OpenDPD 的神经 DPD 全部是 DLA,不是 ILA
- [ ] 复现目标(~500 参数,OpenDPD 口径):DPA_160MHz ACLR ≤ -52
      (GRU 水平)进而冲 -56.8(TRes-DeltaGRU);APA_200MHz ACLR ≤ -53.4
- [ ] WiFi 7 合成链路上验证:320 MHz/4096-QAM 下 Neural DPD EVM
      (星座域)< -47 dB
- [ ] Cadence Envelope 真实数据接入(用 `align_delay` 预处理)
- [ ] 1D-CNN/TCN 变体(面向 ASIC);Transformer 探索(320 MHz 记忆效应)
- [ ] CFR(削峰)模块,解决深压缩工作点的可逆性问题

经验教训(已实证,勿重蹈):线性参数模型(MP/GMP)必须 LS 闭式解,
SGD 训练同一模型差 9 dB+ ACLR;神经模型才需要梯度训练。

## Phase 3:量化与 FPGA/ASIC 部署

目标:满足 320 MHz(> 640 MSPS)实时性。

- [ ] PyTorch → ONNX 导出链
- [ ] INT16/INT8 量化感知训练,定点仿真比对(bit-true 模型);
      对标 OpenDPD 的 W16A16 QAT 方案(对称有符号 INT、scale 取 2 的幂、
      STE 直通估计,从浮点 checkpoint 微调)
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
Phase 1 (baseline) ✅
   └─→ Phase 1.5 (OpenDPD 对标检视) ✅
          └─→ Phase 2 (neural, 真实数据)
                 └─→ Phase 3 (部署)
                 └─→ Phase 4 (联合设计,可与 Phase 3 并行)
```
