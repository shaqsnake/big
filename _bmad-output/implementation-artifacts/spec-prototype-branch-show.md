---
title: '原型分支详情查询'
type: 'feature'
created: '2026-06-12'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-branch-metadata.md'
---

# 原型分支详情查询

## Intent

**Problem:** 原型已经支持创建和列出 branch/ref，但用户只能从列表中看到压缩信息，无法单独查看某个命名 branch 或 workspace-private ref 的来源、head 版本和 head 对应 workspace。

**Approach:** 增加 `big branch show <branch-or-ref>`，复用现有 branch 元数据查询，并在 head version 存在时补充 step、workspace、state 和 message 摘要；不引入 checkout、reset、ACL 或目录物化行为。

## Suggested Review Order

- [../../src/big/cli.py](../../src/big/cli.py) -- 先看 `branch show` 的输出字段和错误路径是否符合当前 CLI 风格。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 再看命名 branch、workspace-private ref 和未知 ref 的覆盖是否足够。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工测试说明是否能指导用户验证 branch 详情查询。
