# Android 化 Phase 0：可行性 spike

一个最小 Android 工程，**没有业务 UI**——一个按钮、一块文本。它存在的唯一
目的，是把三个**只能在真机上回答**的未知变成数字：

1. Chaquopy 的 scipy 轮子是否含 padpd 实际用到的子模块；
2. 这些建模操作在手机 SoC 上到底要多久；
3. 带 numpy + scipy 的 APK 有多大。

拿到数字之前不要往 Phase 1（Python 适配层）走——完整规划见
`/root/.claude/plans/` 里的实施计划，能力边界与架构决策都在那。

---

## 怎么构建

两条路，**先走 CI**——它不需要你本地装任何东西。

### 一、GitHub Actions（推荐）

`.github/workflows/android-spike.yml`，改动 `android/**` 时自动跑，也可以
在 Actions 页手动触发（workflow_dispatch）。两个 job：

| job | 干什么 | 覆盖哪条验收 |
|---|---|---|
| **build** | arm64-v8a release 构建，量 APK 体积，超 120 MB 直接红 | 4 |
| **probe** | x86_64 模拟器上跑 `ProbeTest` 这个 instrumented test | 1、2、5 |

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

点 Run probe（第一次会慢，因为要解包 numpy/scipy），跑完点 Copy result 把
报告复制出来。

---

## 这个工程里已经验证过什么

作者环境无法访问 `dl.google.com` 与 `chaquo.com`（网络策略拦截），
**所以这份工程在作者手里从未被构建过**。诚实区分：

| 项 | 状态 |
|---|---|
| `padpd_spike/probe.py` 逻辑 | ✅ 已在桌面跑通（见下方基线） |
| 三个 `*.gradle` 的 Groovy 语法 | ✅ 已用 Gradle 自带 Groovy 解析器验证 |
| `settings.gradle` 的仓库配置 | ✅ Gradle 实际读取并尝试了全部四个仓库 |
| workflow YAML | ✅ 已解析验证 |
| `MainActivity.kt` / `ProbeTest.kt` | ❌ **未编译过**（环境无 Kotlin 编译器与 Android SDK） |
| Gradle 依赖解析 / Chaquopy 打包 / APK | ❌ **未验证**——交给上面那条 CI |

第一次 CI 跑红是**预期内**的，尤其是版本 pin。

---

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


### 这个 spike 已经挡掉的坑

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

## 拿到数字之后

把真机报告贴进 `cairn/LOG.md` 顶部新条目（摘要 + 指针，≤ 20 行），并记下
用的是哪台设备。若某条验收不过，把**为什么不过**也写进去——那正是
`cairn/` 该装的过程知识。

---

## 目录说明

```
android/
  settings.gradle          仓库配置（含 chaquo.com maven）
  build.gradle             插件版本 pin
  gradle.properties
  app/build.gradle         Chaquopy 配置 + Python 源码暂存任务
  app/src/main/
    AndroidManifest.xml    无任何权限声明
    java/com/padpd/spike/MainActivity.kt
    python/padpd_spike/probe.py    ← 真正干活的地方
    res/values/strings.xml
```

**`stagePythonSources`**（`app/build.gradle`）把 `../src/padpd` 与
`../gui_core` 暂存到 `build/python-src/`，Chaquopy 从那里打包。这样 app 跑的
是**和桌面 GUI 同一份代码**，而不是副本——`gui_core/services.py` 是共享契约，
分叉了整个架构就塌了。同时避免把 `tests/`、`docs/`、2.9 MB 的 `manual/` 一并
卷进去。

这个 spike 是**一次性的**：`padpd_spike/` 不会被 Phase 1 之后的 app 引用。
