# Project Cairn 日志

本文件按倒序记录实质进展——最新条目紧跟本行之下。每条保持简短,只写摘要
与指针;结论沉淀进 `cairn/<topic>.md`。

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
