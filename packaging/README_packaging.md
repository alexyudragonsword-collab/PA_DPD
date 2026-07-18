# padpd 桌面版打包说明(PyInstaller)

把 PySide6 桌面 GUI(`gui_qt/`)打成免安装的可执行程序。

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

## Linux 冒烟验证(本仓库 CI/开发环境)

```bash
cd packaging
PADPD_NO_TORCH=1 python -m PyInstaller --clean --noconfirm padpd_qt.spec
QT_QPA_PLATFORM=offscreen ./dist/padpd-desktop/padpd-desktop   # 应正常启动
```

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
