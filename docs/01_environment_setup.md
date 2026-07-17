# WiFi 7 PA + DPD 研发环境搭建清单

覆盖:软件、开源代码、数据集、GPU 训练环境、Cadence/ADS 接口、Python
自动化脚本框架。

## 1. Python 环境(Phase 1 必需)

```bash
# Python >= 3.10,建议 venv/conda 隔离
python -m venv .venv && source .venv/bin/activate
pip install -e .        # 安装本仓库 padpd 包及依赖
pytest tests/           # 验证环境:42 项测试应全部通过
```

Phase 1 依赖(见 `requirements.txt`):numpy、scipy、matplotlib、pytest。
核心包保持纯 numpy;PyTorch 是 **可选依赖**(仅 `padpd.nn` 需要):

```bash
# 标准安装(CPU 版,推荐)
pip install torch --index-url https://download.pytorch.org/whl/cpu
# 或 GPU 环境直接 pip install torch
# 若网络策略屏蔽 download.pytorch.org(只有 PyPI 可达),PyPI 的 Linux
# 轮子是 CUDA 版,需完整安装其 nvidia 依赖(约 3 GB,纯 CPU 也能跑):
pip install torch
```

无 torch 时 `padpd` 其余功能与全部经典测试不受影响(`tests/test_nn.py`
自动跳过)。

## 2. GPU 训练环境(Phase 2 起)

| 项目 | 建议 |
|------|------|
| GPU | ≥ 1 张 24 GB 显存(RTX 4090 / A5000 / A100);GRU/LSTM 训练单卡足够 |
| CUDA | 与 PyTorch 官方轮子匹配的版本(pytorch.org 查询) |
| 框架 | `pip install torch`(Phase 2);导出用 `onnx`、`onnxruntime` |
| 数据存储 | 10M~100M 复数样本(每样本 16 B),单数据集 0.2~2 GB,NVMe SSD |

## 3. 开源代码与用途

| 仓库 | 用途 | 引入时机 |
|------|------|---------|
| [OpenDPD](https://github.com/lab-emi/OpenDPD) | 神经 PA 建模/DPD 参考实现(GRU/DGRU)、公开 DPA 测量数据集 | Phase 2 对标 |
| [PyTorch](https://github.com/pytorch/pytorch) | 神经模型训练 | Phase 2 |
| [scikit-rf](https://github.com/scikit-rf/scikit-rf) | S 参数/网络分析(与 PA 设计组交接) | 按需 |
| [GNU Radio](https://github.com/gnuradio/gnuradio) | 实时 DSP 原型、SDR 台架验证 | Phase 3 |

## 4. 数据集

1. **合成数据(当前)**:`python scripts/generate_dataset.py` —— OFDM 波形
   过虚拟 `ReferencePA`,输出 `.npz`(`IQDataset` 格式)。
2. **OpenDPD 公开数据**(已接入):4 套实测 PA 数据集(DPA_160MHz、
   DPA_200MHz、APA_200MHz、APA_200MHz_b,共 55 MB,已预对齐、预切分)。
   `git clone --depth 1 https://github.com/lab-emi/OpenDPD.git` 后用
   `padpd.data.load_opendpd_dataset` 加载(自动解析 spec.json),
   `scripts/run_opendpd_baseline.py` 一键复现经典 baseline。
3. **Cadence Envelope 仿真数据(目标)**:见下节导出流程,用
   `padpd.data.load_cadence_csv` 加载。

## 5. Cadence Spectre / ADS 数据接口

### 5.1 Spectre Envelope 仿真导出流程

1. 测试激励:用本框架生成基带 IQ(`generate_dataset.py` 保存的 `.npz`
   中 `x` 即 PA 输入),或 MATLAB WLAN Toolbox 生成 802.11be 波形;
   通过 PWL/端口文件送入 envelope 仿真的调制源。
2. 仿真:Spectre Envelope(`envlp`)分析,载频设为信道中心,
   envelope 输出带宽 ≥ 4× 信道带宽(与波形过采样一致)。
3. 导出:在 ViVA/OCEAN 中把输入、输出包络的实部/虚部导成一个 CSV,
   列名:`time, i_in, q_in, i_out, q_out`(精确规范见
   `02_data_interface.md`)。
4. 加载:`padpd.data.load_cadence_csv("env.csv")` → `IQDataset`,
   采样率自动从 time 列推断。

### 5.2 ADS

Envelope 仿真同理;导出 dataset 为 CSV(相同列名)即可复用同一加载器。

### 5.3 MATLAB 交接

MATLAB 侧保存 `save('cap.mat','x','y','fs')`(复数列向量 + 标量采样率),
Python 侧 `padpd.data.load_matlab_mat("cap.mat")` 加载。

## 6. Python 自动化脚本框架(本仓库)

```
scripts/generate_dataset.py   # 波形生成 + (虚拟)PA → 数据集
scripts/run_baseline_demo.py  # 建模 + DPD + 指标 + 图,一键复现 baseline
src/padpd/                    # 可编程 API,所有脚本均基于它
tests/                        # 回归测试,改动后必须全绿
```

典型 API 用法:

```python
from padpd.waveform import OFDMConfig, generate_ofdm
from padpd.pa import GMPModel, ReferencePA
from padpd.dpd import ILAPredistorter
from padpd.metrics import evm_of_signal, aclr

wf = generate_ofdm(OFDMConfig(bandwidth_hz=320e6, qam_order=4096))
pa = ReferencePA()                      # 将来替换为真实数据回放
dpd = ILAPredistorter().fit(pa, wf.x)
print(evm_of_signal(dpd.linearize(pa, wf.x), wf))
```

## 7. EDA 软件(PA 设计组,本仓库不管理)

Cadence Virtuoso/Spectre RF(主)、Keysight ADS、AWR;PDK 按项目工艺
(CMOS/SOI)由 IT 统一部署。本仓库只约定数据交换格式。
