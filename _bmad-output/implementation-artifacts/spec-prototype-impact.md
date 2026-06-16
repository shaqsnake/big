---
title: '原型下游 impact 查询'
type: 'feature'
created: '2026-06-16'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cross-branch-consumes.md'
---

# 原型下游 impact 查询

## Intent

**问题：** 原型已经可以通过 `--cross-branch-input` 记录 `provenance_edges(consumes)`，也可以在 `lineage` 中从下游向上游查看 consumes 关系。但当某个上游 version 被修改、回退或准备降级时，工程师还需要反向查看哪些下游 version 直接或间接依赖它。

**方案：** 增加 `big impact <version> [--depth N] [--verbose]`。命令先校验目标 version read 权限，再按 `provenance_edges.upstream_version_id` 查询下游 consumes 边。默认 `--depth 1` 只显示直接下游；增加 depth 时按层递归展开，并用 visited set 防止环或重复节点。输出区分 visible 与 restricted downstream，避免把无权限节点误报为无影响。

## Boundaries

- 本切片只基于显式 `consumes` 边查询 impact，不自动扫描 EDA 文件内容、日志或目录。
- 本切片不实现 GUI DAG、不实现大结果分页/导出，也不实现跨站点 impact。
- 无权限下游只输出受限占位符和计数，不泄露 version ID、branch、step、path 或状态。
- `--verbose` 展示 edge evidence 摘要，例如 CLI 提供的 evidence path；`--full` 当前与 verbose 等价，保留给后续完整展开。

## Acceptance

- Given 上游 version 存在直接下游 consumes 边
- When 执行 `big impact <upstream-version>`
- Then 输出下游 version ID、edge 类型、上游 branch、下游 branch、step 和状态。

- Given 下游 version 继续被第三个 version 消费
- When 执行 `big impact <upstream-version> --depth 2`
- Then 输出第二层下游 version
- And 不重复输出已访问节点。

- Given 用户使用 `--verbose`
- When 输出 impact 结果
- Then 每条可见边显示 evidence path、actor 和 created_at 摘要。

- Given 上游 version 没有任何可见或受限下游
- When 执行 `big impact <version>`
- Then 输出 `no visible downstream impact`。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/ImpactSmoke --repo-id ImpactSmoke`
- `python -m big impact --help`
