---
title: '原型从历史版本 checkout 新分支'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

# 原型从历史版本 checkout 新分支

## Intent

**问题：** 原型已经支持 `big checkout <branch>`，但还不能覆盖 MVP FR6 中“从历史版本重新出发”的日常路径。用户只能先 `branch create --from <version>`，再 checkout 新分支，流程比规划中的 `big checkout <version> --new-branch <name>` 更绕。

**方案：** 扩展 `big checkout`：当目标 ref 是 version 且提供 `--new-branch <branch>` 时，先解析历史 version 和目标路径；`--plan` 只预览，不创建 branch 或目录；真实 checkout 成功物化目录后，创建命名 branch，head 指向该历史 version。

## Boundaries

- 不带 `--new-branch` 时，直接 checkout version 会被拒绝，避免用户误以为会原地回退。
- `--plan` 不创建 branch，不创建目录。
- 真实 checkout 先完成 copy-only 物化，再登记新 branch；不改写源 workspace。
- 本历史版本 checkout 切片不负责 `restore --in-place`、subset checkout、branch ACL enforcement 或 workspace generation；新分支 ACL 元数据默认值由 branch ACL 切片覆盖。

## Acceptance

- Given 一个已存在 version
- When 执行 `big checkout <version> --new-branch from-v1 --plan`
- Then 输出目标路径、`branch_created: plan-only`，且 branch `from-v1` 不存在。

- Given 同一个 version
- When 执行 `big checkout <version> --new-branch from-v1`
- Then 创建 checkout 目录，写入 marker，创建 branch `from-v1`，head 指向该 version。

- Given branch `from-v1` 已存在
- When 再次执行同一命令
- Then BIG 拒绝创建，避免覆盖已有 branch 语义。
