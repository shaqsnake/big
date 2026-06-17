---
title: '原型 derived_from lineage 展示'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-restore-in-place.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-details.md'
---

# 原型 derived_from lineage 展示

## Intent

**问题：** FR14 和 Story 3.4 要求系统能表达制品集之间的 `derived_from` 语义关系，例如从早期版本 restore 后重新生成的新版本。原型已经在 restore 后的 commit 中记录 `restored_from_version_id`、`restore_journal_id` 和 workspace generation，但 lineage 输出只显示 `restored_from`，业务语义不够直观。

**方案：** 在 `big lineage` 中，当某个 version 带有 `restored_from_version_id` 时，同时输出 `derived_from: <version>`。这复用现有 restore provenance，不引入新的边表或自动推断。

## Boundaries

- 本切片只增强 lineage 展示，不改变 version schema 或 restore 事务。
- `derived_from` 当前仅覆盖显式 restore 后继续 commit 的场景。
- branch-from-version、跨 work root 推断和完整 DAG 建模留待后续设计。
- `restored_from` 和 `restore_journal` 仍保留，便于审计和故障排查。

## Acceptance

- Given 用户执行 `big restore --in-place <old-version>` 后继续 commit
- When 用户执行 `big lineage <new-version>`
- Then 新 version 节点显示 `derived_from: <old-version>`
- And 仍显示 `restored_from`、`restore_journal` 和 `workspace_generation`。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_restore_in_place_rewrites_clean_workspace_with_journal`
- `python -m pytest`
