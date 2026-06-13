---
title: '原型当前 ref 指针回退'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-status.md'
---

# 原型当前 ref 指针回退

## Intent

**Problem:** 原型可以连续 commit 并查看历史，但还不能表达“把当前 workspace-private ref 回到某个已知稳定版本”的回退操作；如果用逆向 commit 表达，会混淆制品集血缘。

**Approach:** 增加 `big reset <version>`，默认解析当前目录对应的 workspace-private ref，只在元数据事务中移动该 ref 的 head 指针，并记录最小 `branch_events` 审计事件。reset 不创建新 version、manifest 或 CAS 对象，不改写工作目录文件，也不执行 checkout/restore。

## 边界

- 普通 reset 只允许目标 version 是当前 head 的祖先版本。
- 目标 version 不存在、前缀歧义、当前 ref 没有 head、或目标不在当前可达历史链上时拒绝。
- 当前 head 已等于目标 version 时返回 no-op，不重复写审计事件。
- 原型阶段尚未接入 Linux groups/ACL，权限拒绝路径留给后续权限切片。

## Suggested Review Order

- [../../src/big/metadata.py](../../src/big/metadata.py) -- 先看 `branch_events` 表和条件更新事务，确认只移动 branch head。
- [../../src/big/cli.py](../../src/big/cli.py) -- 再看 `big reset` 的当前 ref 解析、祖先检查和输出语义。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 确认正常 reset、no-op、跨血缘拒绝、log 可达链和审计记录都有覆盖。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工测试是否清楚强调“不会改工作目录文件”。
