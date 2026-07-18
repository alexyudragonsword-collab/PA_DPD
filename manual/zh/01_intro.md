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

![Web 版工作台总览(深色主题)](assets/web_home_dark.png)

## 1.2 两个图形界面

平台提供两个功能同构的 GUI,共享同一计算服务层与实验注册表:

| | Web 工作台 | 桌面版 |
|---|---|---|
| 技术栈 | Streamlit + Plotly(交互缩放) | PySide6 + matplotlib |
| 启动 | `streamlit run gui/app.py` | `python -m gui_qt.main` |
| 安装 | `pip install -e .[gui]` | `pip install -e .[gui-qt]` |
| 适合 | 团队共享、远程访问 | 单机使用、打包为 Windows exe |

在任意一版里完成的实验(模型拟合、DPD 运行、位宽扫描)都会写入共享的
`gui_runs/` 注册表,另一版的"结果比较"页可直接看到。

![桌面版总览页](assets/qt_home.png)

## 1.3 安装

需要 Python 3.10–3.12:

```bash
git clone <本仓库>
cd PA_DPD
pip install -e .            # 核心(numpy/scipy/matplotlib)
pip install -e .[gui]       # + Web 工作台(streamlit/plotly)
pip install -e .[gui-qt]    # + 桌面版(pyside6)
pip install -e .[nn]        # + 神经功能(torch,可选)
```

不安装 `torch` 也能使用全部经典功能(波形 / 经典建模 / ILA DPD /
定点导出 / 离散联合设计);神经建模、DLA 与梯度寻优页面会给出明确
提示。

如需真实测量数据,克隆 OpenDPD 公开数据集(约 55 MB):

```bash
git clone --depth 1 https://github.com/lab-emi/OpenDPD.git ../OpenDPD
```

## 1.4 语言与主题

两版 GUI 的**侧栏底部**都有语言(中文 / English)与主题(深色 / 浅色)
切换。选择保存在 `gui_prefs.json`,两版共享——Web 里切到英文浅色,
桌面版下次启动即同款外观。

![浅色主题 + 英文界面示例](assets/web_en_light.png)

## 1.5 五分钟上手路线

1. 打开**波形工作台**,默认参数点"生成波形",看 PSD 与 PAPR;
2. 到 **PA 建模**页,数据源选"合成 ReferencePA",点"拟合模型"
   (默认 GMP,秒级完成),得到 NMSE 与拟合 PSD;
3. 到 **DPD 实验室**,直接点"运行 DPD",约半分钟后看 EVM/ACLR
   前后对比与 Mask 徽章;
4. 到**结果比较**页勾选刚才两条 run,点"对比选中"出柱状图;
5. 到**部署**页勾选模型跑"位宽扫描",再"生成产物"导出整数系数
   与参考向量。

后续章节将逐页展开。工程实现细节(算法推导、训练配方、完整实验
记录)见仓库 `docs/` 目录。
