---
title: '原型 3DIC 多 work root 初始化'
type: 'feature'
created: '2026-06-13'
status: 'done'
route: 'one-shot'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-3dic-checkout-target.md'
---

# 原型 3DIC 多 work root 初始化

## Intent

**Problem:** 原型此前只支持单一默认 work root，无法验证 3DIC 场景中 `_3D`、`_Top`、`_Bottom`、`_MIX` 四个并行 NAS root 绑定到同一个逻辑 BIG 仓库的核心路径。

**Approach:** 扩展 `big repo init` 支持重复传入 `--work-root id=path`。主配置仍写在命令指定的 repo home，例如 `_3D`；其他 work root 写指针型 `big.toml`，指向主仓库 home 和对应 `work_root_id`。读取指针配置时回到主配置，因此四个 root 共享同一个 `.big`、CAS 和 metadata。

## 边界

- 本切片只实现配置读写、路径解析和指针配置；checkout 目标 root 归属由 `spec-prototype-3dic-checkout-target.md` 覆盖，本切片不实现 restore、ACL 或常驻 `big service`。
- 当显式传入 `--work-root` 时，主 repo path 必须是登记的 work root 之一。
- 指针 root 不创建自己的 `.big/` 仓库内部目录。

## Suggested Review Order

- [../../src/big/config.py](../../src/big/config.py) -- 先看主配置、指针配置和 `load_config` 指针回跳逻辑。
- [../../src/big/cli.py](../../src/big/cli.py) -- 再看 `repo init --work-root` 参数解析、幂等行为和指针写入。
- [../../tests/test_cli_prototype.py](../../tests/test_cli_prototype.py) -- 确认 `_Top` 指针 root 下 status/commit 都解析到同一个主仓库。
- [../../docs/manual-test-prototype.md](../../docs/manual-test-prototype.md) -- 最后看 WSL 手工说明是否覆盖四 root 初始化命令。
