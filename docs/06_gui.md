# 06 · 图形界面(桌面工作台 + 共享界面契约)

通过 GUI 即可使用全部功能:波形生成、数据接入、PA 建模、DPD、定点部署
导出、专题实验(增益调制、自适应跟踪、前端三环、联合设计、双音诊断)与
结果比较。前端有两个:PySide6 桌面工作台(`gui_qt/`,可打包 exe)与
Android 应用(`android/`,见其 README)。两者共享 `gui_core/`。

```bash
pip install -e .[gui-qt]     # pyside6 + pyqtgraph + markdown
python -m gui_qt.main
```

> **Web 版已退役(2026-10-28)。** Streamlit 工作台(`gui/`)与桌面版
> 各自手写九个页面,逐渐分叉:同一个 DPD 页桌面 21 个输入、Web 12 个,
> 缺的还不是同一批。改成"一套界面契约、多个渲染器"之后,第二个手写前端
> 只剩成本。`pip install -e .[gui]` 保留为桌面依赖的别名。

## 分层

```
gui_core/                    # 纯 Python,不 import 任何 GUI
  services.py   # 计算:波形、数据加载、建模、DPD、部署、各专题实验
  screens.py    # 每个界面的呈现:present_<name>(result, lang) -> 指标卡、
                #   图表规格、说明;Android 直接调用屏幕函数
  chart_spec.py # 每张图的规格(纯 JSON + float32 数组),两个渲染器共用
  experiments.py# 工作台契约:参数 schema、run/present 拆分、对 spec 的
                #   判定、运行记录;execute() 是所有前端与测试的唯一入口
  workspace.py  # 工作区:数据源(以引用保存)、已拟合模型(带来源)、
                #   项目 spec;持久化到用户数据目录
  runstore.py   # 运行记录 gui_runs/*.json
  i18n.py / prefs.py / manual.py
gui_qt/
  main.py            # 窗口:左侧工作流导航、顶栏上下文、懒加载页面栈
  experiment_page.py # 一个模板渲染全部实验:参数 | 判定卡、指标、图、表、来源
  form.py            # 由 Param schema 生成参数表单
  chartview.py       # pyqtgraph 渲染 chart_spec
  pages.py           # 非实验页:总览、数据源、结果比较、手册、模型面板
  theme.py           # 主题 token:QSS、QPalette 与图表配色同源
  common.py          # 偏好、工作区单例、FnWorker
```

新增一个实验:在 `experiments.py` 写 `run`、`present`(必要时 `record`、
`after`)与 `params`,注册进 `EXPERIMENTS`,在 `gui_qt/main.py` 的 `RAIL`
里加一行。表单、判定卡、图、来源、过期提示、语言切换都不用写。

## 契约保证的三件事

1. **结果和输入绑在一起。** 运行后改参数或切数据源,结果上方出现过期
   提示,而不是冒充当前结果;"复现"把参数填回。每个结果显示 run 编号、
   参数、数据源与用时。被 `show` 谓词隐藏的输入由 `effective_values()`
   剔除,不进入运行,也不写进记录。
2. **通过与否由 spec 判定,不由页面判定。** 判定(数值、限值、余量、
   通过、对照组)在 `experiments.py` 里算一次;页面只渲染。改 spec 后
   `present()` 按新限值重判已有结果,不重跑。
3. **语言、主题原地切换。** `run` 昂贵且与语言无关,`present` 便宜且依赖
   语言;切换时只重新 `present`,结果不丢(旧桌面版重建页面、清空结果)。

发射 Mask 余量由 `experiments.mask_margin_db()` 只在模板第一个拐点以外
计算:`check_mask` 把 PSD 按带内峰值归一化,带内恰好贴在模板 0 dB 上,
对任何信号都报 0.0 dB。默认 DPD 运行实际余量 +18.7 dB。

## 工作区与持久化

用户数据目录(源码运行时为仓库根目录;打包版为 `%APPDATA%\padpd` /
`~/.local/share/padpd`)下:

- `workspace/workspace.json`:数据源引用(合成参数,或文件路径 + 加载器
  + 是否对齐)、当前数据源、项目 spec、模型条目(类型、配置、数据源、
  指标、run 编号、文件);`workspace/models/` 存模型本体(各自的
  `save()`,经典 `.npz`、神经 `.pt`)。保存失败的模型只在本次会话可用,
  并明确标注"仅本次会话"。
- `gui_runs/`:运行记录;`gui_prefs.json`:语言与主题。

## 界面

- **左侧导航**按工作流:波形 → 数据源 → PA 模型 → DPD → 部署,然后是
  专题实验与分析。
- **顶栏**:当前数据源(可切换)、模型数(菜单列出模型)、项目 Spec
  (点击编辑);右侧语言与主题。
- **实验页**:左栏 296 px 参数表单;右栏依次为过期提示、判定卡、辅助
  指标、图(悬停读数、框选放大、双击复原;右轴量放到共享 x 轴的下方小图,
  不做双 y 轴)、前后对比表、说明、来源与操作。
- **结果比较**只比同一类运行,并列出取值不同的参数。
- 所有页面在 1280 px 宽、中英文下都放得下(测试强制)。旧版建模页需要
  1730 px(中)/ 1930 px(英)。

## 测试

- `tests/test_experiments.py`:schema 字符串都有英文、隐藏输入不进运行、
  判定随 spec 变化、跨语言重新呈现、每张图都能构建、模型重启后仍在并能
  用于部署扫描。
- `tests/test_gui_qt.py`(offscreen):每页在 1280 px 中英文下不撑宽窗口、
  不横向溢出、英文界面无中文残留;改 spec 重判、过期提示、原地切换语言
  与主题、模型进入选择器、同类比较与参数差异、数据源页。
- 截图:`scripts/make_gui_screenshots.py` 驱动真实窗口重新生成
  `manual/assets/qt_*.png`。

## Qt 侧的坑

- **PySide6 6.12.0 + Python 3.11:每次 `Signal.emit()` 少一个 `True`
  引用。** Python 3.12 起 `True` 是 immortal 对象,无影响;3.11 上
  `True` 的引用计数约两千,pyqtgraph 每次重绘发一次信号,在图上晃几分钟
  鼠标进程就以 `bool_dealloc` 中止。实测 6.12.0 每次 -1.0,6.11.3 为 0。
  `pyproject.toml` 对 Python < 3.12 限定 `pyside6<6.12`,
  `test_signal_emit_does_not_leak_true` 守护。
- 任何作用于 `QSpinBox` 的样式表都会让 Fusion 不再画步进箭头;改用
  `NoButtons` 又会把编辑区压成 1 px(6.12 实测)。箭头用 SVG 图片补回
  (`theme._chevron`)。
- pyqtgraph 会丢掉正好落在坐标范围边缘的类别刻度标签(位宽图的 W16);
  有 `x_ticks` 时 x 范围两侧各留半格。
- 退出时先删除窗口再结束解释器:留给解释器收尾的 pyqtgraph 控件按 GC
  顺序析构,可能段错误。
- 耗时操作走 `FnWorker`,控件值在 GUI 线程快照后再传入;关闭窗口时若有
  任务在跑会先确认。

## 打包成 Windows exe

见 `packaging/README_packaging.md`。推荐 GitHub Actions 云端构建
(Actions → Build Windows EXE,slim/full 双变体,推 `v*` tag 自动出
Release)。pyqtgraph 由 PyInstaller 的 contrib hook 收集;
`examples`/`opengl`/`jupyter` 子包排除。

## 已知边界

- 神经训练在 GUI 里默认小参数,论文级结果请用 `scripts/train_neural_pa.py`
  等命令行脚本。
- DLA 与可微联合寻优需要 PyTorch;未安装时选项下方直接提示,可微联合寻优
  页不出现。
- 实验的取消尚未实现:运行中的任务只能等它结束(关闭窗口会先确认)。
