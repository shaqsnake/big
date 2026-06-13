---
title: '原型 checkout 目标解析'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-3dic-workroots.md'
---

# 原型 checkout 目标解析

## Intent

**Problem:** 原型已经能创建命名 branch，但还不能验证 checkout 的第一步：从当前 workspace 解析目标 branch head version，并计算一个不改写源目录的用户私有稳定目标路径。

**Approach:** 增加 `big checkout <branch> --plan`。该命令解析当前 repo/work root/user/flow、目标 branch head version，并输出 plan-only 的目标路径和可复制执行的 `cd -- <target-path>`。当前切片不复制 CAS 文件、不创建目标目录、不登记 workspace generation，也不改变父 shell cwd。

## 边界

- 目标路径模板为 `<work_root>/user/<user>/.big-checkouts/<flow>/<safe-branch>/<version>`。
- 目标路径位于当前 work root 的用户私有命名空间下，不等于当前 flow workspace。
- 未传 `--plan` 时明确拒绝，避免用户误以为已经完成物化。

## Suggested Review Order

- [../../src/big/cli.py](../../src/big/cli.py) -- 先看 `checkout --plan` 的 branch/head 解析、路径模板和未实现物化保护。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 确认 plan 输出目标路径且不创建目录。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看手工说明是否明确 plan-only 边界。
