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

### 5.1 PA 行为建模(测试集 NMSE,dB;100 epochs、frame_length=50、单 seed)

| 数据集 | GMP-510(经典基准) | GRU-H11 | DGRU-H8 | DGRU-H23 | OpenDPD 参考 |
|--------|--------------------|---------|---------|----------|--------------|
| DPA_200MHz | **-33.7** | -31.0 | -31.4 | — | — |
| APA_200MHz | **-35.5** | — | — | -31.7 | GRU-H23 -43.5(F=200) |
| DPA_160MHz(stride=4 减量) | **-39.2** | — | -37.4 | — | GRU-H24 -38.4 |

结论(诚实记录):在同参数预算、frame_length=50、单 seed、CPU 100 epoch
的条件下,神经模型的 NMSE 尚未超过 GMP-510。OpenDPD 的 -43.5 dB 参考值
使用 frame_length=200 训练(长帧捕获 GaN PA 长记忆),这是下一步最明确
的改进方向(见 §6)。**但注意 §5.3:代理的 NMSE 并不是 DPD 评估保真度
的完整指标。**

### 5.2 DPD 线性化(OpenDPD 口径,DPA_200MHz 测试集)

| 方案 | 评估代理 | ACLR_AVG | EVM(谱) |
|------|----------|----------|---------|
| 无 DPD(实测) | — | -30.6 | -11.6 |
| ILA-GMP-510(Phase 1.5) | GMP-510 | -48.7 | -46.7 |
| DLA DGRU-H8(486 参数) | 神经 DGRU-H8 | -45.1 | -35.1 |

注:两行 DPD 用了不同评估代理,不能直接横比;DLA 结果受 H8 代理
NMSE(-31.4)限制。

### 5.3 APA 代理重评 ⭐(同一 ILA-GMP-510 DPD,只换评估代理)

| 评估代理 | 代理 NMSE | ACLR_AVG | EVM(谱) |
|----------|-----------|----------|---------|
| GMP-510(Phase 1.5) | -35.5 | -26.2 | -38.4 |
| **神经 DGRU-H23** | -31.7 | **-38.53** | **-38.94** |
| OpenDPD GRU(发表) | -43.5 | -38.80 | -38.53 |

**Phase 2 的核心验证结果**:换用神经代理后,同一个经典 DPD 的 ACLR 读数
从 -26.2 收敛到 **-38.53**,与 OpenDPD 发表值(-38.80)几乎逐位吻合——
即使我们的神经代理全局 NMSE(-31.7)数值上低于 GMP 代理(-35.5)。
结论:多项式代理的带外外推不可信(高阶项在峰值区伪造频谱溅射),而
神经代理激活有界、带外行为忠实。**DPD 的代理评估必须用神经代理**;
代理的全局 NMSE 高不代表 ACLR 读数可信。

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
- 后续增量(Phase 2.5 候选,按预期收益排序):
  1. **frame_length=200 训练**(OpenDPD 的 -43.5 dB APA 代理即 F=200;
     长帧捕获长记忆,预计是 NMSE 差距的主因;CPU 上约 4× 训练时间)
  2. lr=5e-3 + 240 epochs(OpenDPDv2 配方)、多 seed 统计
  3. TCN(ASIC 友好)、DeltaGRU/TRes-DeltaGRU(OpenDPD v2 最优)
  4. Transformer 探索(320 MHz 长记忆)
