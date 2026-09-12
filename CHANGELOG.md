# 更新日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

尚无。

## [0.2.0] - 2026-09

Android app 从可行性 spike 走到真机可用,加上一层此前完全缺席的工程
保障:静态检查、覆盖率门槛、CI 权限与超时。

### Android app(新增)
- `android/` **Chaquopy 工程**:APK 里装真正的 CPython 3.10 + numpy +
  scipy,算的是同一份 `padpd` 与同一个 `gui_core` 服务层;界面 Compose,
  图表由 Kotlin 渲染器按 Python 发来的规格画。**全程离线,清单里零个
  `uses-permission`**;
- 桌面九个功能页全部移植,另加 14 种图表规格的画廊;
- **两套导航壳,构建时选**:`classic`(顶部横向栏)与 `drawer`(左侧
  抽屉,横滑开合,与桌面 Qt 的常驻左侧导航同形)。41 条设备测试共用
  一批 `nav:<id>` 标签,两套壳上都成立;
- **padpd 可编译出货**:`-PpadpdCompiled=true` 走 Cython 交叉编译成
  Android `.so`。它只把读算法的成本从「解压就能看」抬到「得反汇编」,
  不是授权校验也不是数据保护;
- 壳 × 形态 = **四个 release**,CI 一次全部装配。每个 APK 带一份
  `assets/padpd-build.json` 自报身份,构建 job 与设备 job 都断言一次
  ——Gradle 把这四个全叫 `app-release.apk`,重命名之前谁也不知道谁是谁;
- 体积:解释版 59,668,327 B,编译版 62,127,995 B(+2,459,668);
- **2026-08-25 编译版在 arm64 真机实测安装并可用**。模拟器全绿不等于
  那些 `.so` 在真设备上 import 得起来。

### 工程保障(新增)
- **ruff** 进 CI(配置在 `pyproject.toml`,版本 pin 死),跑在 3.10 上并
  附带 `compileall`——ruff 的 parser 不管 target-version 都按 PEP 701 收
  跨行 f-string,而 `scripts/` 没有任何测试 import;
- 首轮扫出并修掉:19 处并排数组 `zip()` 补 `strict=True`(静默截断会把
  某个分支的 LUT 增益配到别人的延迟上)、2 处错位一位的写法改
  `itertools.pairwise`、1 条从来没被读过的死测量、3 处 `subprocess.run`
  显式 `check=False`;
- **覆盖率门槛**进 `test-full`(唯一装全可选依赖的 lane):实测 **92.10%**
  (3960 条语句漏 313),门槛设 90 并按棘轮用,只许往上调;
- 六个 workflow 全部写明 `permissions`。`publish.yml` 原先只列 `id-token`,
  而 job 级 permissions 块是整体替换——checkout 拿不到读权限,那个
  workflow 从未跑过所以一直没暴露;
- 五个没有 `timeout-minutes` 的 job 补上;Nuitka(Windows runner 上最长
  90 分钟、按 2 倍计费)改为只在 `v*` tag 与手动触发时跑。

### 修复
- `psd()` 没有下限,常包络输入会让 log10 取到 0 → `-inf`,进到绘图自适应
  和 Android 图表读的 float32 显示数组里;全零输入更是 0/0 = nan 且不
  告警。现按峰值下 -200 dB 取平(80 MHz OFDM 实测底噪 -136 dB,留 64 dB
  余量);
- 图表 fixture 的浮点比较改为规格 7 位有效数字 + 载荷按 `np.allclose`
  容差——跨机器 BLAS 不可逐位复现,此前在五个平台上一起红过。

### 文档
- 根 README 补上 Android 一节(此前只写了两个前端);
- 新增 16:9 中文平台总览页 `docs/pages/platform-overview.html`;
- `CONTRIBUTING.md` 新增「静态检查」一节,写清 E402/BLE001/B905 三条规则
  为什么是打开的。

### 已知限制(本版新增)
- GitHub Pages 未在仓库开启,`Docs` workflow 的 deploy job 因此 404 失败;
  构建站点的 build job 是绿的;
- 仓库默认分支仍是特性分支而非 `main`。

## [0.1.0] - 2026-08

首个版本。从零到覆盖 WiFi 7(802.11be)PA 行为建模 → DPD → 定点部署
→ 联合设计的完整链路,并在三套公开实测数据上对标 OpenDPD。

### 波形与指标
- 802.11be 风格 OFDM 波形(20-320 MHz,16~4096-QAM)、CFR 削峰;
- 星座域 EVM、802.11 风格 ACLR、发射 Mask、AM-AM/AM-PM、CCDF;
- OpenDPD 兼容口径(谱域 EVM、ACLR_AVG)以便与论文横向对比。
  **两套口径数值不可混比**,GUI 按数据源自动选择并标注。

### PA 行为模型
- 经典:Saleh、Memory Polynomial、GMP、DDR-Volterra(+ OpenDPD ~500
  参数对标 preset);
- 神经:GRU / DGRU / TCN。**TCN-H16(464 参数)NMSE -34.9 dB,首次
  超过 GMP-510 的 -33.7**,且量化鲁棒性远超多项式;
- 分段样条族:SMP / SplineGMP / 状态条件化样条 / 跨工况系数调度器。
  同精度下运行时 MAC 降到 1/4~1/5(24 vs 112),条件数低 2-3 个量级;
- 虚拟 DUT:ReferencePA、漂移 PA、自热 PA(耗散功率→RC 热网络)、
  TX 前端(镜像 + LO 泄漏 + counter-IM3);
- HB/S21 导入装配 Wiener-Hammerstein,流片前即可预判 PA+DPD 能否过 spec。

### DPD
- ILA(经典 LS,合成源闭环迭代 / 实测数据驱动)、DLA(神经直接学习);
- 自适应在线 DPD:块 RLS / 白化 NLMS / APA。满漂移下领先冻结批处理
  **10.4 dB EVM**;
- 三个专用抵消环:QMC(镜像+LO 泄漏,精确预逆,三轮 **-88.5 dBc**)、
  观测去嵌(时延/CFO/相位漂移/RX IQ/纹波/RX-IM3)、DPD 快环。三环
  同时闭合在漂移 PA 上:原始环回 +33 dB(失效)→ 三环 **-35.1 dB**。

### 表征驱动的结构定档
- 双音扫音间距 → 记忆强度 → 记忆深度与交叉项;
- 增益调制阶跃辨识 → τ → 状态样条的 `state_alphas`。自热 DUT 上辨识
  4.9/29.1 µs(真值 5/30),状态样条比纯 SMP **+10.5 dB**。

### 部署
- 定点位宽扫描(bit-true)、神经 PTQ 与 QAT;
- 整数系数 JSON、参考向量 CSV、ONNX 导出(数值验证 max err ~1e-6);
- **RTL 生成器**:可综合 Verilog(GMP 复数 MAC 与 LUT 寻址+线性插值
  两条数据通路),iverilog 逐位验证 **0 错误**;
- LUT 提取 + 表深/位宽双轴扫描,LUT256 部署形态 EVM 零损失。

### 数据接口
- OpenDPD 数据集目录、Cadence Envelope CSV、MATLAB .mat、IQDataset .npz;
- 整数+分数延迟自动对齐;
- **完整实测源容器**:单 npz 承载五个可选采集组(突发/阶跃探针/旁路
  标定/衰减步进/多工况),各解锁一类能力;
- `scripts/pack_cadence_source.py` 从 Cadence 导出目录一键打包。

### 界面与文档
- 双版本 GUI(Streamlit Web + PySide6 桌面),9 页功能同构,共享服务层
  与实验注册表,中英文 + 深浅色切换;
- 内置双语用户手册(8 章)、`docs/` 七篇工程文档、三页自包含速览 HTML;
- Windows exe 打包(PyInstaller onedir + Nuitka onefile),云端 CI 构建。

### 记录在案的负结果

这些是本项目的资产,与正面结果同等重要:

- **多项式代理带外外推不可信**:APA 上 ACLR 读数可差 12 dB;DPD 评估
  必须用神经代理(换代理后与发表值 -38.80 逐位吻合);
- **线性参数模型不能用 SGD**:同一 GMP 用 SGD 训练 ACLR 差 9 dB 以上;
- **朴素对角预条件在 DPD 基上发散**:病态来自列间相关而非尺度,只调
  尺度不去相关的方法(含普通 LMS/NLMS)要么发散要么原地打转;
- **PA 后 C-IM3 的 DSP 抵消存在结构天花板 ~-35 dB**:五种线性 LS 架构
  止步 +2~3 dB,直接学习(精确梯度)证明瓶颈是预失真器结构而非算法
  ——抵消 conj(x)³ 会生成无穷高的相位谐波塔。**越过它属于混频器硬件**;
- **RX 纹波/IQ 与 RX-IM3 盲估原理上不可辨识**:前者与 PA 线性响应
  混叠(盲均衡会洗掉 PA 记忆),后者与 PA 立方近共线;必须用旁路标定
  与衰减步进两采集。

### 已知限制
- H16 神经 DPD 长训练未达 -47 dB 验收线(本环境 4 核 CPU 无 GPU,
  三次被容器回收),需 GPU 环境复跑;
- APA_200MHz 的 -43.5 dB PA NMSE 经系统排查判定为公开信息无法复现
  (不影响 DPD 结论);
- FPGA 上板、SDR/仪器在环、Spectre 在环联合设计需硬件/EDA;
- 双频段并发 CIM3 基础设施暂缓。

[未发布]: https://github.com/alexyudragonsword-collab/PA_DPD/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/alexyudragonsword-collab/PA_DPD/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/alexyudragonsword-collab/PA_DPD/releases/tag/v0.1.0
