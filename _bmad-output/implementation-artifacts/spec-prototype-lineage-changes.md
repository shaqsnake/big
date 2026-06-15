---
title: '原型 lineage recipe/input 变化摘要'
type: 'feature'
created: '2026-06-15'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-lineage-parent-chain.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cross-branch-consumes.md'
---

# 原型 lineage recipe/input 变化摘要

## Intent

**问题：** `big lineage` 已经能显示 parent chain 和直接 `consumes` 上游边，但工程师仍需要快速判断血缘链上哪一次提交改变了影响 recipe 的输入文件。单独执行 `big diff` 可以比较两个 version，但不能在一条 lineage tree 里连续展示每个节点相对 parent 的 recipe/input 变化。

**方案：** 为 `big lineage` 增加 `--changes`。命令对 parent-chain 中每个可见节点读取当前 version 和 parent version 的 `input` FileRef，比较 `recipe_hash` 与 input path/hash，输出 `recipe_change`、inputs added/removed/modified 数量和 changed input 摘要。默认只展示少量高影响 input；`--verbose` 展示更多；`--full` 展开全部 changed inputs。

## Boundaries

- 本切片只比较 `role = input` 的 FileRef，不比较 outputs，也不把 lifecycle/retention 状态变化计入 recipe 变化。
- 本切片不做文本级 diff，不解析 Tcl/SDC 内容，只展示 path、hash、size、semantic_role 和 format_hint。
- 本切片把 `consumes` 作为数据依赖边展示，不把跨分支 consumes 输入变化误解释为同一 branch parent 修改。
- 如果 parent version 不可见或无法读取，`--changes` 输出受限/不可用占位符，不泄露路径或 hash 细节。

## Acceptance

- Given 一个 version 的 input hash 相比 parent 发生变化
- When 执行 `big lineage <version> --changes --verbose`
- Then 对应节点输出 `recipe_change: changed`
- And 输出 `input_changes: added=... removed=... modified=...`
- And changed input 摘要包含路径、旧 hash、新 hash、大小变化和 semantic_role/format_hint。

- Given 一个 version 只改变 outputs，inputs 和 recipe_hash 不变
- When 执行 `big lineage <version> --changes`
- Then 输出 `recipe_change: unchanged`
- And 输入变化数量均为 0
- And 不展示 output 文件路径。

- Given changed inputs 中包含脚本、配置、SDC、runset 等高影响输入
- When 默认输出变化摘要
- Then 这些输入优先出现在 changed input 摘要中。

- Given 用户使用 `--full`
- When changed inputs 超过默认摘要数量
- Then CLI 展开所有 changed inputs，不再提示剩余数量。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/LineageChangesSmoke --repo-id LineageChangesSmoke`
- `python -m big lineage --help`
