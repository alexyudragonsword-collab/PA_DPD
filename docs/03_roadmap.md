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

## Phase 3:量化与 FPGA/ASIC 部署(进行中)

目标:满足 320 MHz(> 640 MSPS)实时性。

- [x] **线性参数模型定点部署**(`padpd.deploy`):对称有符号、scale 取
      2 的幂的 bit-true 量化器 + `FixedPointPolyModel`(逐抽头激活量化、
      宽累加器)+ MAC 硬件成本估计。MP/GMP/DDR 无需 QAT,训练后直接量化
      (`scripts/quantize_dpd.py`)。
- [x] **神经模型 PTQ**(`padpd.deploy.neural_ptq`,`quantize_neural_ptq`):
      训练后量化权重+激活,bit-true 前向,无需重训。TCN 前馈完全 bit-true,
      RNN 内部递归近似(如实标注)。`scripts/quantize_neural_pa.py`。
- [ ] 神经模型 QAT(对标 OpenDPD W16A16:对称 INT、scale=2 的幂、STE、
      从浮点 checkpoint 微调)——需 GPU;PTQ 已证明 W12 几乎无损,QAT 收益
      主要在 W8 及以下
- [x] **部署交接链**(`padpd.deploy.export` + `scripts/export_deploy.py`):
      ①神经模型 → ONNX(onnxruntime 数值验证,max err ~1e-6);②线性模型
      → 整数定点系数 JSON(整数码 + 2 的幂 scale,硬件 `acc+=code_w*code_x`
      后移位);③bit-true 参考输入/输出向量 CSV,供 RTL 逐样本比对。
- [ ] 剪枝/蒸馏(蒸馏需 GPU)
- [ ] FPGA 原型(HLS 或 RTL),用上面的 ONNX/系数/参考向量逐样本比对
- [ ] SDR/GNU Radio 台架闭环验证

### 定点 DPD 实测(DPA_160MHz,ACLR_AVG dBc,神经代理评估)

| DPD 基函数 | 复系数 | float | W16 | W12 | W10 | MAC/样本 |
|-----------|-------|-------|-----|-----|-----|---------|
| **DDR r=1** | 140 | -51.6 | **-51.3** | -40.4 | -29.4 | **560**(358 GMAC/s) |
| GMP-510 | 255 | -50.2 | -50.1 | -46.6 | -38.5 | 1020(653 GMAC/s) |

**经典模型部署权衡**:(1) W16 下 DDR 完胜——ACLR 更好且硬件少 45%。
(2) 低位宽下 GMP 更鲁棒(W12:GMP -46.6 vs DDR -40.4),因 GMP 抽头多、
冗余大,量化噪声被平均;DDR 抽头少、基函数动态范围大,量化打击更狠。

### 神经 PTQ vs 经典定点(DPA_200MHz PA 建模,test NMSE dB)

| 模型 | real MAC/样本 | float | W16 | W12 | W10 | W8 |
|------|--------------|-------|-----|-----|-----|-----|
| **TCN-H16(神经)** | **448** | -34.9 | -34.9 | **-34.8** | **-33.3** | **-25.9** |
| DDR r=1 | 560 | -34.0 | -33.9 | -27.7 | -16.9 | -4.9 |
| GMP-510 | 1020 | -33.7 | -33.7 | -31.3 | -22.5 | -11.4 |

**关键部署结论(反转直觉)**:神经 TCN 不仅浮点最准,**量化鲁棒性也碾压
多项式**——W10 时 TCN 几乎不掉(-33.3),而 DDR/GMP 已崩(-16.9/-22.5);
W8 时 TCN 仍可用(-25.9),多项式基本死亡。且 TCN MAC(448)比 DDR(560)、
GMP(1020)都低。**浮点更准 + 量化更稳 + 算力更省,三项全赢。**
机理:多项式基 |x|^k 动态范围跨数量级,量化摧毁高阶项精细抵消;TCN
激活有界(Hardswish)、特征尺度良好,量化噪声均匀温和。

选型指导:能上神经模型就上 TCN(部署综合最优);纯经典约束下 W16 选 DDR、
极低位宽选 GMP。

验收:W16 定点与浮点差 <0.5 dB(满足);吞吐 ≥ 640 MSPS。

## Phase 4:AI Native PA 联合设计(进行中)

目标:PA 设计 + DPD 联合优化,而非"先设计 PA 再补救线性度"。

- [x] **PA/DPD 联合设计权衡研究**(`padpd.codesign` + `scripts/run_codesign.py`):
      扫描 PA 工作点,每点评估效率代理、DPD 达标所需最小复杂度、是否可逆;
      对比"顺序设计"vs"联合设计"。
- [x] **可微 PA + 梯度联合寻优**(`padpd.codesign_torch` +
      `scripts/run_codesign_grad.py`):可微 Saleh PA(drive 为可学参数)+
      内层 LS 最优 DPD(可微),梯度对 PA 工作点做谱约束优化。
- [ ] AI 生成 PA 架构候选 → Spectre 自动仿真回环(需 EDA)
- [ ] WiFi 7 全系统(MLO、多信道)级联评估

### 联合设计实测(160 MHz/1024-QAM,EVM spec -40 dB,DDR DPD)

| PA drive | PAE 代理 | DPD 达标代价 | DPD 后 EVM | 可逆 |
|----------|---------|-------------|-----------|------|
| 0.14 | 20.2% | 23 系数 | -50.4 | ✅ |
| **0.17** | **24.1%** | **23 系数** | **-40.6** | ✅ 联合最优 |
| 0.20 | 27.8% | 149(上限) | -29.6 | ❌ 不可逆 |
| 0.24 | 32.3% | 149(上限) | -20.7 | ❌ |

**核心结论(量化了"AI Native"命题)**:
- **顺序设计**(先把 PA 冲到最高效率 0.24 → 32.3% PAE,再补 DPD):**撞墙**
  ——峰值越过 PA 可逆区,连 149 系数的 DPD 都只到 -20.7 dB,过不了 spec。
- **联合设计**(在 DPD 预算内选最高效率):drive 0.17,24.1% PAE,**仅 23
  系数**即达标 -40.6 dB。
- 可逆性壁垒是**突变**的:DPD 代价在 0.17 前平坦(23),0.20 骤升到上限并
  失败——说明"效率-线性度"边界不能靠事后 DPD 平滑跨越,必须设计时就把
  DPD 一并考虑。这正是"先设计 PA、再补救线性度"范式的根本局限。

### 可微梯度联合寻优(80 MHz/256-QAM,EVM spec -38 dB)

`scripts/run_codesign_grad.py`:可微 Saleh PA(drive 可学)+ 内层 LS 最优
DPD,梯度谱约束优化工作点。

| 设计 | drive | PAE 代理 | EVM | 达标 |
|------|-------|---------|-----|------|
| 保守(固定 drive 0.08) | 0.080 | 11.8% | -56.7 | ✅(过度线性) |
| **梯度联合优化** | 0.146 | **20.9%** | -46.8 | ✅ |

梯度优化自动把工作点抬到更高效率(**+9.1 个 PAE 百分点**),仍满足 spec
——保守设计白白浪费的效率被 autograd 找了回来。轨迹图显示 drive 爬向 spec
边界后被弹回振荡:**逼近可逆壁垒时 landscape 近乎不连续,梯度会振荡**,
这也解释了为何离散 Pareto 扫描(上一小节)是更稳健的生产方法——两者互补:
梯度法快速定位、离散法在壁垒附近可靠定标。

## 里程碑依赖

```
Phase 1 (baseline) ✅
   └─→ Phase 1.5 (OpenDPD 对标检视) ✅
          └─→ Phase 1 收尾 (CFR/持久化/CI) ✅
                 └─→ Phase 2 (neural, 真实数据) ✅
                        └─→ Phase 2.5 (长帧/TCN/DPD 复现) ✅
                        └─→ Phase 3 (部署:定点/PTQ/导出 ✅ / QAT·RTL ⏳)
                        └─→ Phase 4 (联合设计:权衡研究 ✅ / 梯度寻优 ✅)
```
