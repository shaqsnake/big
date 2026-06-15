---
title: '原型跨分支 consumes 血缘边'
type: 'feature'
created: '2026-06-15'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-parent-chain.md'
---

# 原型跨分支 consumes 血缘边

## Intent

**问题：** FR34 要求 MVP 可以表达一个分支的输出被另一个分支作为输入。此前原型只有 commit parent chain 和 restore provenance，无法记录跨分支数据依赖；`big lineage` 也只能显示同一 branch 的 parent 链。

**方案：** 在 metadata 中新增 `provenance_edges` 表，使用 `edge_type = "consumes"` 表达下游 version 显式消费上游 version。`big commit` 增加 `--cross-branch-input <version>[:path]`，在创建 version 的同一事务中写入 consumes 边；`path` 是可选 evidence，用来记录人类可读的上游文件或产物路径。`big lineage` 在 parent chain 节点下显示直接 consumes 上游边，并保持 consumes 与 parent 的输出层级分离。

## Boundaries

- 本切片只实现用户显式声明的 `consumes` 边，不自动扫描 EDA 文件、脚本或日志推断依赖。
- 本切片不实现 `derived_from` 独立边表、不实现下游影响分析、不实现跨 work root 联动查询，也不实现 Growth 阶段的完整 DAG UI。
- `--cross-branch-input` 必须能解析到唯一上游 version，且当前用户需要有该 version 所属 branch 的 read 权限。
- `lineage` 显示 consumes 上游时，如果上游 version 不可读，输出受限占位符，不泄露上游 branch、step、path 或状态细节。
- consumes 边写入与 version、FileRef、audit 同属 `create_version` 元数据事务。

## Acceptance

- Given alice workspace 已提交 APR version
- When bob workspace 执行 `big commit --cross-branch-input <alice-version>:outputs/top.def`
- Then 新 version 创建成功，CLI 输出 `cross_branch_inputs: 1`。

- Given 下游 version 存在 consumes 边
- When 用户执行 `big lineage <downstream-version>`
- Then parent chain 仍显示下游自身 branch 的 commit parent
- And 该节点下输出 `consumes:`，列出上游 version、`edge=consumes`、上游 branch、step、path 和状态。

- Given `--cross-branch-input` 引用了不存在或歧义的 version
- When 用户执行 commit
- Then 系统拒绝创建 version，并提示 cross-branch input version 无法解析。

- Given 上游 version 所属 branch 对当前用户不可读
- When 用户执行 commit 或 lineage
- Then commit 拒绝写入；lineage 仅显示受限占位符。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/CrossBranchSmoke --repo-id CrossBranchSmoke`
- `python -m big commit --help`
- `python -m big lineage --help`
