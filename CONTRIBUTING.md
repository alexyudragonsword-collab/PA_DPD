# 参与开发

面向要改这个仓库的人:怎么装、怎么跑测试、CI 卡什么、代码与文档的
约定,以及加一个新模型/新环时的检查清单。

## 1. 开发环境

```bash
git clone https://github.com/alexyudragonsword-collab/PA_DPD.git
cd PA_DPD
python -m venv .venv && source .venv/bin/activate    # 3.10+
pip install -e ".[dev]"                              # 核心 + pytest
```

按需追加 extras(彼此独立,不装也不会 import 失败——相关测试会 skip):

| extra | 内容 | 解锁 |
|---|---|---|
| `dev` | pytest | 测试 |
| `nn` | torch | 神经建模、DLA、直接学习 |
| `onnx` | onnx + onnxruntime | ONNX 交接与数值验证 |
| `gui` | streamlit + plotly | Web 工作台 |
| `gui-qt` | pyside6 + markdown | 桌面版 |
| `packaging` | pyinstaller + nuitka | exe 打包 |

RTL 测试另需系统级 `iverilog`(`apt install iverilog`);缺了对应测试
会 skip 而不是失败。

## 2. 跑测试

```bash
# 快车道:日常改动跑这个(约 2-3 分钟)
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -m "not slow" -q

# 全量:含长训练,提交前或改了神经/训练路径时跑
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
```

两个环境变量的由来,都是踩出来的:

- **`QT_QPA_PLATFORM=offscreen`** 是必需的,无头机器上没有它 Qt 测试
  直接崩;
- 测试套件曾整体**死锁**,`tests/conftest.py` 里的 `OMP_NUM_THREADS=1`
  与 pandas 预导入不要删——前者绕开 libgomp 屏障死锁,后者绕开导入
  顺序问题。真正的根因是 Qt widget 析构函数被 GC 到 streamlit 的
  ScriptRunner 线程上执行,`tests/test_gui_qt.py` 的 fixture 因此显式
  `deleteLater()` + `processEvents()` + `gc.collect()` 拆除,**新增 Qt
  测试请沿用这个 fixture,不要自己造**。

`-m "slow"` 标记留给长训练;新增耗时 >30 s 的测试请打上 `@pytest.mark.slow`。

## 3. CI 门禁

`.github/workflows/ci.yml` 六类 job,PR 必须全绿:

| job | 环境 | 内容 |
|---|---|---|
| `test` 矩阵 | ubuntu 3.10/3.11/3.12 + windows + macos | 快车道 |
| `test-full` | ubuntu | 全量(装 torch + onnx 全家) |
| `test-gui` | ubuntu | `[gui,gui-qt]`,离屏 |
| `test-rtl` | ubuntu + iverilog | RTL 位真验证 |
| `build` | ubuntu | sdist + wheel |
| `test-opendpd` | 需数据集,默认 skip | 实测数据 baseline |

**注意矩阵与 `test-full` 的依赖不同**:快车道装 torch 但不装 onnx。
写测试时不要假设可选依赖存在,该 `pytest.importorskip` 就写上——曾有
一个 ONNX 测试只在开发机(恰好装了 onnx)通过,云端一直红。

`.github/workflows/build-windows.yml` 只在 `packaging/**` 变更或 `v*`
tag 时构建 exe(PyInstaller onedir slim/full + Nuitka onefile)。

## 4. 代码约定

- **代码与注释一律英文**;面向用户的文档(`docs/`、`manual/zh`)中文,
  `manual/en` 是其英文版,两边必须同步改。
- 行宽 79;标准库 → 第三方 → 本地的 import 分组。
- **注释写"为什么",不写"是什么"**。这个仓库的 docstring 里保存了
  大量设计理由与**失败记录**(C-IM3 五种抵消架构为什么都不行、结构
  天花板怎么证的、冷启动约定为什么必须这样评估),这些是资产,改动
  相关代码时请一并维护,不要删。
- 负结果照写。宁可写"这条路走不通,原因是 X",不要悄悄删掉。
- 数值断言写**实测值**并在注释里标出来源,例如
  `assert gain > 6.0   # measured +10.5`,这样阈值退化时看得出来。

### 模型接口

所有 PA/DPD 模型实现 `fit(x, y)` / `__call__(x)`;线性参数模型另实现
`basis_matrix(x)`(才能进 `AdaptiveDPD`)与 `get_config()`(才能持久化
与被调度器复制)。**线性参数模型必须用 LS 闭式解拟合,不要用 SGD**
——同一 GMP 用 SGD 训 ACLR 差 9 dB 以上,这条在 OpenDPD 与本工程双重
实证过。

## 5. 加东西时的检查清单

**新 PA/DPD 模型**:实现接口 → `tests/` 加拟合精度与持久化往返测试 →
若要进 GUI,在 `gui_core/services.py` 的 `CLASSICAL_MODELS` 注册 →
手册 §5 补一段(中英)。

**新损伤机制 / 新环**:先问它属于哪类相位谐波(见
`docs/pages/modeling-blockdiagram.html`)——若现有分支结构上表示不了,
需要新分支;若发生在 PA 之前,大概率有精确预逆(参考 QMC),不必挤进
DPD 基。补测试 + 手册 §5.9 + 性能汇总 §3.7。

**新 GUI 面板**:服务层函数放 `gui_core/services.py`(纯 Python,不 import
GUI),两个 GUI 各接一次,新增中文 UI 串**必须**在 `gui_core/i18n.py`
加英文——`tests/test_gui_i18n.py` 会 AST 扫描所有 `tr()` 调用,漏了直接
红。Qt 侧耗时操作走 `FnWorker`,并在 GUI 线程上快照控件值再传进闭包
(worker 线程里访问 QWidget 不安全)。

## 6. 提交与 PR

- 提交信息写清**为什么**与实测数字;修 bug 时写清根因(不是"fix test")。
- 一个提交一件事;文档与代码同批改。
- 提 PR 前:快车道全绿 + 改了文档就跑 `pytest tests/test_manual.py`。
- 改了性能数字,同步 `docs/05_performance_summary.md`、`README.md`、
  手册三处(目前靠人工,数字必须一致)。

## 7. 目录速查

```
src/padpd/     核心库(英文代码/注释)
gui_core/      两个 GUI 共享的服务层与 i18n(框架无关)
gui/           Streamlit Web 工作台      gui_qt/  PySide6 桌面版
docs/          工程文档(中文) + pages/ 三页速览 HTML
manual/        内置双语用户手册(zh/en 各 8 章 + 截图)
scripts/       研究脚本与数据打包工具
examples/      可直接载入的输入范例
tests/         pytest(含与 OpenDPD 原版指标的数值等价测试)
```
