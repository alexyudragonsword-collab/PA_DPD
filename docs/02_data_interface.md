# 数据接口规范

所有外部数据统一转换为 `padpd.data.IQDataset`(PA 输入 `x`、输出 `y`
两条对齐的复基带序列 + 采样率 + 元信息),下游建模/DPD/指标代码只依赖
这一容器。

## 0. 通用约定

- **复基带 IQ**:所有序列为等效复基带(envelope)信号,不含载波。
- **采样对齐**:`x[n]` 与 `y[n]` 必须是同一时刻的输入/输出(环回/仿真
  中的固定延迟需在导出前对齐;后续版本会提供自动对齐工具)。
- **采样率**:≥ 4× 信道带宽(320 MHz 信道 → ≥ 1.28 GSPS envelope 步长),
  保证 5 阶以内频谱再生可观测。
- **单位**:幅度单位任意(V 或归一化均可),框架内部按需归一化
  (`IQDataset.normalized()`),增益关系保留在 `y/x` 中。

## 1. Cadence Envelope CSV(`load_cadence_csv`)

单个 CSV 文件,带表头,列名不区分大小写:

| 列 | 含义 |
|----|------|
| `time` | 秒,必须均匀采样(容差 1e-6 相对误差),采样率由此推断 |
| `i_in`, `q_in` | PA 输入包络实部/虚部 |
| `i_out`, `q_out` | PA 输出包络实部/虚部 |

示例:

```csv
time,i_in,q_in,i_out,q_out
0.000000000000e+00,0.1234,-0.0567,0.1180,-0.0611
1.562500000000e-09,0.1301,-0.0432,0.1245,-0.0489
```

加载:

```python
from padpd.data import load_cadence_csv
ds = load_cadence_csv("pa_envelope.csv")   # ds.sample_rate_hz 自动推断
```

## 2. MATLAB .mat(`load_matlab_mat`)

| 变量 | 类型 | 含义 |
|------|------|------|
| `x` | 复数向量 | PA 输入 |
| `y` | 复数向量 | PA 输出(与 x 等长对齐) |
| `fs` | 标量 | 采样率 Hz |

变量名可通过 `x_var/y_var/fs_var` 参数改写。MATLAB 侧:
`save('cap.mat','x','y','fs')`(v5/v7 格式;v7.3 需另行支持)。

## 3. OpenDPD 风格 CSV(`load_opendpd_csv`)

输入/输出各一个 CSV,均含 `I,Q` 两列(表头不区分大小写),采样率由调用方
提供:

```python
ds = load_opendpd_csv("train_input.csv", "train_output.csv",
                      sample_rate_hz=800e6)
```

两文件长度不一致时按较短者截断。

## 4. 内部格式:IQDataset `.npz`(`IQDataset.save/load`)

`numpy.savez_compressed` 存储:`x`、`y`(complex128)、`sample_rate_hz`、
`meta`(字典的 repr 字符串,加载时 `ast.literal_eval` 还原)。
合成数据的 `meta` 记录带宽、QAM 阶数、符号数、过采样率、PA 工作点、种子,
保证可复现。

## 5. 数据规模建议

| 用途 | 样本量 |
|------|--------|
| GMP/MP 最小二乘拟合 | ≥ 100k(系数数的 ~2000 倍) |
| 神经模型训练(Phase 2) | 10M~100M |
| 指标评估(EVM/ACLR) | ≥ 10 个 OFDM 符号,与训练集不同种子 |

**训练/验证必须用不同随机种子的波形**(参考
`scripts/run_baseline_demo.py` 的 train/val 划分),避免记忆效应造成的
乐观偏差。
