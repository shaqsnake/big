---
title: '原型 capture evidence 记录'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-settle-window.md'
---

# 原型 capture evidence 记录

## Intent

**问题：** `big commit` 已经会把输入和输出文件复制到 staging，并发布为只读 CAS 对象，但仅有 CAS hash 不能解释 capture 当时的稳定性证据。后续排查 EDA 写入冲突、手工复核 manifest 或设计更强 quiet-state 机制时，需要知道每个 FileRef 在复制前后看到的基础文件状态。

**方案：** 在 `stable_copy_to_staging` 中记录源文件复制前后的 stat 快照，包括 size、mtime_ns、ctime_ns、inode 以及平台缺失字段；在 `file_refs` 表中新增 `capture_evidence_json`，随 FileRef 一起落库。`big show --full` 为每个文件展示简短 evidence 摘要，便于人工复核。

## Boundaries

- 本切片只记录证据，不把 evidence 当成强一致性证明。
- commit 仍然只通过 size 和 mtime_ns 判断复制期间文件是否变化；ctime 和 inode 仅作为诊断信息。
- evidence 不包含源文件绝对路径，避免把机器本地路径放入 manifest 细节。
- SQLite schema 以追加列方式兼容已有本地原型仓库。
- 本切片不实现 NAS/filesystem snapshot、外部 EDA 进程锁定或生产级事务提交。

## Acceptance

- Given 用户执行 `big commit`
- When 每个 input/output 被复制到 staging
- Then BIG 记录该文件复制前后的 stat 快照，并把 evidence 写入对应 FileRef。

- Given 用户执行 `big show <version> --full`
- When version 中存在带 evidence 的 FileRef
- Then 输出每个文件的 `capture_evidence` 摘要，包括 before/after size 与 mtime_ns。

- Given 旧仓库的 `file_refs` 表没有 `capture_evidence_json`
- When BIG 初始化 metadata schema
- Then 自动补充该列，并让旧 FileRef 在展示时显示 evidence unavailable。

## Verification

- `python -m py_compile src/big/cas.py src/big/cli.py src/big/metadata.py`
- `python -m pytest tests/test_cli_prototype.py::test_repo_init_commit_log_show_and_diff`
- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/CaptureEvidenceSmoke --repo-id CaptureEvidenceSmoke`
