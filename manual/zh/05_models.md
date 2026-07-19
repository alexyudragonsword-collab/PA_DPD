# 5. 模型与算法速览

面向使用者的最小必要背景:每个模型/算法是什么、何时选它。推导与
实现细节见 `docs/00_overview.md` 与 `docs/04_neural.md`。

## 5.1 经典 PA 行为模型(LS 闭式解)

| 模型 | 特点 | 适用 |
|---|---|---|
| Saleh | 无记忆 AM-AM/AM-PM 解析式 | 教学、粗略仿真 |
| Memory Polynomial (MP) | 对角 Volterra,阶数×记忆 | 快速基线 |
| GMP | MP + 交叉滞后/超前项 | **黄金基线**,精度/成本均衡 |
| DDR-Volterra | 动态偏差约减,r 阶截断 | **DPD 基函数首选**(见 5.4) |

三个 OpenDPD 对标 preset:MP-500、GMP-510、DDR-140(数字为实参数量)。

**重要**:这类线性参数模型必须用最小二乘闭式解拟合,不要用 SGD——
同一 GMP 用 SGD 训练 ACLR 差 9 dB 以上(OpenDPD 与本工程双重实证)。
GUI 的"经典 (LS)"路径即闭式解。

![经典建模:实测 vs 预测 PSD](assets/qt_modeling.png)

## 5.2 神经 PA 模型(SGD 训练)

| backbone | 结构 | 特点 |
|---|---|---|
| GRU | 原始 IQ 序列输入 | 基线 RNN |
| DGRU | 6 通道特征(I,Q,幅度,幅度³,sin,cos)+ 前馈旁路 | OpenDPD 主力结构 |
| TCN | 逐点卷积 + 4 层空洞深度卷积(d=1/2/4/8) | 无递归,**定点/ASIC 最友好** |

实测数据上 TCN-H16(464 参数)NMSE -34.9 dB,首次超过 GMP-510 经典
基线;且量化鲁棒性远超多项式(见第 6 章)。

## 5.3 DPD 两条路线

- **ILA(间接学习)**:辨识 PA 的后逆(以 `y/G` 为输入、`x` 为目标做
  LS),把后逆搬到前级。经典、秒级、无需 torch。合成源可闭环迭代;
  实测数据用数据驱动版(`fit_measured`)。
- **DLA(直接学习)**:预失真器(神经)与**冻结的神经 PA 代理**级联,
  以 `G·x` 为目标端到端梯度训练。需要先拟合神经代理,但在真实 PA
  (多项式失效的 GaN 等)上显著更强。

![DPD 前后 PSD 与星座对比](assets/qt_dpd.png)

## 5.4 三条经过实证的选型法则

1. **DPD 评估必须用神经代理**:多项式代理带外外推失真,ACLR 读数可差
   12 dB(APA 实测);全局 NMSE 高不代表 ACLR 可信。
2. **建模准 ≠ DPD 好**:DDR 正向建模只追平 GMP,但作 DPD 基函数用
   55% 参数全面超越(GaN 上领先 8.5 dB)。选基函数直接评 DPD 后指标。
3. **深压缩工作点先 CFR**:峰值进入 PA 不可逆区时 DPD 发散;CFR 用
   有界的 EVM 代价(削峰)换回可逆性,"CFR + DPD"才能 Mask PASS。

## 5.5 指标口径

| 口径 | 指标 | 用途 |
|---|---|---|
| padpd 原生 | 星座域 EVM(解调后)、802.11 风格 ACLR、发射 Mask | 工程验收 |
| OpenDPD 兼容 | 谱域 EVM、ACLR_AVG(nperseg 分段 Welch) | 与论文横向对标 |

两套口径数值**不可混比**;GUI 按数据源自动选择并在结果中标注。

## 5.6 流片前:从电路仿真到 PA+DPD 预判

PA 还没流片时,电路仿真已能提供初步建模所需的一切:

| 仿真 | 提取 | 用途 |
|---|---|---|
| 谐波平衡扫功率 | AM-AM/AM-PM 表 | 静态非线性 |
| S 参数 / PSS+PAC | 输入/输出匹配 S21 | 线性记忆(FIR) |
| 包络瞬态 | 输入/输出 IQ 对 | 直接按第 4 章 Cadence CSV 导入 |

`padpd.pa.load_hb_pa` 把 AM-AM/AM-PM 表 + S21 表装配成
Wiener-Hammerstein 模型(FIR → 查表非线性 → FIR,超表输入饱和):

```python
from padpd.pa import load_hb_pa
pa = load_hb_pa("hb_amam.csv", "s21_in.csv", "s21_out.csv",
                fs=320e6, drive=0.14)   # 标准 PAModel,即插即用
```

`scripts/import_hb_pa.py --demo` 生成示例 CSV 并跑通完整预测链——
demo 结果:GMP 拟合导入 PA 达 NMSE -43.7 dB;DPD 预测 EVM
-18.3 → **-48.1 dB**、Mask FAIL → PASS。扫 `--drive`(配合 CFR 与
联合设计)即可在流片前回答:**这颗 PA 配多大 DPD、退多少功率能过
spec**。建议同时做鲁棒性扫描(非线性强度/记忆深度扰动 ±20%)确认
结论不翻转。CSV 列约定见 `docs/02_data_interface.md` 第 8 节。

## 5.7 自适应/在线 DPD 与现场漂移

批处理 DPD 一次性辨识;产品形态需要从环回持续自适应以跟踪 PA 漂移
(温度/供电/老化)。`padpd.dpd.AdaptiveDPD` 用块 RLS 在 GMP/DDR 基上
递归更新:

```python
from padpd.dpd import AdaptiveDPD
dpd = AdaptiveDPD(forget=0.6)      # forget 越小跟踪越快、越噪
dpd.warm_start(pa, x, blocks=6)    # 从直通收敛
dpd.update(pa, x)                  # 每块从环回观测更新
```

**只提供 RLS**:多项式基条件数约 1e10,LMS/NLMS(即便白化)会发散
——"线性参数模型必须用 LS 而非 SGD"在在线场景的翻版。

`scripts/run_drift_study.py` 量化现场价值:PA 冷→热漂移中,冻结批处理
DPD 退化到 **-28.4 dB EVM**,自适应保持 **-38.8 dB**(满漂移领先
10.4 dB)。这回答了"DPD 在现场能不能扛住"。

## 5.8 双音记忆诊断:用两音扫间距预判 DPD 该留多少资源

单音 AM-AM/AM-PM 只给**静态**非线性,看不见记忆:同一条静态曲线既能
拟合无记忆 PA,也能拟合强动态 PA。而**双音扫音间距(delta-f)**恰好是
流片前电路仿真最容易给的大信号表征(谐波平衡跑几个音间距的 IM3),
所以它是从 Spectre 到"DPD 该多复杂"的天然桥梁。

思路不是逼双音交出完整记忆核,而是**用多个 delta-f 的 IM3 粗判记忆
强度**,据此决定 DPD 要预留多少记忆,再把系数训练交给实测数据。
`padpd.two_tone` 从 IM3 读两种正交的记忆信号:

- **随间距变化**(spacing spread):扫音间距即扫包络频率;IM3 随间距
  变化就说明有记忆(MHz 级间距 = 偏置/匹配电记忆,kHz 级 = 热记忆)。
  无记忆非线性的 IM3 与间距无关。
- **上下不对称**(asymmetry):无记忆非线性上下 IM3 严格相等;任何
  不对称都是记忆(复数/交叉项)信号,且向小间距增大指向热记忆。

两者取较大者浓缩为标量**记忆强度(dB)**——大致等于"静态模型无法
复现的那部分 IM3 有多少 dB"。`recommend_dpd_budget` 把它映射到粗略
DPD 规模:留多深的对角记忆、要不要 GMP 交叉项。

```python
from padpd.two_tone import sweep_two_tone, recommend_dpd_budget
r = sweep_two_tone(pa, [0.5e6,1e6,2e6,5e6,10e6,20e6,40e6], fs=320e6)
b = recommend_dpd_budget(r)          # {'memory_depth':3,'use_cross_terms':True,...}
# 电路双音仿真结果也能直接喂:
from padpd.two_tone import memory_strength_from_table
r = memory_strength_from_table(spacings, im3_lower_dbc, im3_upper_dbc)
```

**GUI 入口**:数据管理页"〰️ 双音记忆诊断"标签可直接"载入示例"或上传
你的双音 IM3 表 CSV,即时看到记忆强度、建议记忆深度/交叉项/估算系数量、
IM3-音间距曲线与热记忆判断(示例
`examples/two_tone_example.csv` → 记忆强度 8.5 dB、深度 5、需交叉项、
疑似热记忆)。

`scripts/run_two_tone_study.py` 做了闭环验证:无记忆 Saleh 读出记忆
强度 **0.0 dB**(留 depth 1),强色散 PA 读出 **3.0 dB**(留 depth 3
+ 交叉项)。在强 PA 上用真实 802.11 信号扫 ILA-GMP 记忆深度,EVM 拐点
正好落在双音预判的 depth 3:无记忆 DPD 只到 -19.7 dB,depth 2/3 拿到
-27.9/-36.1 dB 的大头,再加深(depth 4/6 → -39.9/-41.5)收益递减。
即**流片前用便宜的双音就把 DPD 记忆量级定下来**,系数留给实测训练。
