# API 参考

从模块 docstring 与函数签名自动生成。这个库的 docstring 里保存了大量
**设计理由与失败记录**(为什么某条路走不通、天花板在哪),建议连同
签名一起读。

| 模块 | 内容 |
|---|---|
| [waveform](waveform.md) | OFDM 波形生成与解调、QAM 星座 |
| [pa](pa.md) | PA 行为模型:经典、样条族、虚拟 DUT |
| [dpd](dpd.md) | ILA / 自适应 / QMC / 直接学习 |
| [data](data.md) | 数据容器、加载器、对齐、观测去嵌 |
| [metrics](metrics.md) | EVM / ACLR / PSD / Mask / OpenDPD 口径 |
| [deploy](deploy.md) | 定点、LUT、RTL、ONNX 与系数导出 |
| [表征与环路](analysis.md) | 双音诊断、增益调制辨识、环回、三环、CFR |
