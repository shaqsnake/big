---
title: '原型 show 详情摘要'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-capture-evidence.md'
---

# 原型 show 详情摘要

## Intent

**问题：** Story 3.2 要求 `big show <version>` 展示 version 基本信息、manifest 摘要，并在 `--verbose` 下展示 inputs/outputs 的分类摘要、大小分布和 capture evidence 摘要。原型此前已有基础 manifest 输出和 `--full` 文件列表，但默认输出缺少 commit message，verbose/full 缺少聚合摘要。

**方案：** 在 `show` 基础输出中增加 `message` 字段；在 `--verbose` 或 `--full` 时，为 input/output 分别输出文件数、总字节数、semantic_role 计数、format_hint 计数、size 分布和 capture evidence 可用性统计。`--full` 继续展示完整 FileRef 列表与逐文件 evidence 摘要。

## Boundaries

- 本切片只增强只读展示，不改变 manifest、CAS 或权限逻辑。
- 默认 `big show <version>` 仍只展示摘要，不展开文件列表。
- `--verbose` 的分类摘要只使用当前 MVP 的 input/output 两类 FileRef，不引入独立 params 角色。
- size 分布使用整数 avg，作为快速扫描信息，不用于计费或容量决策。

## Acceptance

- Given 用户执行 `big show <version>`
- When version 有 commit message
- Then 输出包含 `message`，并且默认不展开 FileRef 列表。

- Given 用户执行 `big show <version> --verbose`
- When version 包含 inputs 和 outputs
- Then 输出 input/output 分类摘要、semantic_role 计数、format_hint 计数、size 分布和 capture evidence 可用性统计。

- Given 用户执行 `big show <version> --full`
- When version 包含 FileRef
- Then 输出分类摘要和完整 FileRef 列表，每个 FileRef 仍包含 path、size、hash、semantic_role、format_hint 和 capture evidence 摘要。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_repo_init_commit_log_show_and_diff`
- `python -m pytest`
