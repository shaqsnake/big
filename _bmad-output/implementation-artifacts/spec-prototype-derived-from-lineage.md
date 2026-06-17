---
title: '原型 derived_from lineage 记录'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-restore-in-place.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-details.md'
---

# 原型 derived_from lineage 记录

## Intent

**问题：** FR14 和 Story 3.4 要求系统能表达制品集之间的 `derived_from` 语义关系，例如从早期版本 restore 后重新生成的新版本，或从历史 version 创建新分支后继续生成的新版本。原型已有 `restored_from_version_id` 和 branch source metadata，但还没有独立 version 字段承载通用 `derived_from` 关系。

**方案：** 在 `versions` 表中新增 `derived_from_version_id`。`big commit` 创建 version 时优先使用 restore provenance；如果没有 restore provenance，则当目标 branch 的 `source_version_id` 等于当前 parent head 时，把 branch source version 记录为 `derived_from`。`big commit`、`big show`、`big log --verbose` 和 `big lineage` 都展示该字段。

## Boundaries

- 本切片只记录显式来源，不自动扫描 EDA 文件或推断隐式数据依赖。
- `derived_from` 不替代 `parent_id`；新版本仍保留 parent-chain 祖先关系。
- 跨 work root 推断和完整 DAG 建模留待后续设计。
- `restored_from` 和 `restore_journal` 仍保留，便于审计和故障排查。

## Acceptance

- Given 用户执行 `big restore --in-place <old-version>` 后继续 commit
- When 用户执行 `big lineage <new-version>`
- Then 新 version 节点显示 `derived_from: <old-version>`
- And 仍显示 `restored_from`、`restore_journal` 和 `workspace_generation`。

- Given 用户从历史 version 创建 branch 后第一次 commit
- When branch source version 等于本次 commit 的 parent
- Then 新 version 记录并显示 `derived_from: <source-version>`
- And 不显示 `restored_from`。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m py_compile src/big/metadata.py`
- `python -m pytest tests/test_cli_prototype.py::test_commit_records_branch_source_as_derived_from`
- `python -m pytest tests/test_cli_prototype.py::test_restore_in_place_rewrites_clean_workspace_with_journal`
- `python -m pytest`
