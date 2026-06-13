---
title: '原型分支事件查看'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-reset.md'
---

# 原型分支事件查看

## Intent

**Problem:** `big reset` 已经会记录最小 `branch_events` 审计事件，但用户只能通过测试或数据库直接确认；手工测试时无法方便地查看某个 ref 是否发生过 head 移动。

**Approach:** 增加只读命令 `big branch events [branch] --limit N`。未指定 branch 时解析当前 workspace-private ref；输出 reset 事件的 branch、old head、new head、actor、时间和 reason。该切片只暴露已有事件，不实现完整 append-only hash-chain audit、不改变 reset、branch 或权限语义。

## Suggested Review Order

- [../../src/big/cli.py](../../src/big/cli.py) -- 先看 `branch events` 的默认 ref 解析、无事件提示和输出字段。
- [../../src/big/metadata.py](../../src/big/metadata.py) -- 确认事件查询只读并支持 limit。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 再看 reset 后查看事件、命名 branch 无事件提示的测试。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看手工 reset 用例是否包含审计查看步骤。
