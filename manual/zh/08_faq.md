# 8. FAQ 与路线图

## 8.1 常见问题

**Q:神经建模 / DLA / 梯度寻优页面提示缺 PyTorch?**
`pip install -e .[nn]` 安装 torch(CPU 版即可)。不装也不影响全部
经典功能。

**Q:总览页提示"OpenDPD 未找到"?**
`git clone --depth 1 https://github.com/lab-emi/OpenDPD.git`,在数据
管理页把目录指向其 `datasets/` 即可;或忽略——合成 ReferencePA 不
依赖它。

**Q:加载自己的 CSV 后 AM-AM 图是"一团云"?**
输入输出未对齐。重新加载并勾选**自动延迟对齐**;若仍散,检查采样率
是否正确、I/Q 列是否对应。

**Q:DPD 后 EVM 反而更差 / 不收敛?**
工作点过深(峰值进入 PA 不可逆区)。降低 drive,或开 CFR(目标 PAPR
7–8 dB)后再跑 DPD;参见第 5.4 节。

**Q:GUI 里神经训练能到论文精度吗?**
GUI 默认 epochs ≤ 100、hidden ≤ 32,定位交互实验。论文级复现请用
`scripts/train_neural_pa.py --frame-length 200 ...`(配方见
`docs/04_neural.md`),建议 GPU。

**Q:实测源为什么必须选"评估代理"?**
实测数据没有可解调的星座真值,DPD 后的 PA 输出需要一个 PA 模型来
预测;而且该代理应为神经模型(多项式带外不可信,见第 6.3 节)。

**Q:两版 GUI 的实验为什么互相可见?**
run 注册表(`gui_runs/`)、语言/主题偏好(`gui_prefs.json`)与模型
checkpoint(`models/`)都在仓库目录共享。

**Q:浅色主题下图表文字看不清 / 中文变方框?**
平台已为深浅主题各配一套图表配色,并自动选择系统中文字体
(Windows 微软雅黑 / Linux 需装 `fonts-wqy-zenhei` 之类)。

**Q:切换语言后桌面版页面上的图消失了?**
切语言/主题会重建页面(文案在构造时固化),数据源、模型与 run 都
保留,重新点一次"运行"即可重画。

## 8.2 环境需求

| 场景 | 需求 |
|---|---|
| 经典全流程 + GUI | 4 核 CPU、8 GB 内存即可 |
| 神经交互实验(GUI) | CPU 可跑(分钟级) |
| 论文级神经训练 / 多 seed | 建议 GPU(CUDA 版 torch) |

## 8.3 路线图与边界

已完成:Phase 1(经典链路)→ 1.5(OpenDPD 对标)→ 2/2.5(神经建模
与 DLA)→ 3(定点部署与导出)→ 4(联合设计)→ 双 GUI 与本手册。

待硬件/EDA 条件推进的方向(接口与脚本已就绪):

- **QAT**(量化感知训练,W8 以下保精度)与多 seed 统计——需 GPU;
- **FPGA RTL 落地**——用第 7 章参考向量做逐样本比对;
- **Spectre 在环联合设计**——把虚拟 PA 换成 EDA 仿真回环;
- **SDR/仪器台架在环 DPD**——`fit_measured` 数据驱动接口已预留。

工程实现细节、完整实验记录与逐阶段结论,见仓库 `docs/` 目录七份
文档;打包细节见 `packaging/README_packaging.md`。
