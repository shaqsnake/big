---
title: '原型 commit settle window 检查'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-success-marker.md'
---

# 原型 commit settle window 检查

## Intent

**问题：** EDA 工具可能在工程师执行 `big commit` 时仍在读写目标文件。BIG 不能宣称源目录天然被锁住，但至少应在 capture 前验证候选文件在一个短窗口内没有变化，避免把明显正在写入的文件打包进 manifest。

**方案：** 在 `big.toml` 中增加 `[capture].settle_ms`，并提供 `big commit --settle-ms <ms>` 临时覆盖。commit 解析 inputs/outputs 后，对候选文件读取 size、mtime、ctime 和 inode 等平台可得元数据，等待 settle window，再读取一次；如果窗口内发生变化，则拒绝 commit，不创建可见 version。

## Boundaries

- 本切片只实现 commit 前的候选文件 settle 检查，不实现 NAS/filesystem snapshot，也不证明整个源目录具备事务级一致性。
- 检查范围仅限本次 inputs/outputs 解析出的文件集合；外部 success marker 不作为被 capture 文件参与 settle 检查。
- 检测到变化时直接拒绝 commit；本切片不实现自动重试。
- `settle_ms = 0` 表示不启用 settle window，保持原有 best-effort 行为。

## Acceptance

- Given `big.toml` 配置 `[capture] settle_ms = 25`
- When 用户执行 `big commit`
- Then BIG 在 capture 前等待 25ms，并确认候选 inputs/outputs 的稳定性元数据未变化。

- Given 候选文件在 settle window 内变化
- When 用户执行 `big commit`
- Then BIG 拒绝 commit
- And 输出 `Files changed during settle window`、变化文件路径和变化字段。

- Given 用户传入 `big commit --settle-ms 1`
- When 项目配置了其它 settle window
- Then 本次 commit 使用 CLI 参数覆盖项目配置，并在 summary 中输出 `settle_ms: 1`。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/SettleWindowSmoke --repo-id SettleWindowSmoke`
- `python -m big commit --help`
