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

## Phase 5:现场硬化与硅前/硅后落地 ✅

在完整平台(五阶段 + 双 GUI + 手册 + exe)之上补齐"实验室到量产"链路:

### 5.1 自适应/在线 DPD(`padpd.dpd.AdaptiveDPD`)
指数加权块 RLS 在 GMP/DDR 基上递归更新,从环回观测持续跟踪 PA 漂移。
**LMS/NLMS 刻意不提供**:多项式基条件数 ~1e10,梯度法(即便用暖启协
方差白化)发散为 NaN——这是"线性参数模型必须用 LS 而非 SGD"在在线
场景的翻版。

### 5.2 温漂/老化跟踪研究(`DriftingReferencePA` + `run_drift_study.py`)
时变 PA(drive/AM-AM 拐点/AM-PM 斜率随状态 0→1 漂移)下,冻结批处理
DPD 与自适应 RLS 对比:满漂移时**冻结退化到 -28.4 dB EVM(ACLR
-34.3),自适应保持 -38.8 dB(ACLR -40.6)——现场失效差距 10.4 dB**。

### 5.3 物理效率模型接入联合设计(`codesign.drain_efficiency`)
用 PAE 惯例 `<P_out>/<P_dc>` 从任意 PA 模型的 AM-AM 饱和导出平均漏极
效率(Class A/B/AB;CW 饱和达 π/4 / 0.5,已验证),替换原 PAE 代理;
对 HB 导入的 Wiener-Hammerstein PA 同样成立,故联合设计的效率轴在
流片前即有物理意义。

### 5.4 量化感知训练(`padpd.deploy.qat`)
直通估计的 fake-quant(功率-2 对称,与部署量化器逐位一致)在微调中
把浮点权重适配到目标位宽;对已很抗量化的小 TCN 一致回收 ~0.7-0.8 dB,
PTQ 损失越大回收越多。

### 5.5 RTL 生成器(`padpd.deploy.rtl`)⭐
生成可综合的定点复数 MAC(DPD 系数点积,占 DSP 面积主体)Verilog +
自检 testbench,系数烧成 ROM;`verify_with_iverilog` 用 Icarus Verilog
跑通并**逐位比对 Python 整数金标准:39 抽头 GMP DPD × 64 向量 → 0 错误**。
全整数运算保证 RTL 与 Python 完全一致;基函数生成前端(延迟、|x|^k)
作为独立块。已接入部署导出(经典模型导出即产 `rtl/dpd_mac.v` 并报告
bit-true 通过)。

### 5.6 跨平台 CI + PyPI 打包
CI 扩为 ubuntu/windows/macos 矩阵(+ Linux 3.10/3.12),专用 Linux
job 装 iverilog 跑 RTL 测试;`v*` tag 经 Trusted Publishing 发 PyPI。
wheel/sdist 本地构建 + `twine check` 均通过。

**Phase 3/4 的原 GPU/EDA 待办**:QAT ✅(CPU 可行部分)、RTL ✅(定点
MAC + iverilog 验证);仍需硬件的是 FPGA 上板与 SDR/仪器在环、Spectre
在环联合设计。

## Phase 6:分段样条模型 + LUT DPD ✅

MP/GMP 用全局幂次 `|x|^k`,幂列高度相关(实测条件数 1e7+),阶数一高
即数值病态、峰值区外推失控。样条族改用局部支撑的 B 样条基:任意幅度
处只有 degree+1 个基非零,这既是数值优势也天然就是硬件 LUT。

### 6.1 样条模型族(`padpd.pa.spline` / `spline_state`)
`SplineMemoryPolynomial`(SMP)、`SplineGMP`(滞后/超前交叉包络分支)、
`StateConditionedSpline`(慢功率状态 q_k 与 (r,q) 二维面)、
`CoefficientScheduler`(系数随工况标量 PCHIP 插值)。全部线性于系数,
LS 一步解;`from_signal()` 依数据放节点(hybrid:分位数铺主体 + 均匀铺
压缩尾部)后即为固定节点,可持久化、可作 AdaptiveDPD 模板。
估计侧:相对 ridge、P 样条二阶差分平滑、WLS;`basis_cond()` 直接比条件数。

### 6.2 实测(160 MHz/1024-QAM,ReferencePA)
| 模型 | 系数 | 运行时 MAC/样本 | 条件数 | PA NMSE | DPD EVM |
|---|---:|---:|---:|---:|---:|
| MP o7 m4 | 28 | 112 | 1.2e5 | -52.3 | -57.6 |
| Spline-MP K8 m4 | 40 | **24** | **2.0e2** | -52.3 | -57.2 |
| GMP (default) | 52 | 208 | 1.2e5 | -57.9 | -63.5 |
| Spline-GMP K8 | 76 | **48** | 1.9e3 | -57.7 | -61.7 |

同精度下运行时算力降到 1/4~1/5,条件数低 2-3 个量级。**踩过的坑**:
单位分解使 SplineGMP 交叉分支列块与主载波共线(条件数 2.6e16),
每个交叉分支去掉首个基列后修复(→1.9e3)。

### 6.3 LUT 提取与插值 RTL(`padpd.deploy.lut` / `rtl`)⭐
`lut_from_model` 把每分支复增益采成均匀插值表,`LUTDPD` 是该数据通路
的浮点孪生;`export_lut` 出整数表项 JSON;`emit_lut_rtl` 生成 **LUT
寻址 + 线性插值 + 延迟线 + 复数 MAC 的 Verilog**,自带 testbench 与
整数金标准,`verify_with_iverilog` 逐位验证(errors=0)。LUT256 部署
形态 EVM 零损失;位宽轴与表深轴正交,部署页两个面板分别扫描。

### 6.4 表征驱动的结构定档
双音扫音间距(`padpd.two_tone`)→ 记忆强度 → 记忆深度/交叉项;
增益调制阶跃辨识(`padpd.gain_modulation`)→ τ → `state_alphas`。
自热虚拟 DUT 上辨识出 4.9/29.1 µs(真值 5/30),用辨识 α 配置的状态
样条比纯 SMP 改善 **+10.5 dB**,与真值配置差距 <1 dB。

## Phase 6.5:TX/RX 前端损伤全链路 ✅

Phase 1-6 的模型都是**相位等变**的(只含 x·f(|x|) 形式),对直变收发机
的三类前端损伤在结构上视而不见。本阶段把它们逐一补齐,并给出每类
损伤的专用处理环。

### 6.5.1 相位谐波分支(建模方向)
镜像(IQ 失衡)基带等效 `conj(x)`,counter-IM3(混频器 3LO 谐波经 PA
三阶互调)基带等效 `conj(x)³`,LO 泄漏是 DC 常数——三种相位谐波
e^{+jφ}/e^{−jφ}/e^{−j3φ} **互不可表示**,各需专用分支。
实测:镜像分支 DPD EVM **+22.3 dB**(IRR≈30);conj³ 分支 C-IM3 建模
**+14.5 dB**。部署链全程携带相位阶与 DC(RTL 里 conj³ = 一次复数立方,
分支功率标度用左移对齐,iverilog 位真 0 错误)。

### 6.5.2 三个专用抵消环(`padpd.three_loop`)⭐
分工的依据是结构:相位等变的 PA 失真对另外两个环的估计项**投影为零**。
- **QMC 慢环**(`padpd.dpd.QMCCorrector`):镜像 + LO 泄漏发生在 PA 之前,
  `v = a·z + b·z* + c` 有精确代数预逆,**无结构天花板**——每轮 −19 dB,
  三轮到 **−88.5 dBc**;收编后 DPD 基退回纯相位等变,40 系数 + QMC
  ≥ 81 系数宽基 DPD。
- **观测去嵌环**(`padpd.data.ObservationDeembedder`):整数时延 → CFO →
  分数时延 → 共相漂移 → widely-linear IQ/DC → RX-IM3 逆 → FIR 均衡。
  端到端:不去嵌自适应 **+3.6 dB(失效)** → 去嵌后 **−48.4 dB**。
  其中 RX 纹波/IQ 与 RX-IM3 盲估**原理上不可辨识**,分别用旁路 PA 标定
  采集与衰减步进两采集解决(盲 −29.0 → 标定 −35.9 dB)。
- **DPD 快环**:块 RLS 跟踪 PA 非线性与漂移。
三环同时闭合(12 块冷→热):原始环回 **+33 dB 失效** / 仅去嵌钉在
IRR **−29** / 三环 **−35.1 dB**,镜像残差全程 <−60 dBc。

### 6.5.3 诚实边界:C-IM3 的 TX 侧抵消
conj³ 分支服务建模方向;TX 侧闭环抵消系统性试了**六种方案**——五种
线性 LS 架构(ILA 带 conj³ 列、u 域注入、x 域注入、两个交替记账变体)
全部停在 +2~3 dB,根因是两环耦合(杂散污染主 DPD 的 ILA 估计;注入项
经未线性化的裸 PA 传输;交替方案会把注入学进后逆导致双重抵消)。
第六种是直接学习(torch 梯度经可微样条代理),优于 ILA +1.0 dB,但
**证明了结构天花板 ~−35 dB**:抵消 conj³ 需要无穷高的相位谐波塔。
**工程结论:越过它属于混频器硬件(谐波抑制混频/LO 占空比调节),
不是更聪明的 DPD。**

### 6.5.4 完整实测源容器(`padpd.data.complete`)
单个 npz 承载平台能消费的全部采集:必备 (x,y,fs) + 五个可选采集组
(突发→状态样条、阶跃探针→τ 辨识、旁路标定→RX 去嵌、衰减步进→RX-IM3、
多工况→系数调度),各解锁一类能力;GUI 数据页显示完整度清单并可
一键消费。`scripts/pack_cadence_source.py` 从 Cadence 导出目录打包
(所有采集共用一个定标系数——逐采集归一化会抹掉衰减步进与突发高低段
的相对功率信息)。

## 当前待办

**需硬件/EDA**:FPGA 上板、SDR/仪器在环、Spectre 在环联合设计。
**需 GPU**:H16 神经 DPD 长训练(验收表中唯一未达项)。
**已明确暂缓**:双频段并发 CIM3 基础设施。

## 候选改进

比阶段小、比 issue 大的想法:**都不是承诺**,是被识别出来但当时没做的
事,连同"为什么现在没做"。做之前先确认它仍然值得。

### 算法 / 建模
- **RX-IM3 的高阶逆**:`calibrate_rx_im3` 目前只做一阶逆
  (`y - κ·y|y|²`),在标定电平附近够用;RX 压缩更深或要求更高时需要
  迭代逆或含记忆的 RX 非线性模型。
- **冷却段 τ 拟合的偏差**:回退段对热状态激励弱,冷却 τ 天然比加热 τ
  不确定(线性 RC 的 DUT 在 8 倍窗仍读 0.51)。可尝试加热/冷却共享 τ
  的联合拟合,或把探针低电平抬高一些换取激励。现状是**如实标注不可靠
  而非修正**(见 `hysteresis_reliable`)。
- **观测路径的 RX 记忆**:去嵌器把 RX 线性响应当作静态 FIR 标定;若
  接收机本身有显著非线性记忆,需要更强的模型。
- **双频段并发 CIM3**:已明确暂缓。真要做需要双载波波形基建 + 交叉
  频段的相位谐波记账,工作量接近一个 Phase。

### 工具 / 数据
- **MATLAB 侧的打包桥**:`pack_cadence_source.py` 吃 Cadence CSV;从
  MATLAB 出完整源容器目前要绕一次 Python。可加一个 npy-matlab 的写出
  样例或 `.mat` 直读分支。
- **采集组预览图**:数据页现在只显示采集组的 ✓/✗ 清单,没有每组的
  波形/包络预览。诊断"这份数据对不对"时会想要。

### 界面
- **跨工况调度器没有 GUI 入口**:`CoefficientScheduler` 只能走脚本,
  而完整源容器已经能提供多工况点了,接上去是顺水推舟。
- **QMC / 去嵌环只有演示入口**:两个环在 DPD 页是合成 DUT 的 demo,
  没有"对已注册的实测源跑这两个环"的路径。

### 工程
- **指标数字的三处同步靠人工**(README / `docs/05_performance_summary.md`
  / 手册)。可以定一处为唯一真源、其余生成,或加一个一致性测试。
  当前靠 `tests/test_docs_site.py` 只挡住了阶段级的漂移。
- **文档站只有中文**:`manual/en` 已有英文手册,但 mkdocs 站是中文
  导航。要做英文站得引入 i18n 插件并决定 `docs/` 是否也翻译。
- **发版流程半自动**:tag → Release + exe 已自动,但 CHANGELOG 仍手写。
