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

## 7. 环回观测通路损伤模型(`padpd.loopback`)

产品形态的 DPD 从 TX→耦合→RX 环回采样自适应,**环回链的损伤会被辨识
"学"进 DPD**(等效把 RX 的逆错误地搬到 TX)。`LoopbackChannel` 可按
dBc/dB 预算注入各项损伤(IQ 失衡/LO 泄漏/CFO/相噪/幅相纹波/RX IM3/
整数+分数延迟与漂移/噪底),`scripts/run_loopback_study.py` 逐项量化
其对 DPD 后指标的代价(80 MHz/1024-QAM,ReferencePA,ILA-GMP,
干净观测基线 EVM -55.1 / ACLR -51.9):

| 环回损伤(单项) | ΔEVM | ΔACLR | 预算启示 |
|---|---|---|---|
| SNR 50 dB | +0.1 | +0.8 | 环回 SNR 目标 ≥50 dB |
| SNR 40 / 30 dB | +4.0 / +13.4 | +4.5 / +9.6 | 40 dB 是底线 |
| IRR 40 / 30 dB | +19.8 / +27.2 | +7.7 / +14.1 | **先做 IQ 校准再开 DPD** |
| RX IM3 -50 / -40 dBc | +3.7 / +10.4 | +0.6 / +3.3 | 比目标 ACLR 好 ~15 dB |
| 纹波 0.5 dB / 2 dB(含群时延) | +11.2 / +23.4 | +5.9 / +16.1 | 需标定均衡 |
| 相噪 1° / 3° rms | +20.5 / +27.1 | +2.6 / +11.0 | 共 LO 设计的价值 |
| 延迟 7.3 采样(对齐后 / 未对齐) | +2.5 / **+52.8** | +3.1 / **+26.1** | 对齐是硬前提 |
| 采集期漂移 0.5 采样 | +21.1 | +12.4 | 周期性重估延迟 |

工程要点(本研究实测踩坑):对齐器会把 PA 自身群时延一并吸收,DPD
随之携带分数超前——**EVM 评估必须做接收机式定时同步**,否则星座上
出现相位斜坡、EVM 卡在 -20 dB 而 ACLR 正常。`align_delay` 现含互谱
相位斜率精化;评估侧参照 `run_loopback_study.evaluate`。

## 8. HB/S 参数导入:流片前 PA+DPD 预判(`padpd.pa.hb_import`)

把谐波平衡与 S 参数仿真结果装配成 Wiener-Hammerstein 行为模型
(FIR → AM-AM/AM-PM 查表 → FIR),流片前即可跑通"建模→DPD→指标"
预测链。CSV 约定:

| 表 | 列 | 来源 |
|---|---|---|
| AM-AM/AM-PM | `r_in,r_out,phase_deg` 或 `pin_dbm,pout_dbm,phase_deg`(50Ω 换算) | HB 扫功率 |
| S21(输入/输出匹配) | `freq_hz,mag_db,phase_deg`(相对载波的基带频率) | S 参数 / PSS+PAC |

```python
from padpd.pa import load_hb_pa
pa = load_hb_pa("hb_amam.csv", "s21_in.csv", "s21_out.csv",
                fs=320e6, drive=0.14)   # 即插即用的 PAModel
```

`scripts/import_hb_pa.py --demo` 生成示例 CSV 并跑完整预测链
(demo 结果:GMP 拟合 NMSE -43.7 dB;DPD 后 EVM -18.3 → -48.1 dB,
Mask FAIL → PASS)。扫 `--drive`(配合 CFR / 联合设计脚本)即可在
流片前回答"这颗 PA 配 DPD 能不能过 spec、退多少功率"。注意:S21
FIR 的整体群时延不计入模型(实测中由对齐消除),仅保留色散。

## 9. 完整实测源容器(`padpd.data.complete`)

单个 `.npz` 承载平台能消费的全部采集。必备 `x`、`y`、`sample_rate_hz`
(普通 IQDataset npz 即退化情形);五个**可选采集组**各解锁一类能力:

| 采集组(数组名) | 内容 | 解锁 |
|---|---|---|
| `burst_x/burst_y` | 高低功率交替突发采集(段长 ≳ 最慢 τ) | `StateConditionedSpline`(平稳采集里慢状态不可观测) |
| `step_x/step_y` | 恒包络阶跃探针录制(`step_probe_drive` 生成发射序列) | `identify_gain_modulation_capture` 离线辨识 τ → `state_alphas` |
| `cal_rx_ref/cal_rx_obs` | 旁路 PA 标定采集(已知信号只过观测 RX) | `calibrate_rx_path`(RX WL + 逆 FIR) |
| `atten_ref/atten_hi/atten_lo/atten_step_db` | 同一驱动、RX 衰减步进两采集 | `calibrate_rx_im3`(分离 RX 立方 κ) |
| `op_conditions` + `op{i}_x/op{i}_y` | 每工况点一组 (x,y) + 工况标量 | `CoefficientScheduler` |

`meta` 建议记录:参考平面、中心频率、绝对功率标定、TX/RX 是否共本振。
API:`save_complete_npz` / `load_complete_npz` / `extras_summary`;
services 侧一键消费 `consume_source_extras`。示例文件
`examples/complete_source_demo.npz`(由
`scripts/make_complete_source_demo.py` 生成,含全部五组)在虚拟 DUT
真值下验证:离线 τ 辨识 5.1/29.6 µs(真值 5/30)、状态样条 +8.5 dB、
RX-IM3 估计 -28.8 dBc(配置 -28)、IRR 30.2 dB(真值 30.1)。GUI 数据
页载入 npz 后显示采集组清单并可"运行完整源工具"。
