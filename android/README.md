# Android 化 Phase 0：可行性 spike

一个最小 Android 工程，**没有业务 UI**——一个按钮、一块文本。它存在的唯一
目的，是把三个**只能在真机上回答**的未知变成数字：

1. Chaquopy 的 scipy 轮子是否含 padpd 实际用到的子模块；
2. 这些建模操作在手机 SoC 上到底要多久；
3. 带 numpy + scipy 的 APK 有多大。

拿到数字之前不要往 Phase 1（Python 适配层）走——完整规划见
`/root/.claude/plans/` 里的实施计划，能力边界与架构决策都在那。

---

## 这个工程里已经验证过什么

作者环境无法访问 `dl.google.com` 与 `chaquo.com`（网络策略拦截），
**所以这份工程从未被构建过**。诚实区分：

| 项 | 状态 |
|---|---|
| `padpd_spike/probe.py` 逻辑 | ✅ 已在桌面跑通（见下方基线） |
| 三个 `*.gradle` 的 Groovy 语法 | ✅ 已用 Gradle 自带 Groovy 解析器验证 |
| `settings.gradle` 的仓库配置 | ✅ Gradle 实际读取并尝试了全部四个仓库 |
| `MainActivity.kt` | ❌ **未编译过**（环境无 Kotlin 编译器与 Android SDK） |
| Gradle 依赖解析 / Chaquopy 打包 / APK | ❌ **未验证**——这正是你要做的事 |

第一次构建报错是**预期内**的，尤其是版本 pin。

---

## 构建之前：先核实三个 pin

这三个版本号是在**没有网络核实**的情况下填的，是起点不是定论。开工第一件事
是去对一遍，不对就改：

| 位置 | 当前值 | 要核实什么 |
|---|---|---|
| `build.gradle` | Chaquopy `16.0.0` | 当前发布版；同时确认它与 AGP 的兼容矩阵 |
| `build.gradle` | AGP `8.7.2` / Kotlin `2.0.21` | 与你本机 Android Studio 匹配 |
| `app/build.gradle` | `python version "3.11"` | **必须同时满足**：Chaquopy 支持该版本，且 ≥ 3.10（`pyproject.toml` 的 `requires-python`） |

顺带确认 **Chaquopy 的许可**。近年它已转为免费，但本项目是 MIT，**请自己去
看一眼当前条款**，不要照抄这句话。

Chaquopy 还需要本机有一个 Python 3 用来跑 pip（"buildPython"）。装了
Android Studio 通常能自动找到；找不到就在 `python { }` 里显式给
`buildPython "/path/to/python3"`。

---

## 构建与运行

```bash
cd android
# 首次：把 Gradle wrapper 补全（本仓库不提交 wrapper jar）
gradle wrapper --gradle-version 8.10.2

./gradlew :app:installDebug        # 装到已连接的 arm64 真机
./gradlew :app:assembleRelease     # 量体积用
```

APK 体积看：

```bash
ls -l app/build/outputs/apk/release/app-release.apk
```

**在真机上跑，不要只看模拟器。** x86_64 模拟器的耗时数字与 arm64 真机不是
一回事，结论以真机为准。

点 Run probe（第一次会慢，因为要解包 numpy/scipy），跑完点 Copy result 把
报告复制出来。

---

## 验收标准

任何一条不过，**回到计划重新评估，不要进 Phase 1**：

| # | 标准 | 为什么是这个值 |
|---|---|---|
| 1 | `scipy.signal` / `optimize` / `interpolate` / `io` 四个子模块全部 import 成功 | 缺任何一个都会在某个页面里晚爆，而不是在这里 |
| 2 | `import gui_core.services` 成功，且 `torch not imported` | 服务层是整个架构的边界；torch 在 Android 无轮子 |
| 3 | GMP 拟合 < 15 s，ILA 三轮 < 30 s | 留足余量的**上限**，不是目标值；目标是桌面基线的 1–3 倍 |
| 4 | 单 ABI release APK < 120 MB | 超了就要考虑砍 scipy 依赖或改服务端架构 |
| 5 | 冷启动到 Python 就绪 < 5 s | 报告首行的 `python start + import` |

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
