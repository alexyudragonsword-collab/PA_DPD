# CLAUDE.md

给 AI 会话的操作性约束。人类贡献者请看 `CONTRIBUTING.md`(装环境、
提 PR、代码风格),这里只写**每次动手都要照做的事**与**已经踩过的坑**。

## 开工前

- 容器可能在会话中途被回收,工作区会**静默退回旧提交**。任何一轮开始
  前(尤其是发现文件"消失"或 `git log` 对不上时),先:
  `git fetch origin <branch> && git reset --hard origin/<branch>`。
  本会话因此吃过五次亏,已推送的工作从未真正丢失。
- 代码与注释一律**英文**;`docs/`、`manual/zh/` 中文,`manual/en/` 是
  其英文版——**两边必须同批改**。

## 验证:声称完成前必须跑

```bash
# 快车道(约 4 分钟,日常改动的门槛)
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -m "not slow" -q

# 改了神经/训练/ONNX 路径时再跑全量
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
```

没跑过就不要说"完成"。测试失败要如实报,不要淡化。

## 不要动的东西(都是修复,不是冗余)

- `tests/conftest.py` 的 `OMP_NUM_THREADS=1` 与 pandas 预导入 —— 分别
  绕开 libgomp 屏障死锁与导入顺序死锁;
- `tests/test_gui_qt.py` fixture 里的 `deleteLater()` + `processEvents()`
  + `gc.collect()` —— Qt widget 析构函数若被 GC 到 streamlit 的
  ScriptRunner 线程上执行会**永久挂起整个 pytest 进程**。新增 Qt 测试
  沿用这套 fixture,不要自己造;
- docstring 里的**失败记录与设计理由**(C-IM3 五种抵消架构为什么都不行、
  ~-35 dB 结构天花板怎么证的、状态模型的冷启动约定)——这些是资产。

## 写代码时

- 注释写**为什么**,不写是什么;负结果照写("这条路不通,因为 X"),
  不要悄悄删。
- 数值断言写**实测值并注明来源**:`assert gain > 6.0   # measured +10.5`。
- 线性参数模型**必须用 LS 闭式解**,不要用 SGD(同一 GMP 用 SGD 训
  ACLR 差 9 dB 以上,双重实证过)。
- 新增中文 UI 串**必须**在 `gui_core/i18n.py` 补英文——
  `tests/test_gui_i18n.py` 会 AST 扫描所有 `tr()` 调用,漏了直接红。
- Qt 侧耗时操作走 `FnWorker`,并**在 GUI 线程上快照控件值**再传进闭包
  (worker 线程里访问 QWidget 不安全)。
- 服务层函数放 `gui_core/services.py`(纯 Python,不 import GUI),
  两个 GUI 各接一次。

## 改数字/文档时

- 性能数字改动要**三处同步**:`README.md`、`docs/05_performance_summary.md`、
  `manual/zh|en`。`tests/test_docs_site.py` 会检查 README 提到的每个
  Phase 在 `docs/03_roadmap.md` 里存在(路线图曾落后两个阶段);
- 改了手册跑 `pytest tests/test_manual.py`;改了 mkdocs 配置或 API 页跑
  `pytest tests/test_docs_site.py`。

## 已知陷阱清单

- **`np.allclose` 的默认 `atol=1e-8`**:检查时间列均匀性时,1e-8 秒在
  100 MHz 以上比采样周期还大,抖动的导出会被静默放行。写成 `atol=0.0`。
- **首采冻结类校准的电平次序**:`ThermalReferencePA` 的耗散功率参考、
  `LoopbackChannel(rx_im3_freeze=True)` 的 κ 都在**第一次调用**冻结。
  标定采集必须在**标称工作电平**先做,回退采集排第一会把参考冻错两个
  量级。表征探针与建模采集要各用新建的 DUT 实例。
- **CI 矩阵与 `test-full` 的依赖集不同**:快车道装 torch 但**不装
  onnx**。不要假设可选依赖存在,该 `pytest.importorskip` 就写上(一个
  ONNX 测试曾在开发机长期通过、云端长期红)。
- **状态模型的评估约定**:单采集切分后,验证尾段带着前段的热历史,必须
  **全信号预测、尾段打分**,否则 +10 dB 的收益会缩水成 +1。
- **相位谐波不可互相表示**:e^{+jφ}(主)、e^{-jφ}(镜像)、e^{-j3φ}
  (C-IM3)各需专用分支。加新损伤前先判断它属于哪一类;若发生在 PA
  之前,大概率有精确预逆(参考 QMC),不必挤进 DPD 基。

## 提交

- 提交信息写清**为什么**与实测数字;修 bug 写清根因,不写 "fix test"。
- 只推送到指定分支;未获明确许可不要推 main、不要打 tag、不要开 PR。
