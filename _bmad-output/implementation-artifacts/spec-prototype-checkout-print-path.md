---
title: '原型 checkout print-path 输出模式'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-shell-init.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture.md'
---

# 原型 checkout print-path 输出模式

## Intent

**问题：** `big checkout` 已经输出 `target_path` 和 `cd:`，但这是面向人阅读的多行文本。shell 集成、脚本和非交互流程需要一个只输出目标路径的稳定接口，避免解析人类摘要字段。

**方案：** 为 `big checkout` 增加 `--print-path`。该参数只改变输出格式，不改变 checkout 语义：不带 `--plan` 时仍会物化或复用目录；带 `--plan` 时只解析路径且无副作用。

## Boundaries

- `--print-path` 不是新的 dry-run 语义；是否有副作用仍由 `--plan` 决定。
- `big checkout <branch> --plan --print-path` 只打印路径，不创建目录。
- `big checkout <branch> --print-path` 会执行正常 checkout 物化/复用，然后只打印路径。
- `big checkout <version> --new-branch <name> --print-path` 同样遵守 `--new-branch` 和 `--plan` 规则。
- 不修改 shell wrapper 实现；该模式先作为通用脚本底座提供。

## Acceptance

- Given 已存在 branch `feature/place`
- When 执行 `big checkout feature/place --plan --print-path`
- Then 只输出目标路径，目标目录不存在。

- Given 同一 branch
- When 执行 `big checkout feature/place --print-path`
- Then 目标目录被物化或复用，stdout 只包含目标路径。

- Given 已存在历史 version
- When 执行 `big checkout <version> --new-branch from-v1 --plan --print-path`
- Then 只输出 `from-v1` 的目标路径，不创建 branch。
