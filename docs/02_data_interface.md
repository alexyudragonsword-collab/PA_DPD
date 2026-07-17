# 数据接口规范

所有外部数据统一转换为 `padpd.data.IQDataset`(PA 输入 `x`、输出 `y`
两条对齐的复基带序列 + 采样率 + 元信息),下游建模/DPD/指标代码只依赖
这一容器。

## 0. 通用约定

- **复基带 IQ**:所有序列为等效复基带(envelope)信号,不含载波。
- **采样对齐**:`x[n]` 与 `y[n]` 必须是同一时刻的输入/输出。环回/仿真/
  实测数据的固定整数延迟可用 `padpd.data.align_delay(x, y)` 自动估计并
  消除(互相关求延迟 + LS 复增益),见第 5 节。
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

## 3. OpenDPD 数据集(`load_opendpd_dataset`,推荐)

加载一个完整的 OpenDPD 数据集文件夹(https://github.com/lab-emi/OpenDPD),
自动解析 `spec.json` 元数据:

```python
from padpd.data import load_opendpd_dataset
ds = load_opendpd_dataset("/path/to/OpenDPD/datasets/DPA_160MHz")
train, val, test = ds["train"], ds["val"], ds["test"]   # IQDataset ×3
spec = ds["spec"]        # fs、带宽、nperseg 等,同时也在各 split 的 meta 里
```

文件夹格式(两种皆支持):

| 格式 | 文件 | 说明 |
|------|------|------|
| `split_csv` | `{train,val,test}_{input,output}.csv`,各含 `I,Q` 两列 | 预切分、逐样本时间对齐 |
| `single_csv` | `data.csv`,含 `I_in,Q_in,I_out,Q_out` 四列 | 按 `split_ratios`(默认 0.6/0.2/0.2)连续切分 |

`spec.json` 关键字段:`input_signal_fs`(采样率)、`bw_main_ch`、
`bw_sub_ch`、`n_sub_ch`、`nperseg`(OpenDPD 指标分段长度)、
`modulation`;APA 类数据集另有 `scs`、`ofdm_nfft`、`n_active`、CP 参数。
这些字段是计算 OpenDPD 兼容指标(`padpd.metrics.aclr_opendpd` 等)的
必要输入。

低层加载器 `load_opendpd_csv(input_csv, output_csv, sample_rate_hz)`
仍可用于加载单对 CSV(两文件长度不一致时按较短者截断)。

## 4. 内部格式:IQDataset `.npz`(`IQDataset.save/load`)

`numpy.savez_compressed` 存储:`x`、`y`(complex128)、`sample_rate_hz`、
`meta`(字典的 repr 字符串,加载时 `ast.literal_eval` 还原)。
合成数据的 `meta` 记录带宽、QAM 阶数、符号数、过采样率、PA 工作点、种子,
保证可复现。

## 5. 时间对齐工具(`align_delay`)

实测/EDA 数据常有未知整数延迟与复增益。拟合行为模型前先对齐:

```python
from padpd.data import align_delay
x_a, y_a, info = align_delay(x, y, max_lag=4096)
# info = {"lag": 整数延迟(正=y滞后), "lag_total": 含分数部分的总延迟(浮点),
#         "gain": 对齐后 LS 复增益}
```

分数延迟(如 DAC/ADC 时钟相位差)由相关峰抛物线插值自动估计,超过
0.02 采样时用 FFT 相位斜坡校正,无需额外参数。

注意:OpenDPD 数据集已预对齐,无需此步骤;Cadence Envelope 导出与
仪器采集通常需要。

## 6. 数据规模建议

| 用途 | 样本量 |
|------|--------|
| GMP/MP 最小二乘拟合 | ≥ 100k(系数数的 ~2000 倍) |
| 神经模型训练(Phase 2) | 10M~100M |
| 指标评估(EVM/ACLR) | ≥ 10 个 OFDM 符号,与训练集不同种子 |

**训练/验证必须用不同随机种子的波形**(参考
`scripts/run_baseline_demo.py` 的 train/val 划分),避免记忆效应造成的
乐观偏差。
