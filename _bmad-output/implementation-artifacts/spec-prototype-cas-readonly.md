---
title: '原型 CAS 只读硬化'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
---

# 原型 CAS 只读硬化

## Intent

**Problem:** 原型新发布 CAS 对象时已经会设置只读权限，但复用已有合法对象时只校验 hash，不会重新收紧权限；如果对象曾被旧原型或手工操作误设为可写，就会削弱“CAS 对象只读不可变”的 MVP 不变量。

**Approach:** 将 CAS 对象权限收紧逻辑提取为 `make_readonly`，并在新发布、复用已有对象、并发 publish 发现对象已存在三条路径上统一执行。该切片不改变 SHA-256 地址、manifest、commit 或 checkout 行为。

## Suggested Review Order

- [../../src/big/cas.py](../../src/big/cas.py) -- 先看新对象和已有对象是否都会调用只读硬化。
- [../../tests/test_cas.py](../../tests/test_cas.py) -- 再看新发布对象和已有可写对象复用两条路径的测试。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工检查命令是否清楚说明预期无输出。
