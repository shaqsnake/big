---
title: '原型 lineage 详情展开'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cross-branch-consumes.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-parent-chain.md'
---

# 原型 lineage 详情展开

## Intent

**问题：** Story 3.4 要求 lineage 在 verbose/full 模式下展示每个节点的作者、时间、recipe_hash、状态和边类型，并能展开 consumes 边的 evidence。原型此前默认 tree 能显示 parent 链和 consumes 上游，但 verbose/full 没有额外节点详情，也无法直接看到 consumes 对应的 FileRef hash 与 manifest 摘要。

**方案：** 保持默认 `big lineage <version>` 简洁输出不变；当使用 `--verbose` 或 `--full` 时，为每个节点输出 `edge_type`、author、created_at、recipe_hash 和 manifest_hash。`--full` 对 consumes 边额外输出 upstream manifest 摘要、evidence path 对应的 FileRef role/path/hash/size，以及原始 evidence JSON。

## Boundaries

- 本切片只增强只读 lineage 输出，不改变 provenance_edge 数据模型。
- `edge_type: target` 表示查询起点，`edge_type: parent` 表示 parent-chain 上的祖先节点；consumes 边仍在独立 `consumes:` 区块展示。
- 只有用户对 upstream version 有 read 权限时才展开 evidence 详情。
- 当前 evidence JSON 仍来源于 MVP 的 `--cross-branch-input VERSION[:PATH]` 显式声明，不自动扫描 EDA 文件内容。

## Acceptance

- Given 用户执行 `big lineage <version> --verbose`
- When lineage 包含 parent-chain 节点
- Then 每个节点显示 edge_type、author、created_at、recipe_hash 和 manifest_hash。

- Given lineage 包含 consumes 边
- When 用户执行 `big lineage <version> --full`
- Then consumes 边显示 upstream author、recipe_hash、evidence manifest、evidence FileRef 摘要和 evidence JSON。

- Given 用户执行默认 `big lineage <version>`
- When lineage 输出完成
- Then 默认 tree 仍保持简洁，不强制展开所有详情。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_commit_can_record_cross_branch_consumes_lineage`
- `python -m pytest`
