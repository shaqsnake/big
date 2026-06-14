---
title: '原型 checkout 目录上下文识别'
type: 'fix'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-shell-init.md'
---

# 原型 checkout 目录上下文识别

## Intent

**问题：** `big checkout <branch>` 已经能物化到 `.big-checkouts/<flow>/<branch>/<version>`，但进入目标目录后，CLI 仍按普通 `/user/<user>/<flow>` 规则解析路径，会把 flow 误判为 `.big-checkouts`，导致 `status`、`log` 和后续默认 `commit` 指向错误 ref。

**方案：** CLI 在解析当前上下文时优先向上查找 `.big-checkout.json` marker。若 marker 属于当前 repo 且指向当前目录，则使用 marker 中的 user、flow、branch、version 生成 checkout workspace context，并把默认 ref 设置为 marker 中的 branch。

## Boundaries

- 不改变普通 `/user/<user>/<flow>` workspace 的解析规则。
- 不改变 checkout 目录结构、CAS 物化方式或 shell wrapper 行为。
- 只识别由 BIG 原型写入的 schema 1 copy marker；marker 损坏或 repo 不匹配时拒绝继续，避免静默写错 ref。
- 本 checkout context 切片不负责显式 `restore --in-place`；workspace generation 由 restore 切片维护。

## Acceptance

- Given 用户位于 `big checkout feature/place` 物化出的目标目录
- When 执行 `big status`
- Then 输出 `default_ref: feature/place`，并显示 checkout workspace id。

- Given 用户位于同一 checkout 目录
- When 执行 `big log`
- Then 默认显示 `feature/place` 的历史。

- Given 用户位于同一 checkout 目录并执行 `big commit`
- Then 新版本写入 `feature/place`，而不是写入 `workspace/default/<user>/.big-checkouts`。
