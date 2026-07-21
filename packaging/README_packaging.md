# padpd 桌面版打包说明(PyInstaller)

把 PySide6 桌面 GUI(`gui_qt/`)打成免安装的可执行程序。

## 方式零(推荐):GitHub Actions 云端构建,无需本地 Windows

仓库自带 `.github/workflows/build-windows.yml`,在 GitHub 的
`windows-latest` runner 上构建并做启动冒烟:

1. GitHub 仓库页 → **Actions** → **Build Windows EXE** →
   **Run workflow**(可选任意分支)→ 等待完成(slim 约 8 分钟,
   full 约 20 分钟);
2. 在该 run 的 **Artifacts** 下载:
   - `padpd-desktop-windows-slim.zip`(PyInstaller onedir 精简版,~200 MB,
     经典功能全可用);
   - `padpd-desktop-windows-full.zip`(onedir 完整版,含 CPU 版 torch,
     神经功能可用);解压后运行 `padpd-desktop\padpd-desktop.exe`;
   - `padpd-desktop-windows-onefile`(**Nuitka 单文件 exe**,精简版,
     下载即单个 `padpd-desktop.exe`,双击即运行,无需解压目录)。
3. 推送 `v*` tag(如 `v1.0.0`)会自动构建全部变体并附到 GitHub
   Release。

以下本地构建方式作为无法使用 Actions 时的备选。

## 应用图标

图标源图在 `packaging/icon/source.png`。运行
`python packaging/make_icon.py` 会生成:

- `packaging/icon/padpd.ico`(16–256 多分辨率)——EXE 图标,`padpd_qt.spec`
  自动引用;
- `gui_qt/assets/padpd.png`(512, 圆角透明)——随包分发,作为窗口/任务栏
  图标(`gui_qt/main.py` 设置)。

换图标只需替换 `source.png` 后重跑该脚本。

## 重要限制:PyInstaller 不能跨平台

PyInstaller 只能在**目标平台上**构建目标平台的产物:

- Windows `.exe` → 必须在 Windows 上构建;
- Linux 可执行 → 在 Linux 上构建(本仓库已在 Linux 上冒烟验证同一份
  spec);
- macOS `.app` → 在 macOS 上构建。

## Windows 构建步骤

1. 安装 Python 3.10–3.12(勾选 "Add python to PATH")。
2. 克隆本仓库,进入 `packaging/` 目录。
3. 双击或在终端运行:

   ```bat
   build_windows.bat            :: 完整版(含 torch,产物约 2 GB)
   build_windows.bat --no-torch :: 精简版(约 400 MB)
   ```

4. 产物在 `packaging/dist/padpd-desktop/`,把整个目录拷走即可,
   入口是 `padpd-desktop.exe`(onedir 模式,启动快、杀软误报少)。

### 完整版 vs 精简版

| | 精简版 `--no-torch` | 完整版 |
|---|---|---|
| 波形/CFR/数据加载 | ✅ | ✅ |
| 经典建模(MP/GMP/DDR)+ ILA DPD | ✅ | ✅ |
| 定点位宽扫描 / 整数系数 / 参考向量导出 | ✅ | ✅ |
| 离散 Pareto 联合设计 | ✅ | ✅ |
| 神经建模(GRU/DGRU/TCN)/ DLA / ONNX / 梯度寻优 | ❌(界面提示缺 torch) | ✅ |
| 体积(onedir) | ~400 MB | ~2 GB(CPU 版 torch) |

完整版请先装 **CPU 版 torch**(`pip install torch --index-url
https://download.pytorch.org/whl/cpu`),否则 PyInstaller 会把几个 GB 的
CUDA 运行库一起打进去。

## 方式二:Nuitka 单文件构建(single .exe,仅精简版)

想要**一个 exe 文件**(而非整目录)分发时,用 Nuitka:

```bat
:: 在 Windows 上,从 packaging/ 运行
build_windows_nuitka.bat
```

产物是**单个** `packaging\build_nuitka\padpd-desktop.exe`,双击即运行。
Nuitka 把 Python 编译成 C 再链接,启动后把自身解压到 `%TEMP%`。

单文件 vs onedir 取舍:

| | PyInstaller onedir(方式一) | Nuitka onefile(方式二) |
|---|---|---|
| 产物 | 一个目录、几百个文件 | **单个 .exe** |
| 分发 | 拷整目录 / zip | 拷一个文件 |
| 首次启动 | 快 | 略慢(解压到 %TEMP%) |
| torch 完整版 | ✅ 支持 | ❌ 仅精简版(见下) |
| 构建时长 | 快(几分钟) | 慢(10–30 min,编译 C) |

**为什么只做精简版**:onefile 每次启动都要把内容解压到临时目录,塞进
几 GB 的 torch 会让体积和首启都不可接受。需要神经功能的完整版请用
方式一(PyInstaller)。Nuitka 同样**不能跨平台**——Windows exe 必须在
Windows 上构建。

## Linux 冒烟验证(本仓库 CI/开发环境)

PyInstaller:

```bash
cd packaging
PADPD_NO_TORCH=1 python -m PyInstaller --clean --noconfirm padpd_qt.spec
QT_QPA_PLATFORM=offscreen ./dist/padpd-desktop/padpd-desktop   # 应正常启动
```

Nuitka onefile(Linux 需先 `apt-get install patchelf`;`pip install
"nuitka[onefile]"`):同一命令去掉 `--windows-*`、加 `--linux-icon`,
从仓库根运行,产物 `packaging/build_nuitka/padpd-desktop`,
`QT_QPA_PLATFORM=offscreen` 下启动冒烟。

## Streamlit Web 版怎么“打包”?

Web 版(`gui/`)定位是工作台/团队共享,不做 exe:任何有 Python 的机器

```bash
pip install -e .[gui]
streamlit run gui/app.py
```

需要“像应用一样”的单机入口时,直接用桌面版(两版共享 `gui_runs/`
实验注册表,数据互通)。

## 常见问题

- **杀毒软件报警**:PyInstaller onedir 产物偶发误报,把目录加入白名单
  或改用 `--no-torch` 精简版(体积小误报少)。
- **启动报缺 DLL(Windows Server / 精简系统)**:安装
  "Microsoft Visual C++ Redistributable x64"。
- **图中文字变方框**:系统需有中文字体(Windows 自带微软雅黑,无需处理;
  精简 Linux 需 `fonts-wqy-zenhei` 之类)。
- **Nuitka 单文件首次启动慢**:onefile 每次运行先解压到 `%TEMP%`,首启
  比 onedir 慢几秒,之后正常;对启动速度敏感就用方式一的 onedir。杀软
  对单文件自解压偶有误报,同样加白名单即可。
