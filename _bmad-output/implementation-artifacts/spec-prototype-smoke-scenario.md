---
title: '原型 WSL smoke 场景'
type: 'test'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-restore-in-place.md'
---

# 原型 WSL smoke 场景

## Intent

**问题：** `make smoke` 原先只覆盖 init、commit、log，已经落后于当前原型的关键路径；用户在 WSL 中手工验证时，还需要确认 shell 集成输出、workspace-private ref 隔离、显式 `restore --in-place`、parent-chain lineage、Candidate 晋升、命名 branch、branch checkout、`--print-path` 输出模式、历史版本 `--new-branch` checkout、recipe_only inputs-only checkout、仓库级完整性校验、repo stats 和 audit hash-chain。

**方案：** 新增 `tools/run_manual_smoke.py`，由 Makefile 调用。脚本在可重置的 `manual-lab/` 目录下生成 fixture，执行真实 `python -m big` 命令，并对关键输出和落盘文件做断言。

## Boundaries

- `make smoke` 面向 WSL/Linux 手工验证，不作为生产部署入口。
- `--reset` 只允许删除仓库内 `manual-lab/` 下的路径；遇到只读 CAS 文件时先恢复写权限再删除。
- smoke 不依赖 `big` console script，仍通过 `PYTHONPATH=src python -m big ...` 验证源码工作区。
- smoke 不新增 CLI 行为，不改变 metadata/CAS 合约。

## Acceptance

- Given 当前源码工作区
- When 执行 `make smoke`
- Then 脚本重建 `manual-lab/data/WslChip` 并完成 repo init。

- Given alice 的 APR workspace
- When smoke 执行 shell-init、commit、restore plan、restore execute、lineage、promote、branch create、branch checkout、`--print-path`、历史版本 `--new-branch` checkout
- Then restore 将 alice workspace 从第二个版本恢复到第一个版本，并写入 generation 与 restore journal；checkout 目录被创建，文件内容可读；进入 checkout 目录后 `status/log` 默认指向对应分支；再次 checkout 输出 `materialization: reused`。

- Given shaqsnake 的 APR workspace
- When smoke 执行独立 commit、log、recipe_only 降级和 `recipe/shaq` checkout
- Then shaqsnake 的默认 log 不包含 alice 的 version，recipe_only checkout 只物化 inputs/scripts、不物化 outputs/reports，`main` 仍无可见历史。

- Given smoke 完成
- When 查看 repo stats
- Then `big repo verify` 输出 `integrity: ok`，repo stats 输出 3 个 version、15 个 file_ref、6 个唯一引用对象和 6 个 CAS 对象。
- And repo stats 的 review 分布包含 `Candidate: versions=1` 和 `Exploring: versions=2`，retention 分布包含 `resident: versions=2` 和 `recipe_only: versions=1`。

- Given smoke 完成
- When 执行 `big audit verify`
- Then 输出 `events: 9` 和 `integrity: ok`。
