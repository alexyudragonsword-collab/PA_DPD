# 7. 部署与打包

## 7.1 定点位宽扫描

部署页对已拟合模型做 **bit-true 定点仿真**:系数与激活按 2 的幂缩放
对称量化,在测试数据上复算 NMSE。勾选模型与位宽(W16–W8)即可得到
"位宽 vs 精度"曲线与浮点基线虚线,用于确定硬件位宽边界。

经验结论(见第 6 章表格):神经 TCN 可压到 W10–W12 仍几乎无损;
多项式模型 W16 安全、W12 以下显著劣化。

![位宽扫描](assets/qt_deploy.png)

## 7.2 FPGA/ASIC 交接产物

"导出交接产物"生成三件套:

| 产物 | 内容 | 用途 |
|---|---|---|
| 整数系数 JSON | 量化后的整数系数 + 缩放因子 + 结构描述 | RTL 系数 ROM |
| 参考向量 CSV | bit-true 输入/输出样本序列 | RTL 仿真逐样本比对 |
| ONNX(神经模型) | 标准计算图,含数值验证(max err ~1e-6) | 工具链/加速器导入 |

命令行等价入口:`python scripts/export_deploy.py`、
`scripts/quantize_dpd.py`、`scripts/quantize_neural_pa.py`。

## 7.3 桌面版打包为 Windows exe

**推荐方式:GitHub Actions 云端构建(无需本地 Windows)**——仓库
Actions 页运行 **Build Windows EXE** 工作流,完成后从 Artifacts 下载
`padpd-desktop-windows-slim.zip`(精简)或 `-full.zip`(含 CPU torch);
推送 `v*` tag 则自动构建并附到 GitHub Release。云端构建包含 20 秒
启动冒烟,失败会直接标红。

也可在本地 Windows 用 PyInstaller 打成免安装目录(onedir):

```bat
cd packaging
build_windows.bat            :: 完整版(含 torch,约 2 GB)
build_windows.bat --no-torch :: 精简版(约 400 MB,经典功能全可用)
```

产物在 `packaging/dist/padpd-desktop/`,入口 `padpd-desktop.exe`,
整个目录拷贝即可分发。

**关键限制:PyInstaller 不能跨平台**——Windows exe 必须在 Windows 上
构建(本仓库已在 Linux 用同一份 spec 验证过构建与启动)。

| | 精简版 --no-torch | 完整版 |
|---|---|---|
| 波形 / CFR / 数据 / 经典建模 / ILA / 定点导出 / 离散联合设计 | ✅ | ✅ |
| 神经建模 / DLA / ONNX / 梯度寻优 | ❌(界面提示) | ✅ |
| 体积 | ~400 MB | ~2 GB |

完整版建议先装 **CPU 版 torch**(`pip install torch --index-url
https://download.pytorch.org/whl/cpu`),避免把数 GB CUDA 运行库打进包。

其余细节(杀软误报、缺 DLL、中文字体)见
`packaging/README_packaging.md`。

## 7.4 Web 版部署

Web 版定位为团队工作台,不做 exe:任何有 Python 的机器
`pip install -e .[gui] && streamlit run gui/app.py` 即可;局域网共享
加 `--server.address 0.0.0.0`。两版共享 `gui_runs/` 注册表。

## 7.5 QAT 与 RTL 生成(硅前落地)

**量化感知训练**(`padpd.deploy.qat`):低位宽下 PTQ 直接舍入会掉精度;
QAT 在微调中插入与部署量化器逐位一致的 fake-quant(直通估计),让浮点
权重适配目标网格,再在同位宽 PTQ 即可回收精度。`scripts/run_qat_demo.py`
给出 W10..W6 的 PTQ vs QAT 对比表。

**RTL 生成器**(`padpd.deploy.rtl`)⭐:把定点 DPD 系数点积生成为可综合
的复数 MAC Verilog(系数烧成 ROM,占 DSP 面积主体)+ 自检 testbench,
用 Icarus Verilog **逐位验证**对 Python 整数金标准(39 抽头 GMP × 64
向量 → 0 错误)。经典模型在部署页"生成产物"时会一并产出
`rtl/dpd_mac.v` 并报告 bit-true 通过。基函数生成前端(延迟、|x|^k)
作为独立块。
