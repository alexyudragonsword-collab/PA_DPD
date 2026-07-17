# Phase 2:神经 PA 建模与 Neural DPD

对标 OpenDPD(结构、训练配方、评估协议逐行对齐),接口对齐 padpd
(1-D 复数序列 in/out,与经典模型可互换)。torch 为可选依赖:
`pip install -e .[nn]`(纯 CPU:`pip install torch --index-url
https://download.pytorch.org/whl/cpu`)。

## 1. 模型结构(`padpd.nn.backbones`)

- **GRU**:`nn.GRU(input=2, H)` → `Linear(H→2)`;输入原始 I/Q。
- **DGRU**(OpenDPD v1 最优):forward 内构造 6 通道特征
  `[I, Q, |x|, |x|³, sin φ, cos φ]` → `nn.GRU(6, H)` →
  `ReLU(Linear(H→H))` → 与特征拼接 → `Linear(H+6→2)`。
- 隐状态每帧零初始化;正交(hh)/Xavier(ih、输出层)初始化。
- DGRU-H8 ≈ 500 参数(与经典 GMP-510 同预算,公平对比)。

## 2. 训练配方(`padpd.nn.NeuralPAModel`)

OpenDPD 复现配方:滑窗帧(frame_length=50, stride=1)、batch 64、
AdamW lr=1e-3、MSE 整帧、梯度裁剪 200、ReduceLROnPlateau
(factor 0.5, patience 10, min_lr 1e-6, 按验证指标步进)、
best checkpoint 按验证 NMSE 选取。

```python
from padpd.nn import NeuralPAModel
model = NeuralPAModel(backbone="dgru", hidden_size=8)
model.fit(train.x, train.y, val.x, val.y)
y_hat = model(test.x)          # 1-D complex,与 GMP 同型
model.save("pa_dgru_h8.pt")
```

## 3. DLA Neural DPD(`padpd.nn.DLAPredistorter`)

与经典 ILA 的区别:**DLA(直接学习)**冻结可微 PA 模型,把神经 DPD
放在其前,以 `G·x` 为目标(G=峰值幅度比)反传穿透训练;best
checkpoint 按验证 ACLR_AVG(OpenDPD 口径)选取。对不可微 PA
(实测数据/ReferencePA)先拟合神经代理再 DLA——与 OpenDPD 协议一致。

```python
from padpd.nn import DLAPredistorter
dpd = DLAPredistorter(backbone="dgru", hidden_size=8,
                      target_gain=g, aclr_spec={...})
dpd.fit(pa_model, train.x, val.x)
y_lin = pa_model(dpd(test.x))
```

## 4. 复现命令

```bash
# PA 行为建模(真实测量数据)
python scripts/train_neural_pa.py --dataset-dir ../OpenDPD/datasets/DPA_200MHz \
    --backbone dgru --hidden 8 --compare-gmp

# DLA DPD(接上一步的 checkpoint)
python scripts/train_neural_dpd.py --dataset-dir ../OpenDPD/datasets/DPA_200MHz \
    --pa-model models/DPA_200MHz_dgru_h8.pt

# 用神经代理重评 Phase 1.5 的经典 DPD(修 APA 的 ACLR 读数)
python scripts/rerun_apa_surrogate.py --dataset-dir ../OpenDPD/datasets/APA_200MHz \
    --pa-model models/APA_200MHz_dgru_h23.pt

# WiFi 7 合成链路(320 MHz / 4096-QAM)
python scripts/run_wifi7_neural_demo.py
```

## 5. 实测结果

(以下数字为本仓库实际运行输出;训练环境 4 核 CPU。)

### 5.1 PA 行为建模(测试集 NMSE,dB)

| 数据集 | GMP-510(经典基准) | GRU | DGRU | OpenDPD 参考 |
|--------|--------------------|-----|------|--------------|
| DPA_200MHz | -33.7 | TBD | TBD | — |
| APA_200MHz | -35.5 | — | TBD | GRU-H23 -43.5 |
| DPA_160MHz(减量) | -39.2 | — | TBD | GRU-H24 -38.4 |

### 5.2 DPD 线性化(OpenDPD 口径,测试集)

| 数据集 | 无 DPD ACLR | ILA-GMP-510 | DLA DGRU-H8 | OpenDPD 发表 |
|--------|------------|-------------|-------------|--------------|
| DPA_200MHz | -30.6 | -48.7 | TBD | — |

### 5.3 APA 代理重评(同一 ILA-GMP-510 DPD,不同评估代理)

| 评估代理 | 代理 NMSE | ACLR_AVG | EVM(谱) |
|----------|-----------|----------|---------|
| GMP-510(Phase 1.5) | -35.5 | -26.2 | -38.4 |
| 神经 DGRU | TBD | TBD | TBD |
| OpenDPD GRU(发表) | -43.5 | -38.8 | -38.5 |

### 5.4 WiFi 7 合成链路(320 MHz / 4096-QAM,ReferencePA 在环)

| 链路 | 星座 EVM | ACLR | Mask |
|------|----------|------|------|
| 无 DPD | TBD | TBD | TBD |
| ILA-GMP | TBD | TBD | TBD |
| DLA 神经 DPD | TBD | TBD | TBD |

## 6. 经验与注意

- 线性参数模型(MP/GMP)用 LS 闭式解,神经模型才用梯度训练
  (OpenDPD 实证 LS 比 SGD 训练同一 GMP 好 9 dB+ ACLR)。
- 代理评估的读数只在代理 NMSE 之上可信;强非线性 PA(APA/GaN)
  必须用神经代理评估 DPD。
- 后续增量(Phase 2.5 候选):TCN(ASIC 友好)、DeltaGRU/TRes-DeltaGRU
  (OpenDPD v2 最优)、多 seed 统计、Transformer 探索。
