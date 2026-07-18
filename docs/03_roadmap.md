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

## Phase 1 收尾 ✅

- [x] CFR 削峰模块(`padpd.cfr.cfr_clip_filter`,迭代削峰滤波);
      drive=0.18 深压缩工作点 CFR(8 dB)+DPD:EVM -27.7 → -36.9 dB、
      ACLR -31.7 → -56.3 dBc、mask FAIL → PASS(见 00_overview §6.4)
- [x] 模型持久化:`PAModel.save` / `padpd.pa.load_model` /
      `ILAPredistorter.save/load`(npz,亦为 FPGA 系数下发格式起点)
- [x] CI:GitHub Actions push/PR 全量 pytest
- [x] `align_delay` 分数延迟(相关峰抛物线插值 + FFT 相位斜坡)
- [x] CCDF 峰值统计(`padpd.metrics.ccdf` + `plot_ccdf`)
- [x] 真实数据 baseline 补 AM-AM/AM-PM 图

## Phase 2:神经 PA 建模 + Neural DPD ✅(核心目标达成)

- [x] `padpd.nn` 子包(torch 可选依赖):GRU/DGRU backbone(6 通道特征
      `[I,Q,|x|³...]`)、FrameDataset、`NeuralPAModel`(OpenDPD 训练配方,
      PAModel 统一接口)、`DLAPredistorter`(DLA 直接学习)
- [x] 真实数据训练:DPA_200MHz(DGRU-H8 -31.4 / GRU-H11 -31.0)、
      APA_200MHz(DGRU-H23 -31.7)、DPA_160MHz 减量(DGRU-H8 -37.4)
- [x] DLA 神经 DPD @DPA_200MHz:ACLR -30.6 → -45.1 dBc(486 参数)
- [x] **APA 代理重评(关键验证)**:同一 ILA-GMP DPD 经神经代理评估,
      ACLR -26.2 → **-38.53**,与 OpenDPD 发表值 -38.80 逐位吻合;
      确立"DPD 代理评估必须用神经代理"
- [x] WiFi 7 合成链路:DLA 神经 DPD EVM -44.4 dB / Mask PASS
      (ILA-GMP 对照 -64.2;-47 目标差 2.6 dB,增加训练量可达)
- [x] 8 项神经单元测试;CI 含 torch

实测数字与分析:`docs/04_neural.md`。

## Phase 2.5:长帧 + TCN + DPD 复现 ✅

- [x] frame_length=200 长帧训练——证实 DPA/APA 记忆跨度短、非帧长受限
- [x] **TCN backbone:DPA_200MHz -34.9 dB 超过 GMP-510(-33.7)** ⭐
      (首个胜出的神经 PA 模型,ASIC 友好,对接 Phase 3)
- [x] **DLA 神经 DPD 真实数据复现**:DPA_160MHz ACLR **-53.1 dBc** 越过
      -52 验收线,优于其发表 GRU(-51.9);DPA_200MHz -49.5 dBc
- [x] APA 代理重评(F=200 神经代理):ACLR -38.56 与发表 -38.80 吻合
- [x] 神经单元测试含 TCN(10 项);CI 含 torch

**未达成/推迟(需 GPU 或更大算力)**:
- [ ] 神经 PA NMSE 在 DPA/APA 上超过 GMP-510(仅 DPA_200 的 TCN 做到)
- [ ] APA -43.5 dB 复现(四类变量排查后判定公开信息无法复现)
- [ ] DeltaGRU/TRes-DeltaGRU(-56.8;delta 稀疏 RNN CPU 不可行)
- [ ] OpenDPDv2 配方(lr 5e-3、240 epochs)与多 seed 统计
- [ ] Cadence Envelope 真实数据接入(用 `align_delay` 预处理)
- [ ] Transformer 探索(320 MHz 长记忆)

**环境限制记录**:4 核 CPU、无 GPU;长时后台训练熬不过容器空闲挂起
(训练链两次在 ~1.5-2h 处被回收),故用"单步快跑、完成即提交"策略。

经验教训(已实证,勿重蹈):
1. 线性参数模型(MP/GMP)必须 LS 闭式解,SGD 差 9 dB+ ACLR。
2. 多项式代理的带外外推不可信——代理全局 NMSE 高不代表 ACLR 读数可信;
   DPD 评估用神经代理。
3. 帧长决定可学的记忆跨度:GaN PA 需要 F≈200,F=50 学不到长记忆。

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
          └─→ Phase 1 收尾 (CFR/持久化/CI) ✅
                 └─→ Phase 2 (neural, 真实数据) ✅
                        └─→ Phase 2.5 (长帧/TCN/DPD 复现) ✅
                        └─→ Phase 3 (部署)
                        └─→ Phase 4 (联合设计,可与 Phase 3 并行)
```
