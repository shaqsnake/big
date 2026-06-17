---
title: '原型 lineage depth 参数别名'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-parent-chain.md'
---

# 原型 lineage depth 参数别名

## Intent

**问题：** Story 3.4 要求 lineage 长链查询支持 `--depth` 或等价参数。原型已有 `--limit` 可以限制 parent-chain 节点数，但从血缘查询语义看，`--depth` 更贴近用户直觉，也方便后续与 `big impact --depth` 保持一致。

**方案：** 为现有 `big lineage <version> --limit N` 增加 `--depth N` 别名，两个参数映射到同一实现，不改变默认值、截断逻辑或输出格式。

## Boundaries

- 本切片只增加 CLI 参数别名，不改变 lineage 查询算法。
- `--depth` 当前语义等同于 parent-chain 最大节点数；后续如果支持完整 DAG depth，可再拆分概念。
- 同时保留 `--limit`，避免破坏已有脚本。

## Acceptance

- Given 用户执行 `big lineage <version> --depth 1`
- When parent chain 超过 1 个节点
- Then 输出 `entries: 1` 和 `truncated: yes`。

- Given 用户执行 `big lineage <version> --limit 1`
- When parent chain 超过 1 个节点
- Then 行为与 `--depth 1` 保持一致。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_repo_init_commit_log_show_and_diff`
- `python -m pytest`
