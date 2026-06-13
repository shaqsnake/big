---
title: '原型 checkout copy-only 物化'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-plan.md'
---

# 原型 checkout copy-only 物化

## Intent

**问题：** 原型已经能用 `big checkout <branch> --plan` 解析目标路径，但还不能让用户进入一个真实可查看的 checkout 目录验证制品集内容。

**方案：** 在不带 `--plan` 时，将目标 branch head version 的 FileRef 从只读 CAS 复制到用户私有目录 `<work_root>/user/<user>/.big-checkouts/<flow>/<safe-branch>/<version>`，并写入 `.big-checkout.json` marker。再次 checkout 同一 repo、branch、version 时复用已有目录。

## Boundaries

- 只实现 copy-only 物化，不创建硬链接或符号链接，不暴露可写 CAS。
- 物化前校验 CAS 对象存在、大小一致且 SHA-256 匹配。
- `--plan` 仍只输出路径，不创建目标目录。
- 不移动 branch head，不改写源 workspace，不实现 in-place restore，不登记 workspace generation。
- 如果目标目录已存在但 marker 不匹配，拒绝覆盖，避免破坏用户已有数据。

## Review Order

1. [../../src/big/cli.py](../../src/big/cli.py) -- checkout 物化 helper、CAS 校验、marker 复用和命令输出。
2. [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 端到端验证 plan、copied、reused 和复制后的文件内容。
3. [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- WSL 手工测试中的 checkout 用例。

## Acceptance

- Given 已存在命名 branch `feature/place`
- When 执行 `big checkout feature/place --plan`
- Then 只输出目标路径和 head version，不创建目标目录。

- Given 同一 branch head version 的 CAS 对象完整
- When 执行 `big checkout feature/place`
- Then 目标目录被创建，FileRef 对应文件被复制，输出 `materialization: copied`。

- Given 目标目录已有匹配 marker
- When 再次执行 `big checkout feature/place`
- Then 输出 `materialization: reused`，不重复覆盖目录。
