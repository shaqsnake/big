---
title: '原型 CLI 帮助与错误引导'
type: 'feature'
created: '2026-06-17'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
---

# 原型 CLI 帮助与错误引导

## Intent

**问题：** 原型已经有 Click 自动生成的基础帮助，但 Story 1.5 要求工程师在没有 GUI 或额外文档入口时，也能直接通过 CLI 看到初始化、提交和典型工作流示例；业务错误也应该提示下一步可以查看哪个命令的帮助。

**方案：** 为根命令、`big repo init` 和 `big commit` 增加可复制 examples；通过统一的 Click command class 捕获命令回调中的业务 `ClickException`，追加 `Next step: run <command> --help` 提示。Click 自身的参数解析错误保持默认 UsageError 行为。

## Boundaries

- 本切片只增强帮助文本与业务错误提示，不改变命令参数契约或业务行为。
- `--help` 不要求当前目录属于 BIG 仓库，也不得初始化 metadata、CAS 或 staging。
- 帮助文本继续使用当前 CLI 的英文风格；BMad 规划和实现文档保持中文。
- 统一 hint 只处理命令回调中抛出的业务错误；未知选项、缺失 required option 等 Click 解析错误由 Click 默认帮助提示处理。

## Acceptance

- Given 用户在任意目录执行 `big --help`
- When CLI 渲染帮助
- Then 输出 BIG 用途、命令列表和可复制示例，并且不创建 `.big`。

- Given 用户执行 `big repo init --help`
- When CLI 渲染帮助
- Then 输出普通 2D 初始化示例和 3DIC 多 work root 示例。

- Given 用户执行 `big commit --help`
- When CLI 渲染帮助
- Then 输出 step、inputs、outputs、message、success marker、settle window 等参数说明
- And 明确当前原型只区分 inputs 与 outputs，独立 params 角色属于未来范围。

- Given 用户触发业务错误
- When CLI 返回错误
- Then 输出失败原因，并追加对应命令的 `--help` 下一步提示。

## Verification

- `python -m py_compile src/big/cli.py`
- `python -m pytest tests/test_cli_prototype.py::test_core_help_outputs_examples_without_repo`
- `python -m pytest tests/test_cli_prototype.py::test_commit_rejects_missing_inputs`
- `python -m pytest`
