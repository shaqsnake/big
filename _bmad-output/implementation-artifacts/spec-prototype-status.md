---
title: '原型当前上下文状态查询'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-branch-metadata.md'
---

# 原型当前上下文状态查询

## Intent

**Problem:** 工程师在 `user/<username>/<flow>` 目录下手工测试时，需要快速确认 BIG 如何解析当前目录，以及默认 commit/log 会落到哪个 workspace-private ref；仅靠 `commit` 输出或 `log` 不够直观。

**Approach:** 增加只读命令 `big status`，输出 repo、integration、home、cwd、work root、workspace、user、flow、default ref 和当前 head；当 head 存在时补充 head step、state 和 message。该命令不创建版本、不移动 branch head、不进行 checkout 或目录物化。

## Suggested Review Order

- [../../src/big/cli.py](../../src/big/cli.py) -- 先看 `status` 在 repo root 与 workspace 下的输出和错误降级路径。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 再看 status 自动测试是否覆盖未提交前后和 head 摘要。
- [../../Makefile](../../Makefile) -- 确认 smoke 路径能在 WSL/Linux 下顺手验证当前上下文。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看手工说明是否把 status 放在合适的验证节点。
