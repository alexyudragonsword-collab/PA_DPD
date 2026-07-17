# WiFi 7 PA + DPD AI 辅助研发工程

面向 RFIC/Analog IC 团队的 WiFi 7(802.11be)功率放大器(PA)+ 数字预失真(DPD)研发框架,覆盖:

```
CMOS/SOI PA 设计 → 电路仿真(Spectre)→ 行为建模(GMP baseline / 神经网络)
     → DPD(ILA / Neural)→ FPGA/ASIC 部署 → WiFi 系统验证(EVM/ACLR/Mask)
```

**Phase 1(当前)**:可运行的 Python 基线框架 —— 802.11be 风格 OFDM 波形、经典 PA 行为模型(Saleh/MP/GMP)、ILA-GMP DPD、完整系统指标(EVM/ACLR/频谱 Mask/AM-AM/AM-PM),用合成数据端到端跑通,并预留 Cadence/MATLAB/OpenDPD 真实数据接口。

## 快速开始

```bash
pip install -e .          # 安装 padpd 包(依赖 numpy/scipy/matplotlib)
pytest tests/             # 运行全部单元测试(42 项)
python scripts/run_baseline_demo.py       # 端到端 baseline demo
python scripts/generate_dataset.py        # 生成合成 PA 数据集(.npz)
```

demo 实测结果(160 MHz / 1024-QAM / 虚拟 ReferencePA):

| 指标 | 无 DPD | ILA-GMP DPD |
|------|--------|-------------|
| EVM | -19.0 dB | **-57.4 dB** |
| ACLR(上邻道) | -31.1 dBc | **-54.8 dBc** |
| 发射 Mask | FAIL | **PASS** |

GMP 行为模型验证集 NMSE:**-57.8 dB**(52 系数),优于 Memory Polynomial 的 -52.2 dB。
demo 同时输出 PSD / 星座图 / AM-AM & AM-PM 对比图到 `results/`。

## 仓库结构

```
docs/                    # 中文文档
  00_overview.md         #   总体研发流程(AI 增强流程全景)
  01_environment_setup.md#   研发环境搭建清单(软件/开源工具链/数据集/GPU/EDA 接口)
  02_data_interface.md   #   数据接口规范(Cadence CSV / MATLAB .mat / OpenDPD)
  03_roadmap.md          #   分阶段路线图(Phase 1~4)
src/padpd/               # Python 包(代码与注释为英文)
  waveform/              #   802.11be 风格 OFDM + 16~4096-QAM
  pa/                    #   PA 行为模型:Saleh / MP / GMP / ReferencePA(虚拟 DUT)
  dpd/                   #   ILA 间接学习 DPD
  metrics/               #   EVM / ACLR / PSD+Mask / AM-AM & AM-PM
  data/                  #   IQDataset 容器 + 外部数据加载器
  plotting.py            #   标准对比图
scripts/                 # 端到端 demo 与数据集生成
tests/                   # pytest 单元测试
```

## 设计原则

1. **GMP 是黄金 baseline**:后续所有神经网络模型(GRU/LSTM/Transformer)必须与 GMP 在同一数据、同一指标下对比。
2. **统一模型接口**:所有 PA/DPD 模型实现 `fit(x, y)` / `__call__(x)`,神经模型可直接替换经典模型。
3. **数据源可替换**:`ReferencePA` 是晶体管级仿真的占位,换成 Cadence Envelope 导出数据后下游代码零改动(见 `docs/02_data_interface.md`)。

## 路线图

- **Phase 1**(本仓库当前状态):经典 baseline 全链路 ✅
- **Phase 2**:PyTorch 神经 PA 建模(GRU/LSTM/DGRU)+ Neural DPD,对标 OpenDPD
- **Phase 3**:量化(INT16)/剪枝/蒸馏,FPGA 定点部署验证
- **Phase 4**:可微 PA 模型 + PA/DPD 联合优化(AI Native PA Design)

详见 `docs/03_roadmap.md`。
