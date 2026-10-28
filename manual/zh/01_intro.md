# 1. 产品简介与快速入门

## 1.1 padpd 是什么

**padpd** 是一个面向 RFIC / Analog IC 团队的 **WiFi 7(802.11be)功率
放大器(PA)+ 数字预失真(DPD)AI 辅助研发平台**,把从波形生成到
FPGA/ASIC 交接的完整链路装进一个 Python 工程:

- **802.11be 风格波形**:20–320 MHz 带宽、16–4096-QAM OFDM,含 CFR 削峰;
- **PA 行为建模**:经典(Saleh / Memory Polynomial / GMP / DDR-Volterra)
  与神经网络(GRU / DGRU / TCN)两条路线;
- **数字预失真**:ILA(经典最小二乘)与 DLA(神经直接学习);
- **系统指标**:星座 EVM、ACLR、发射频谱 Mask、AM-AM/AM-PM、CCDF,并
  内置 OpenDPD 论文口径用于横向对标;
- **定点部署**:bit-true 位宽扫描、神经 PTQ、ONNX / 整数系数 / 参考
  向量导出;
- **PA/DPD 联合设计**:离散 Pareto 扫描与可微梯度寻优。

真实测量数据上的代表性结果:DPA_160MHz 数据集 DLA 神经 DPD 将 ACLR 从
-34.5 改善到 **-53.1 dBc**(越过 -52 dBc 验收线);TCN 神经 PA 模型以
464 参数达到 **-34.9 dB** NMSE,超过约 500 参数的经典 GMP 基线。

![桌面工作台:DPD 实验页,按项目 spec 判定](assets/qt_dpd.png)

## 1.2 图形界面

平台的图形界面是一个 PySide6 桌面工作台(`python -m gui_qt.main`),也可
打包成 Windows exe(第 7 章);同一套计算与界面契约还驱动 Android 应用。

界面由三部分组成:

- **左侧导航**按工作流排列:波形 → 数据源 → PA 模型 → DPD → 部署;
  其后是专题实验(增益调制、自适应跟踪、前端三环、联合设计、可微联合
  寻优、双音诊断)与分析(结果比较、用户手册)。
- **顶栏**常驻三样东西,所有结果都以它们为准:**当前数据源**、工作区
  里的 **PA 模型**数量、**项目 Spec**(EVM 与 ACLR 上限,发射 Mask 用
  802.11 模板)。点数据源可切换,点 Spec 可修改。
- **实验页**左侧是参数(只显示当前选择下有意义的输入),右侧依次是:
  对 spec 的判定卡(数值、限值、余量、通过/不通过、对照组)、辅助指标、
  可悬停读数与框选放大的图、前后对比表,以及这条结果的来源(run 编号、
  参数、数据源、用时)。

数据源、拟合出的模型与 spec 都保存在工作区里,重启后仍在;每次运行都记入
`gui_runs/`,可在"结果比较"页并排比较。

![桌面版总览页](assets/qt_home.png)

> 早期版本另有一个 Streamlit Web 版(`gui/`),已于 2026-10-28 退役:
> 两套界面各自手写、逐渐分叉(同一个 DPD 页,桌面版 21 个输入、Web 版
> 12 个)。现在只有一套界面契约(`gui_core/experiments.py`),桌面与
> Android 共用。

## 1.3 安装

需要 Python 3.10–3.12:

```bash
git clone <本仓库>
cd PA_DPD
pip install -e .            # 核心(numpy/scipy/matplotlib)
pip install -e .[gui-qt]    # + 桌面工作台(pyside6/pyqtgraph)
pip install -e .[nn]        # + 神经功能(torch,可选)
python -m gui_qt.main
```

不安装 `torch` 也能使用全部经典功能(波形 / 经典建模 / ILA DPD /
定点导出 / 离散联合设计);神经建模与 DLA 的选项会给出明确提示,
"可微联合寻优"页不出现。

如需真实测量数据,克隆 OpenDPD 公开数据集(约 55 MB):

```bash
git clone --depth 1 https://github.com/lab-emi/OpenDPD.git ../OpenDPD
```

## 1.4 语言与主题

顶栏右侧切换语言(中文 / EN)与主题(浅色 / 深色)。切换是**原地**进行的:
已有结果不会丢失,只是换一种语言重新呈现。选择保存在 `gui_prefs.json`,
下次启动沿用。

![英文界面 + 深色主题](assets/qt_en_dark.png)

## 1.5 五分钟上手路线

1. 打开**数据源**页:工作区自带一个合成源(ReferencePA,160 MHz /
   1024-QAM,drive 0.14),已是当前数据源;
2. 到 **PA 模型**页,默认 GMP 点"运行"(秒级),得到测试 NMSE;模型自动
   存进工作区;
3. 到 **DPD** 页点"运行"(数秒),看三张判定卡:EVM、ACLR 较差一侧、
   发射 Mask 带外余量,以及无 DPD 时的对照;
4. 改一个参数(例如基函数),结果上方会出现"输入已改动"提示——它仍是
   上一次的结果;点"复现"把参数填回,或"重新运行";
5. 在结果底部点"在结果比较中打开",并排比较同类运行及其参数差异;
6. 到**部署**页勾选模型跑位宽扫描,再"导出交接产物"。

后续章节将逐页展开。工程实现细节(算法推导、训练配方、完整实验
记录)见仓库 `docs/` 目录。
