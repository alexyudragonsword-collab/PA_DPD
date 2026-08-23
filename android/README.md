# padpd Android

Kotlin 原生 UI + Chaquopy 嵌入的 Python 计算核。跑的是**和两个桌面 GUI
同一份** `gui_core/services.py`，不是副本。

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 可行性 spike | ✅ 五条验收全过（见下方「真机实测」） |
| Phase 1 | Python 适配层（`padpd_mobile/`） | ✅ 44 条桌面测试 |
| Phase 2 | Kotlin 图表渲染器 + 14 种规格画廊 | ✅ 本页「图表层」一节 |
| Phase 3 | 9 个页面 | 未开始 |

## 怎么构建

两条路，**先走 CI**——它不需要你本地装任何东西。

### 一、GitHub Actions（推荐）

`.github/workflows/android-spike.yml`，改动 `android/**` 时自动跑，也可以
在 Actions 页手动触发（workflow_dispatch）。两个 job：

| job | 干什么 | 覆盖哪条验收 |
|---|---|---|
| **wheels** | 列出 Chaquopy 仓库里 numpy/scipy 的全部轮子 | — |
| **build** | arm64-v8a release 构建 + JVM 单元测试，量 APK 体积，超 120 MB 直接红 | 4 |
| **instrumented** | x86_64 模拟器上跑 7 条设备测试：`PyBridgeTest`（14 种规格构建 + blob 传输）、`ChartRenderTest`（14 种规格绘制）、`GalleryScreenTest`（启动 → 点开 → 出图） | 1、2 |

报告会贴进 job summary，同时作为 artifact 上传（`probe-report.txt` +
logcat + APK）。

**CI 替代不了真机**：runner 只有 x86_64 模拟器，模拟出来的耗时对 arm64 手机
没有参考价值。**验收标准 3（基准耗时）必须在真机上量。**

### 二、本地

本仓库不提交 wrapper jar，先生成：

```bash
./.github/scripts/gen-gradle-wrapper.sh android 8.10.2
```

**不要**直接在 `android/` 里跑 `gradle wrapper`。AGP 8.7 还在引用
`org.gradle.util.VersionNumber`，这个内部类 Gradle 9 已经删了；而
`gradle wrapper` 会先配置工程、加载插件，于是你若本机装的是 Gradle 9，
它会在"正要去钉 Gradle 版本"那一步就崩掉——先有鸡还是先有蛋。上面那个脚本
在空目录里生成（没有 build 脚本就不加载插件）再拷进来，绕开这一环。
CI 第一次跑就是栽在这儿的。

```bash
cd android
./gradlew :app:installDebug        # 装到已连接的 arm64 真机
./gradlew :app:assembleRelease     # 量体积用
ls -l app/build/outputs/apk/release/app-release.apk
```

启动后是**图表画廊**：14 种图表规格各一条，点开即渲染。每条标了数据来源
（见下方「图表层」）。

---

## Kotlin 代码在哪里被验证

作者环境访问不了 `dl.google.com` 与 `chaquo.com`（网络策略拦截），
**本地没有 Android SDK 也没有 Kotlin 编译器**。所以：

| 层 | 在哪验证 |
|---|---|
| Python 适配层、规格层、画廊 | 桌面 pytest（`tests/test_mobile_api.py`，44 条） |
| `*.gradle` 语法 | 本地用 Gradle 自带的 Groovy 解析器 |
| Kotlin 编译、Compose、Chaquopy 打包、APK | **只有 CI**——`build` job |
| 渲染器真的画得出来 | **只有 CI/真机**——`instrumented` job |

也就是说 Kotlin 侧的第一手反馈全部来自 CI。改 Kotlin 后不要凭"看着对"
就下结论。

---

## Kotlin 的块注释可以嵌套——注释里写 `/*` 会吃掉整个文件

Java 的块注释不嵌套,Kotlin 的**嵌套**。所以在 KDoc 里写一个 glob 路径
(例如 `gui_qt/pages/` 加通配符 `.py`)等于开了一层内层注释,文件末尾的
`*/` 只闭合内层,外层一路吃到文件结束,把后面所有声明吞掉。

`Strings.kt` 里的一处这样的写法产出的报错是:

    Strings.kt:56:1 Syntax error: Unclosed comment.
    MainActivity.kt:34:23 Unresolved reference 'Strings'.
    ...(另外 19 条 Unresolved reference,分布在三个文件)

**20 条错误指向三个无辜文件,真凶那条排在中间。** 按"报错最多的文件"去查
会查错方向。

`tests/test_mobile_pages.py::test_kotlin_block_comments_are_balanced` 守这条:
本地没有 Kotlin 编译器,但这个错误不需要编译器,数深度就够了。

## Compose 测试：`clickable` 会把子节点的 testTag 吞掉

`Modifier.clickable` 隐含 `mergeDescendants = true`，把整个子树合并成**一个**
语义节点。`onNodeWithTag` / `onAllNodes` 默认查的是合并树,所以**放在可点击
容器里的 testTag 一个都查不到**。

代价是七轮 CI。`GalleryScreenTest` 等 `chart:psd`,而 `chart:` / `pending:` /
`error:` 全在行的 `clickable` 里——**无论 app 表现如何,这个节点都不可能出现**。
失败信息看上去完全像产品 bug（"点了没反应"),于是连续几轮都在查点击分发、
协程、状态传播,查的全是好的代码。

两条结论:

- 设备测试里查 tag 一律带 `useUnmergedTree = true`。否则失败模式是**测试静默
  地什么都没断言**——比断言失败危险得多。
- 定位这类问题要看**该出现而没出现的东西**。真正的线索是每行都会合成的
  `expanded:` 标记一个都不在列表里,不是任何一条出现了的信息。

顺带修掉一个真 bug:图表原本在行的点击区**内部**,点图表会把自己那行收起来,
拖动图表会和渲染器的平移缩放抢手势。现在点击区只有标题行。

**尚未解释**:run 7、8 的语义树里同时有"正在启动 Python"和七行条目,而
`caps` 与 `entries` 在源码里由同一个 `onSuccess` 分支一起赋值,不该共存。
run 9 起没再复现,原因不明——记为悬案,不当作已修。`bootPending` 标签保留,
以便复发时一眼看出来。

## 依赖版本天花板（已实测，别改回去）

Chaquopy 仓库里 **scipy 最高只到 1.8.1，且最高只有 cp310**——没有
cp311/cp312/cp313。选 Python 3.11 时 pip 在那儿找不到 scipy，会**静默掉回
PyPI 的源码包**去交叉编译，然后死在 `meson executable "meson" not found`。
CI 第三轮就是这么挂的。

于是这套组合是被平台锁死的：

| | `pyproject.toml` 声明 | Android 能给的 | 依据 |
|---|---|---|---|
| Python | `>=3.10` | **3.10** | Chaquopy 无 cp311+ 的 scipy |
| scipy | `>=1.10` | **1.8.1** | 仓库最高版 |
| numpy | `>=1.24` | **1.23.3** | scipy 1.8.1 要求 `numpy<1.25` |

**两个都低于项目声明的下限，但测试套件在这套版本上是过的**——Python 3.10 +
numpy 1.23.3 + scipy 1.8.1 实测 292 passed / 20 skipped（跳过的是 torch 与
两个 GUI 的测试，那些依赖在 Android 上本来就不存在）。也就是说
`pyproject.toml` 那两个下限是保守值，不是真实约束。

这条结论有保质期：一旦有人用上 numpy 1.24+ 或 scipy 1.10+ 的 API，Android
构建就会悄悄断掉，而且报错会以 Chaquopy 构建失败的面目出现，指不回肇事的那次
提交。`.github/workflows/android-deps-floor.yml` 就是守这条的——它在这个天花板
版本上跑测试套件。

`app/build.gradle` 里的版本**必须钉死**：不钉的话 PyPI 的新版会在解析时赢过
Chaquopy 的 Android 轮子，而 PyPI 没有 Android 构建。

### buildPython 必须和目标 Python 同版本

Chaquopy 用一个本机解释器（"buildPython"）跑 pip，而 **pip 是拿自己运行的
版本去比 wheel 的 `Requires-Python`**，不是拿目标版本比。所以 buildPython
是 3.11、目标是 3.10 时，会出现这种场面：

```
Downloading .../scipy-1.8.1-1-cp310-cp310-android_21_arm64_v8a.whl (20.3 MB)
ERROR: Package 'scipy' requires a different Python: 3.11.16 not in '>=3.8,<3.11'
```

**正确的轮子下载完了，然后被否掉**，而报错只提 scipy，一个字不提 buildPython。
CI 第五轮就栽在这儿。`app/build.gradle` 现在会在配置阶段核对两者并直接报错，
所以这个坑只会踩一次——但本机构建时 `-PpadpdBuildPython` 也要给 3.10。

## 构建之前：先核实这几个 pin

这些版本号是在**没有网络核实**的情况下填的，是起点不是定论：

| 位置 | 当前值 | 要核实什么 |
|---|---|---|
| `build.gradle` | Chaquopy `16.0.0` | 当前发布版；与 AGP 的兼容矩阵。**换版本会换仓库路径**（16.0.0 用的是 `pypi-13.1`），可用轮子也可能跟着变 |
| `build.gradle` | AGP `8.7.2` / Kotlin `2.0.21` | 与你本机 Android Studio 匹配。注意 AGP 8.7 跑不了 Gradle 9 |

CI 里的 **List Chaquopy's Android wheels** job 会列出仓库中 numpy/scipy 的
全部轮子——换 Chaquopy 版本后先看它，再决定 pin 什么。

顺带确认 **Chaquopy 的许可**。近年它已转为免费，但本项目是 MIT，**请自己去
看一眼当前条款**，不要照抄这句话。

Chaquopy 还需要本机有一个 Python 3 用来跑 pip（"buildPython"）。装了
Android Studio 通常能自动找到；找不到就在 `python { }` 里显式给
`buildPython "/path/to/python3"`。

---

## 验收标准

五条全部达成，Phase 0 的门槛已清。

| # | 标准 | 阈值 | 真机实测 | |
|---|---|---|---|---|
| 1 | `scipy.signal` / `optimize` / `interpolate` / `io` 可导入 | 四个全过 | 全过（`signal` 0.98 s） | ✅ |
| 2 | `import gui_core.services` 且 `torch not imported` | — | 0.01 s，无 torch | ✅ |
| 3 | GMP 拟合 / ILA 三轮 | < 15 s / < 30 s | **0.63 s / 2.31 s** | ✅ |
| 4 | 单 ABI release APK | < 120 MB | 43.6 MB | ✅ |
| 5 | 冷启动到 Python 就绪 | < 5 s | **178 ms** | ✅ |

**Phase 0 通过。** 标准 3 余量 24 倍，标准 5 余量 28 倍。

## 真机实测（aarch64 / Linux 5.10.43）

```
python start + import: 178 ms

--- scipy submodules ---
  ok  scipy.signal       0.98 s      ok  scipy.optimize     0.00 s
  ok  scipy.interpolate  0.00 s      ok  scipy.io           0.02 s
--- numpy / BLAS --- numpy 1.23.3 · scipy 1.8.1 · openblas · OMP_NUM_THREADS=1
--- service layer ---  import gui_core.services 0.01 s · torch not imported
--- data dir ---     /data/user/0/com.padpd.spike/files   writable=True
--- benchmarks (160 MHz / 12 符号 / 104,448 样本) ---
  ofdm generate 0.01   gmp fit 0.63 (52 系数)   gmp predict 0.06
  spline-mp fit 0.59   spline-gmp fit 1.98      ila 3-iter 2.31   aclr 0.00
VERDICT: all probes passed in 6.6 s
```

### 一处预测偏差，方向记反了

计划里估"手机约为桌面基线的 1–3 倍慢"，实测**手机比桌面基线还快**：

| | 桌面基线 | 真机 | 比值 |
|---|---|---|---|
| GMP 拟合 | 2.02 s | 0.63 s | 0.31× |
| Spline-GMP 拟合 | 2.76 s | 1.98 s | 0.72× |
| ILA 三轮 | 3.07 s | 2.31 s | 0.75× |

原因是那份"桌面基线"取自一颗受限的共享云 vCPU，不是真工作站。现代 arm64
大核把它比下去了。**教训:基线要标明是什么机器测的**，否则"1–3 倍"这种外推
会连方向都错——这次错在保守一侧，下次未必。

### 仍需注意

- 以上是**单次冷跑**。连续跑多个长作业会热节流，UI 应串行化作业并显示进度。
- CI 的模拟器数字（GMP 0.59 s）碰巧与真机接近,那是巧合:x86_64 模拟器走 KVM
  在 runner CPU 上原生执行,不模拟 ARM。**别把它当手机性能的代理指标。**


### 这条路上已经挡掉的坑

按出现顺序，都是不真跑一次就不可能知道的：

1. runner 预装 Gradle 9，AGP 8.7 引用了 Gradle 9 已删的
   `org.gradle.util.VersionNumber`；
2. Chaquopy 的 scipy 只到 cp310；
3. 依赖不钉版本会被 PyPI 的新版抢赢，而 PyPI 没有 Android 构建；
4. buildPython 必须与目标 Python 同版本，否则正确的轮子会被 pip 否掉；
5. `org.gradle.parallel` 会让 Kotlin 插件在 `friendPaths` 上撞项目状态锁；
6. **`android-emulator-runner` 把 `script:` 逐行放进独立的 `sh -c` 执行**——
   变量、`cd`、`set +e` 一律不跨行。它让 `cd android` 静默失效、`./gradlew`
   在仓库根目录跑，连续四轮都没产出过 gradle 日志。所以脚本逻辑要放进文件，
   `script:` 只留一行调用（见 `.github/scripts/run-probe-on-emulator.sh`）。

`data dir writable=True` 顺带验证了 `gui_core/paths.py` 的
`PADPD_DATA_DIR` 覆写在 Android 上生效——这条通过意味着**那个文件一行都不用
改**。

---

## 桌面基线（对照用）

2.8 GHz Xeon，Python 3.11，numpy 2.4.6 / scipy 1.17.1，
OpenBLAS 且 `OMP_NUM_THREADS=1`（probe 会钉这个值，理由见
`cairn/工程约束与陷阱.md` 的 libgomp 死锁一节）：

```
scipy.signal        0.75 s      ofdm generate     0.08 s
scipy.optimize      0.00 s      gmp fit           2.02 s   (52 系数)
scipy.interpolate   0.00 s      gmp predict       0.13 s
scipy.io            0.02 s      spline-mp fit     0.92 s
gui_core.services   0.01 s      spline-gmp fit    2.76 s
                                ila 3-iter        3.07 s
                                aclr              0.01 s
波形：160 MHz / 1024-QAM / 12 符号 / 4x = 104,448 样本
```

重现：

```bash
PYTHONPATH=src:.:android/app/src/main/python \
PADPD_DATA_DIR=/tmp/padpd-data \
python -m padpd_spike.probe
```

同一份 `probe.py` 在桌面与设备上跑——保持一份实现，两边的数字才可比。

---

## 重新量真机时

`padpd_mobile.api` 仍然导出 `boot()` / `capabilities()`，Phase 0 的探针脚本
已随 spike 删除。换手机、换 Chaquopy 版本或怀疑性能时要重测，最省事的做法是
在画廊里点开 `psd` 与 `three_loop` 并记录耗时——它们分别代表最便宜与最贵的
路径。结果贴进 `cairn/LOG.md` 顶部新条目并记下设备型号。

---

## 图表层（Phase 2）

`gui_qt/figs.py` 有 15 个绘图函数，但它们只落在**四种原语**上：多线 XY、
散点、柱状、带状/阈值叠加。所以 Python 侧把它们移植成**图表规格**
（`padpd_mobile/chart_spec.py`），Kotlin 侧只写**一个**渲染器
（`com.padpd.chart.ChartCanvas`）——Phase 3 加图表是加一个规格构造函数，
不用碰渲染器。

规格是纯 JSON，**数字不在里面**：数组按 key 单独走 float32 blob
（`api.blob`）。一条 4096 点的曲线是 16 KB 二进制 vs 约 80 KB JSON 文本。

配色不写死在规格里，只给语义角色（`primary` / `accent` / `muted` / `warn` /
`seq`）。`figs.py` 钉死了一套暗色板，而手机有桌面 GUI 从来没有的浅色模式，
所以由 `ChartTheme.kt` 按主题映射，取值对齐 `gui_qt/themes.py`。

### 画廊与数据来源标注

启动即是画廊，14 条覆盖了全部四种原语和所有难缠的坐标轴特性：双 Y 轴、
log 轴、分类刻度、等比例、NaN 断口、阴影带。每条标了来源：

- **computed** —— 真实服务路径跑出来的输出；
- **fixture** —— 真实产出方太慢（`codesign_sweep` 是分钟级）、需要 torch
  （训练曲线、梯度联合设计），或需要设备上没有的仪器 CSV（双音）。形状取自
  真实运行，数字是代表性的，**不是实测**。

这个标注是有意为之：**一屏看着像样的图表，非常容易被当成"整条链路能用"
的证据**，而其中一半根本不是那种证据。

### 跨语言契约怎么守

三道守卫，坏的方向都是"静默画出空图"，所以都做成硬失败：

| 守卫 | 位置 | 防什么 |
|---|---|---|
| `chart_spec` 的 builder 必须与 `figs.py` 的 `*_fig` 一一对应 | `tests/test_mobile_api.py`（AST 读，不 import） | 桌面加了图、移动端没跟 |
| Kotlin 解析 **Python 真实产出**的规格 | `ChartSpecParseTest` + `app/src/test/resources/gallery_specs.json` | 字段改名 |
| committed fixture 的键集必须与当前 Python 产出一致 | `tests/test_mobile_api.py` | fixture 过期后 Kotlin 测试对着昨天的形状继续通过 |

schema 有意改动时重新生成 fixture：

```bash
PYTHONPATH=src:.:android/app/src/main/python python - <<'EOF'
import json, os, tempfile, pathlib
os.environ.setdefault("PADPD_DATA_DIR", tempfile.mkdtemp())
from padpd_mobile import api, gallery
specs = {e["id"]: json.loads(api.gallery_chart(e["id"]))["spec"]
         for e in gallery.listing()}
pathlib.Path("android/app/src/test/resources/gallery_specs.json").write_text(
    json.dumps(specs, ensure_ascii=False, indent=1, sort_keys=True))
EOF
```

## 目录说明

```
android/
  settings.gradle / build.gradle / gradle.properties   版本 pin 与仓库
  app/build.gradle                Chaquopy + Compose + Python 源码暂存
  app/src/main/
    java/com/padpd/MainActivity.kt          画廊界面
    java/com/padpd/chart/ChartSpec.kt       规格（typed，对齐 Python）
    java/com/padpd/chart/ChartCanvas.kt     唯一的渲染器
    java/com/padpd/chart/Scales.kt          坐标映射与刻度（纯算术）
    java/com/padpd/chart/ChartTheme.kt      语义角色 → 配色
    java/com/padpd/chart/Blobs.kt           float32 解码 + 缓存
    java/com/padpd/chart/PyBridge.kt        Chaquopy 桥
    python/padpd_mobile/api.py              句柄注册表 + JSON 门面
    python/padpd_mobile/chart_spec.py       figs.py 的规格移植
    python/padpd_mobile/gallery.py          14 条画廊条目
  app/src/test/         JVM 单元测试 26 条（不需要模拟器）
  app/src/androidTest/  设备测试 7 条：PyBridgeTest / ChartRenderTest /
                        GalleryScreenTest
```

**`stagePythonSources`**（`app/build.gradle`）把 `../src/padpd` 与
`../gui_core` 暂存到 `build/python-src/`，Chaquopy 从那里打包。这样 app 跑的
是**和桌面 GUI 同一份代码**，而不是副本——`gui_core/services.py` 是共享契约，
分叉了整个架构就塌了。同时避免把 `tests/`、`docs/`、2.9 MB 的 `manual/` 一并
卷进去。
