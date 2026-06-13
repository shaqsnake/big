---
title: '原型仓库存储统计'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-verify.md'
---

# 原型仓库存储统计

## Intent

**Problem:** 原型已经能提交、校验和查看 version，但还缺少最小存储可见性；用户无法直接看到当前仓库有多少 CAS 对象、manifest 逻辑引用了多少字节，以及 CAS 去重带来的节省。

**Approach:** 增加只读命令 `big repo stats`，从元数据聚合 version/FileRef 的逻辑字节、去重后引用对象和按 retention_state 聚合的数据，再扫描 `.big/cas/objects` 得到实际 CAS 对象数和物理字节数。该命令不执行垃圾回收、不改变生命周期状态、不修复 CAS。

## Suggested Review Order

- [../../src/big/metadata.py](../../src/big/metadata.py) -- 先看 `storage_summary` 的 SQL 聚合是否符合 FileRef/retention 模型。
- [../../src/big/cli.py](../../src/big/cli.py) -- 再看 `big repo stats` 的 CAS 目录扫描和输出字段。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 确认首次 commit 后的统计输出有自动覆盖。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工说明是否能指导用户查看存储统计。
