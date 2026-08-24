# padpd Android

Kotlin 原生 UI + Chaquopy 嵌入的 Python 计算核。跑的是**和两个桌面 GUI
同一份** `gui_core/services.py`，不是副本。

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 可行性 spike | ✅ 五条验收全过（见下方「真机实测」） |
| Phase 1 | Python 适配层（`padpd_mobile/`） | ✅ 44 条桌面测试 |
| Phase 2 | Kotlin 图表渲染器 + 14 种规格画廊 | ✅ 本页「图表层」一节 |
| Phase 3 | 9 个页面 | ✅ 九页全部移植（60 条桌面测试 + 每页真机 instrumented test） |

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

## 共享控件不能自带滚动:嵌套横向滚动直接抛异常

Compose 在横向滚动组件收到**无限宽约束**时抛 `IllegalStateException`,而
`Row(horizontalScroll)` 里再放一个 `Row(horizontalScroll)` 正好制造这个约束:

    Horizontally scrollable component was measured with an infinity
    maximum width constraints, which is disallowed.

这条是重构引入的回归:把波形页的 `Choice`(内部无滚动)与建模页的
`ChoiceRow`(内部有滚动)合并成共享 `OptionRow` 时,保留了带滚动的那版,而
波形页把它放在一个已经在滚动的外层 Row 里。**上一轮波形页三条设备测试是全过
的,是合并把它们弄坏的。**

约定:`screens/Common.kt` 里的共享控件**不带滚动修饰符**——它不知道会被嵌进
什么容器。需要滚动由调用方在外面包一层。`MetricRow` 是例外(它自带横向滚动),
所以它只能直接放在纵向容器里,这一点写在它的注释里。

同轴嵌套才是问题:`Column(verticalScroll)` 里放 `Row(horizontalScroll)` 合法。

## 横向滚动条里的节点:composed ≠ 点得到

导航栏是 10 项的 `Row` + `horizontalScroll`,最后一项(图表画廊)默认在视口外。
`Row` 不是 lazy,所以那个节点**已经 composed、tag 查得到**;
`performClick` 因此不报错,它把触摸注入到视口外的坐标,没有任何人收到。

失败长这样——标签列表里全是导航项和当前页的控件,一个目标页的标签都没有:

    none of [head:psd] appeared within 20000ms.
    Tags present: [..., nav:gallery, ..., generate, cfr, 带宽(MHz):80, ...]

点之前先 `performScrollTo()`。

**这个坑出现过三个变体,根源相同:节点存在 ≠ 可见/可交互。**

| 变体 | 症状 | 修法 |
|---|---|---|
| 合并语义树(`clickable` 吞子节点) | tag 根本查不到 | `useUnmergedTree = true` |
| 横向滚动视口外 | 查得到、`performClick` 不报错、但没反应 | 点前 `performScrollTo()` |
| 纵向滚动视口外 | 查得到、`assertIsDisplayed` 失败 | 断言前 `performScrollTo()` |

前两个都表现为"点了没反应",第三个表现为"组件不可见"。写设备测试时:
**查到 tag 只说明它被组合了,要交互或断言可见,先滚过去。**

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

后来这个守卫**误报**过一次:`SafImport.kt` 里 SAF picker 的 MIME 通配符
写作星号-斜杠-星号,朴素扫描把中间两个字符当成注释结束符,报文件深度 -1。
Kotlin 的词法器不会从字符串字面量里闭合注释,所以守卫也不该——现在它跳过
字符串、字符与原始字符串字面量,并且 `_comment_depth` 自带一条测试,把当年
真正吃掉 i18n 包的那段文本和这次误报的字符串一起钉住。

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

## UI 自动化:节点断言测行为,截图看长相,两者不混

节点断言(`ui-test-junit4` + `createAndroidComposeRule`)从 Phase 2 就在跑,
现在 9 个测试类、35 条、都在 emulator job 里。它测的是**行为**:点了会不会跑、
指标是不是这个数、失败会不会说原因。

它结构上看不见的是**长相**。一张卡片可以"节点存在、文本正确",同时高四行、
把邻居挤出屏幕——断言全绿。所以另加截图。

### 截图不做 golden 对比,只当证据

emulator 用的是 `-gpu swiftshader_indirect` 软件渲染,跑在
`reactivecircus/android-emulator-runner` 给的镜像上,而**镜像版本由 GitHub 自己
升**。字体栅格化、抗锯齿、Skia 版本任何一处变了,整套金图一起红,而那次红和被
测的提交毫无关系。逐像素比对要做,得放到 JVM 上——那里 layoutlib 是钉死版本号的
构件。

所以 `Screenshots.capture` **吞掉自己的异常**:截不到图绝不能让一条行为测试变红。
证据一旦能卡 CI,它就是断言,而这么飘的断言活不过一个月。唯一检查它的是
`ScreenshotTour` 末尾那句 `Screenshots.written > 0`——放在一条本来就不测别的事
的用例里。

### 图怎么从设备上下来

`getExternalFilesDir` 写出来的文件,**API 30+ 上 `adb pull` 需要 root**,而这台
模拟器是 API 34。走 AGP 的正规通道:

- `build.gradle` 打开 `useTestStorageService: 'true'`,并把
  `androidx.test.services:test-services` 作为 `androidTestUtil` 装进去(它是随
  测试 APK 一起安装的服务,不编进测试代码);
- AGP 于是给测试传一个 `additionalTestOutputDir` 参数,并在跑完把那个目录拉到
  `build/outputs/connected_android_test_additional_output/`;
- helper 拿不到这个参数时退回 external files dir,收集脚本两条路都试。

两条都是 best effort,但**每张图的路径都写进 logcat**(`Log.i`,不是 `println`
——instrumented test 的 stdout 不一定进 logcat),收集脚本 grep 出来并打印张数。
所以"一张都没有"和"写成功了只是没拉下来"在日志里是分得开的。

### 截图看不到的那部分,用测量补

截图是给人看的,而**这个开发环境看不到自己的截图**——artifact 主机和
`dl.google.com` 一样被出网代理拦着。所以布局那条不变量不能只靠图:
`LayoutBoundsTest` 切到英文、读每张指标卡的 `getBoundsInRoot()`,断言宽度不超过
`METRIC_MAX_WIDTH`(和布局代码共用同一个常量,免得两边各写一个数字然后分家)。

高度只**记录不卡阈值**:一个 label 折几行是字体度量的函数,把猜出来的行数写成
阈值,就是测试开始为没人在意的原因变红的起点。天花板放宽到只拦"无上限地长"
这一种缺陷,真实数字打进 logcat,以后要收紧就有实测可依。

顺带记一笔:`widthIn` 必须放在 `background` 之前。放在 `padding` 里面的话,
它约束的是文字而不是卡片,卡片实际比写的数字宽 20.dp——那样测试断言的数字
就不是代码里写的那个数字了。

### golden 对比:14 种图 × 明暗两套,跑在 JVM

`src/screenshotTest/` 用 AGP 的 Compose Preview 截图测试(插件
`com.android.compose.screenshot`)。**版本必须和 AGP 配对**,而这个插件的 POM
不声明 AGP——它声明 `com.android.tools.compose:compose-preview-detector`,那个
版本就是 Android tools 版本,`31.x` 对 AGP `8.x`:

| 插件 | compose-preview-detector | → AGP |
|---|---|---|
| **alpha06** | 31.7.0-alpha09 | **8.7**(本项目) |
| alpha07 | 31.8.0-alpha02 | 8.8 |
| alpha08 | 31.9.0-alpha01 | 8.9 |
| alpha09 | 31.10.0-alpha04 | 8.10 |

凭印象本来要钉 alpha08,**差了两个版本**。workflow 里那个查询 job 就是为这个
留着的,和查 Chaquopy 轮子的那个同理。

启用要**两处**,少一处就是一整轮构建:`gradle.properties` 的
`android.experimental.enableScreenshotTest=true`,**加上**模块 `android {}` 块里的
`experimentalProperties["android.experimental.enableScreenshotTest"] = true`。
只设前者会配置到一半然后报 "Please enable screenshotTest source set in module
first"——报错把修法写出来了,但那是花一轮构建换来的。

**数据是真的**:每个 preview 读的是 `chart_spec.py` 自己产出的 fixture
(`tests/test_chart_fixtures.py` 既生成又守),不是在 Kotlin 里手写的
`ChartSpec`。手写的会拿虚构数据去测渲染器,而且会悄悄漏掉那些**渲染器真正
会画错**的情形:对数轴、双轴、类别轴、bar 里的 NaN 断口、掩码带。gallery 的
那套输入本来就是为了跑遍每种绘图原语而存在的。

**渲染时没有文件可读**——这条花了三轮 CI 才认清。layoutlib 在自己的进程里跑
预览,两条取文件的路都不通:

| 放法 | 结果 |
|---|---|
| `src/screenshotTest/resources/` | `fixture ... is not on the classpath` |
| `src/debug/assets/` | `assets=true, classpath=false`——AssetManager 在,但打不开 |

两次都是 28 张预览**全部渲染成空图**(每张约 800 字节)。所以 fixture 现在
**编进 Kotlin 源码**(`ChartFixtures.kt`,由 `tests/test_chart_fixtures.py` 生成):
没有文件、没有 classpath、没有 AssetManager,不依赖渲染器怎么找东西。

两个实现细节:class 文件里单个字符串字面量上限 65535 字节,所以按 30000 字符
切块;**块必须在运行时拼**,因为编译器会把常量 `+` 折回成一个字面量,上限照样撞。

序列在冻结前抽稀到 **800 点**:380dp 宽的图画不出四千个点,而金图要放进源码树。
spec 一个字节都不动(label/范围/轴归属是契约,精确比对),绘图特性也全都在——
NaN 断口、类别刻度、掩码带要么是元数据要么本来就只有几个点。

**明暗都画**:`@Preview` 的 `uiMode` 驱动 `isSystemInDarkTheme()`,而
`ChartTheme` 读的是同一个信号。深色配色在代码里躺了很久,在这之前**没有任何
东西渲染过它**——模拟器跑的是亮色,一条在深色背景上看不见的曲线可以一路发版。

CI 那一步是**自举**的:没有基准图就生成并上传,有基准图就比对,两条路都不会
为"还没有第一次"而红。写这段的开发环境**下载不了 artifact**(出网代理拦了
blob 主机),所以第一批基准图必须由能打开 artifact 的人放进
`app/src/debug/screenshotTest/reference/` 并提交。

### 覆盖范围

`ScreenshotTour` 走十个屏 × 中英两种语言,拍的是**静息态**——布局在结果到达之前
就定下来了。英文那一半是真正值钱的:整张 i18n 表一次性切换,英文字符数约为中文的
三倍,卡片撑爆和表格错位都在这里现形。要结果才有的画面(波形、部署位宽表、数据源
预览、联合设计)由本来就在跑那些计算的测试顺手拍一张,不重复跑一遍一分钟的扫描。

## SAF 给的是授权,不是路径

`gui_core.services.load_source` 收的是文件系统路径——桌面上文件就是路径。
Android 的 Storage Access Framework 给的是 `content://` URI:一份**可撤销
的、指向某个 provider 的授权**,不是位置。它背后的文档可能在别的 app 的
私有目录、在网络 provider 上、或者在一个 zip 里,没有路径可以还原。

所以 `SafImport.copyToCache` 在授权还有效时把字节拷出来,再把真实路径交给
Python。这不是绕过 SAF,这就是 SAF 的用法:picker 返回的授权作用域限于本次
任务,用户离开 app 就可能失效,任何之后还要用内容的代码都必须先取一份拷贝。

两个具体决定:

- **拷到 `cacheDir`**。源一旦被 Python 读进来就已经是内存里的 numpy 数组,
  再永久留一份 40 MB 的采集只是让 app 占用随每次导入增长。
- **保留显示名**。后缀是有语义的:`pages.py` 靠后缀选 loader
  (`npz`/`cadence`/`mat`),按 URI 的 lastPathSegment 命名会让文件以"不支持
  的类型"到达。显示名由 provider 自由决定,可能带路径分隔符,所以只取最后
  一段——`../../databases/x` 拼到 cache 目录上会写到 app 的 databases 里,
  这不是"不太可能",是"必须不可能"。

系统 picker 无法在 instrumented test 里驱动,但 picker 本身没什么可测的:
它只返回一个 URI。`SafImportTest` 用 `file://` URI 走同一条 ContentResolver
路径,测的是这个项目自己写的那半:拷贝、后缀、路径逃逸。

**OpenDPD 数据集目录不提供**:那是以 spec.json 为键的目录树,SAF 一次只授权
一个文档,树导入意味着走 document tree 再逐个拷出来。数据页把这条写在界面
上,而不是摆一个填不了的目录输入框。

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
