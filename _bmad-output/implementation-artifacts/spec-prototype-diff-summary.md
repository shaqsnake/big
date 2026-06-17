---
title: '原型 diff 摘要增强'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
---

# 原型 diff 摘要增强

## Intent

**问题：** Story 3.3 要求 `big diff` 能区分 recipe、manifest、inputs、outputs 和生命周期状态变化。原型此前只输出 recipe_hash 是否变化以及全量 added/removed/modified 数量，工程师需要从 verbose 路径列表里自行判断 input/output 变化，也看不到 review/retention 状态是否只是元数据变化。

**方案：** 在默认 diff 摘要中增加 `manifest_hash` 状态、`review_state`/`retention_state` 变化，以及 input/output 分角色 added/removed/modified 计数。`--verbose` 和 `--full` 继续渐进展开路径级 FileRef 差异。

## Boundaries

- 本切片只增强只读 diff 输出，不改变 version、manifest、CAS 或生命周期元数据。
- 状态变化与 recipe/manifest 变化分开展示；不把 review/retention 变化计入 FileRef diff。
- 文件级 diff 仍只比较 FileRef 的 CAS hash、size 和 path，不做文本级内容 diff。
- 分角色计数仍基于当前 MVP 的 `input` 与 `output` 两类。

## Acceptance

- Given 两个 version 的 recipe_hash 不同
- When 用户执行 `big diff`
- Then 输出 `recipe_hash: changed`，并显示 input/output 分角色变化计数。

- Given 两个 version 的 manifest_hash 相同但 review_state 不同
- When 用户执行 `big diff`
- Then 输出 `manifest_hash: unchanged`、`review_state: old->new`，并保持 FileRef added/removed/modified 为 0。

- Given 用户使用 `--verbose`
- When 存在路径级变化
- Then 继续展示 added、removed 和 modified FileRef 摘要。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_repo_init_commit_log_show_and_diff`
- `python -m pytest tests/test_cli_prototype.py::test_diff_separates_state_changes_from_manifest_changes`
- `python -m pytest`
