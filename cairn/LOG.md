# Project Cairn 日志

本文件按倒序记录实质进展——最新条目紧跟本行之下。每条保持简短,只写摘要
与指针;结论沉淀进 `cairn/<topic>.md`。

## 2026-08-23 · Android CI 全绿;一个查了七轮的假产品 bug

- Android workflow 三个 job 全绿:26 条 JVM 单元测试 + 7 条设备测试
  (`PyBridgeTest` 14 规格构建/传输、`ChartRenderTest` 14 规格绘制、
  `GalleryScreenTest` 启动→点开→出图)。
- **根因是测试查错了树**:`Modifier.clickable` 隐含 `mergeDescendants`,把子树
  并成一个语义节点;`onNodeWithTag` 默认查合并树,于是行内的 `chart:` /
  `pending:` / `error:` 标签**一个都查不到**。失败信息完全像"点了没反应",
  连烧几轮去查点击分发、协程、状态传播——查的全是好代码。
- **教训:定位要看该出现而没出现的东西**。真正的线索是每行都会合成的
  `expanded:` 标记一个都不在 tag 列表里,而不是任何一条已出现的信息。
- 顺带修掉一个真 bug:图表原本在行的点击区**内部**,点图表会收起自己那行,
  拖图表与渲染器的平移缩放抢手势。点击区改为只有标题行。
- 另一个自伤:诊断用的第二次点击把 toggle 又拨回去,使"点击无效"与"点击有效
  但没渲染"输出相同——**加观测点不能改变被观测的状态**。
- 还有一处 CI 空洞:workflow 的 `paths` 没包含 `.github/scripts/`,而 emulator
  job 的全部逻辑都在那个脚本里,导致一次纯脚本修复**根本没触发 CI**,而"没有
  run"看起来很像"排队中"。
- **悬案**:run 7、8 语义树里同时存在"正在启动 Python"与七行条目,而 `caps`
  与 `entries` 由同一个 `onSuccess` 一起赋值,不该共存;run 9 起未复现,原因
  不明,记为未解释而非已修复。
- 详见 `android/README.md`「Compose 测试:`clickable` 会把子节点的 testTag 吞掉」。

## 2026-08-23 · Android Phase 2:Kotlin 渲染器 + 14 种规格画廊

- 模块从 `com.padpd.spike` 改名 `com.padpd`,删除 Phase 0 的探针屏与
  `padpd_spike/`;CI 的 emulator job 改跑 `GalleryRenderTest`,设备侧守卫
  从"Python 能不能跑"换成"每种图表规格能不能构建、传输、绘制"。
- 一个渲染器覆盖 15 个 figs.py 函数:它们只落在四种原语上(多线 XY、散点、
  柱状、带状叠加)。Phase 3 加图表 = 加一个规格构造函数,不碰渲染器。
- 画廊 14 条标注数据来源:`computed`(真实服务路径)vs `fixture`(真实产出方
  是分钟级/需要 torch/需要设备上没有的仪器 CSV)。**一屏像样的图表极易被当成
  "整条链路能用"的证据,而其中一半不是。**
- 跨语言契约三道守卫,坏的方向都是"静默画出空图",所以都做硬失败:
  builder 与 `*_fig` 一一对应(AST 读,不 import);Kotlin 解析 **Python 真实
  产出**的 fixture;fixture 键集必须与当前 Python 产出一致(防 fixture 过期后
  Kotlin 对着昨天的形状继续通过)。
- 一处故意偏离 figs.py:散点抽稀改向上取整,让 `MAX_SCATTER_POINTS` 真的是
  上界(原式 20 万点溢出到 15,385)。渲染无所谓,传输上界必须是界。
- **Kotlin 侧本地无法验证**(无 SDK/编译器),第一手反馈全在 CI。
- 验证:桌面快车道 369 passed / 17 skipped;14 条画廊全部构建成功
  (最慢 three_loop 1.7 s,总 blob 276 KB)。

## 2026-08-23 · Android Phase 1:Python 适配层就绪

- 新增 `padpd_mobile/api.py`(句柄注册表 + JSON 门面)与 `chart_spec.py`
  (figs.py 的 15 个绘图函数移植成图表规格)。**未改 `gui_core/` 与 `src/` 一行**。
- 三个设计要点:活对象(模型/DPD/波形)留在 Python 侧只给字符串句柄;数组走
  float32 blob 而非 JSON(4096 点 PSD 走 JSON 是 80 KB 文本换 16 KB 数据);
  异常以数据返回而不是抛进 Java。
- `call` 同时返回容器本身的句柄——服务函数常返回"数组+活对象"混合的 dict,
  没有整体句柄的话 Kotlin 得逐字段重组。
- `tests/test_mobile_api.py` 27 条,**核心是契约漂移守卫**:断言 DISPATCH 里
  每个名字在 services.py 真实存在、chart_spec 的 builder 集合与 figs.py 的
  `*_fig` 一一对应(用 AST 读,避免 CI 快车道没有 PySide6/matplotlib)。
- 一处**故意偏离** figs.py:散点抽稀改用向上取整,使 `MAX_SCATTER_POINTS`
  真的是上界(原式 200k 点会溢出到 15,385)。渲染无所谓,但传输上界必须是界。
- 验证:全量快车道 352 passed / 17 skipped;适配层在 Android 版本天花板
  (Python 3.10 / numpy 1.23.3 / scipy 1.8.1)上同样 27 passed。

## 2026-08-23 · Android Phase 0 通过(真机实测,五条全达成)

- 真机(aarch64 / Linux 5.10.43):冷启动到 Python 就绪 **178 ms**(阈值 5 s),
  GMP 拟合 **0.63 s**(阈值 15 s),ILA 三轮 **2.31 s**(阈值 30 s),
  scipy 四子模块全过,服务层 0.01 s 且无 torch,APK 43.6 MB。**Phase 0 门槛已清。**
- **预测方向记反了**:计划里估"手机约为桌面基线的 1–3 倍慢",实测反而快
  (GMP 0.31×、ILA 0.75×)。根因是那份"桌面基线"取自受限的共享云 vCPU,不是
  工作站。**教训:基线必须标明测量机器**,否则倍数外推会连方向都错。
- 仍需注意:以上是单次冷跑,连续长作业会热节流;CI 模拟器数字与真机接近是巧合
  (x86_64 + KVM 原生执行,不模拟 ARM),**不可当手机性能的代理指标**。
- 详见 `android/README.md`「真机实测」。

## 2026-08-23 · Android Phase 0:CI 侧五条验收过了三条

- run 11 三个 job 全绿。**标准 1**(scipy 四个子模块全部 import)、**标准 2**
  (服务层导入 0.02 s 且无 torch)、**标准 4**(APK 43.6 MB / 预算 120 MB)达成。
- 顺带确认:`PADPD_DATA_DIR` 覆写在设备上生效(`/data/user/0/.../files` 可写),
  Chaquopy 的 numpy 链的是 OpenBLAS,`scipy.signal` 首次 import 要 1.37 s
  (UI 需预热)。
- **标准 3、5 仍待真机**。CI 的耗时数字(GMP 拟合 0.59 s)比桌面基线还快,因为
  x86_64 模拟器走 KVM 在 runner CPU 上原生跑,没模拟 ARM——**对手机零预测力**,
  不能当性能结论用。标准 5 则是 instrumented test 根本没测(`Python.start()`
  在计时之外)。
- 教训:`android-emulator-runner` 把 `script:` **逐行**丢进独立 `sh -c`,变量、
  `cd`、`set +e` 都不跨行。它让 `cd android` 静默失效、`./gradlew` 在错误目录
  执行,连烧四轮。我有两轮是在修一段**根本没按我以为的方式执行**的脚本——
  排障时应更早怀疑执行模型,而不是只怀疑脚本内容。
- 详见 `android/README.md`「CI 实测结果」与「这个 spike 已经挡掉的坑」(六条)。

## 2026-08-23 · Android 依赖被平台锁在项目声明的下限以下

- Chaquopy 仓库 **scipy 最高 1.8.1 且最高只有 cp310**;选 Python 3.11 时
  pip 找不到轮子会**静默掉回 PyPI 源码包**交叉编译,死在 meson 缺失。
- 由此锁死:Python 3.10 / scipy 1.8.1 / numpy 1.23.3(scipy 1.8.1 要求
  `numpy<1.25`)。而 `pyproject.toml` 声明 numpy>=1.24、scipy>=1.10。
- **实测这套旧版本套件是过的**(292 passed / 20 skipped),说明那两个下限
  是保守值而非真实约束——Android 路线在依赖上可行。
- 结论有保质期:用上 numpy 1.24+/scipy 1.10+ 的 API 会让 Android 构建断掉,
  且报错指不回肇事提交。新增 `.github/workflows/android-deps-floor.yml`
  在天花板版本上跑套件来守。
- 方法论:**不猜版本,让 CI 去列仓库**。加一个几秒的 job 列出 Chaquopy 的
  全部 numpy/scipy 轮子,一次拿到确定答案,省掉反复试 pin 的多轮 CI。
- 详见 `android/README.md`「依赖版本天花板」。

## 2026-08-23 · Android 化 Phase 0 spike 已就位(未构建)

- 结论修正:此前判断"不适合做 Android app",其中依赖与算力两条**不成立**。
  Chaquopy 有官方 numpy/scipy 轮子;实测 GMP 拟合 2.02 s、ILA 三轮 3.07 s
  (104,448 样本,单线程 BLAS),手机上按 1–3 倍算是可交互的。
- 三个白捡的适配性事实(均已实测,非推断):`gui_core/services.py` 导入时
  不加载 torch 也不导入 matplotlib;绘图数据以数组返回,故 Kotlin 可原生
  绘图;`gui_core/paths.py` 的 `PADPD_DATA_DIR` 覆写在 Android 上直接可用,
  **该文件一行不用改**。全项目无 `multiprocessing`。
- 已知能力缺口:torch 在 Android Python 侧无轮子 → `fit_neural`、
  `run_dpd_dla`、PTQ 位宽扫描、ONNX 导出、`codesign_torch` 五个入口跑不了,
  处置为能力探测 + 灰显。
- 新增 `android/`(spike 工程 + `padpd_spike/probe.py`)。**从未构建过**——
  作者环境的网络策略拦截 `dl.google.com` 与 `chaquo.com`。已验证的只有:
  probe 逻辑桌面跑通、三个 `.gradle` 语法合法;`MainActivity.kt` 未编译。
- 五条验收标准与桌面基线见 `android/README.md`;真机数字回来后补一条 LOG。

## 2026-08-15 · Project Cairn 初始化

- 初始化 Cairn 结构:`AGENTS.md`、`CLAUDE.md`(一行 `@AGENTS.md`)、
  `.cairn/config.yaml`、`cairn/LOG.md`。
- 决策:`git_policy: track`(仓库已公开,与本项目公开记录负结果的做法一致)、
  provider 暂缓对接、`language: zh`、`migration_mode: inventory_only`。
- 原 `CLAUDE.md`(80 行操作性约束)按 Cairn 分层重组:高频硬约束进
  `AGENTS.md`,完整陷阱清单进 `cairn/工程约束与陷阱.md`。
- 逐条核对了迁移完整性(20 项),首轮漏了 3 条(LS 不用 SGD、FnWorker
  控件快照、性能数字三处同步),已补回后复核 20/20。**重组类改动要逐条
  对账,不能只看"读起来都在"。**
- 未建 `cairn/ROADMAP.md`——路线图已在 `docs/03_roadmap.md`,不重复。
- 详见 `AGENTS.md` 与 `.cairn/config.yaml`。

## 2026-08-15 · 既有文档体系盘点(inventory_only)

- 清点 README / CONTRIBUTING / CHANGELOG / `docs/` 七篇 / 手册 16 章 /
  文档站,确认均为当前真相,无需搬运或重写。
- 划定 Cairn 边界:既有文档答"是什么、怎么用、结论如何",Cairn 只装过程知识。
- 识别出三项尚无稳定归属的过程知识(C-IM3 六方案比较过程、GUI 死锁诊断
  过程、各阶段选型取舍),按 inventory_only 边界不搬运,留待触发时建档。
- 详见 `cairn/历史文档盘点.md`。
