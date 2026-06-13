---
title: '原型版本 CAS 完整性校验'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cas-readonly.md'
---

# 原型版本 CAS 完整性校验

## Intent

**Problem:** 原型可以把文件发布到 CAS 并在 commit 后回读校验单个对象，但用户还不能对某个已存在 version 的 manifest 引用做事后完整性检查；这会削弱手工验证“CAS 对象存在且未损坏”的能力。

**Approach:** 增加只读命令 `big verify <version>`，遍历该 version 的 FileRef，检查 CAS 对象是否存在、文件大小是否等于 manifest 记录、SHA-256 是否等于 FileRef hash。校验失败时返回非 0；`--full` 展开缺失、大小不一致或 hash 不一致的路径摘要。该命令不修复 CAS、不改写 manifest、不移动 branch head。

## Suggested Review Order

- [../../src/big/cli.py](../../src/big/cli.py) -- 先看 `verify` 的只读校验流程和失败输出。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 再看正常 version 和缺失 CAS 对象的测试覆盖。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工说明是否把 `big verify` 放在 version 详情检查之后。
