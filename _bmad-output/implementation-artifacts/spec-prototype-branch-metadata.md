---
title: '原型分支元数据切片'
type: 'feature'
created: '2026-06-12'
status: 'implemented'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
---

## 意图

**问题：** 当前原型已经能把默认 commit 隔离到 workspace-private ref，但还缺少将某个 workspace head 固化为命名 branch 的最小能力。用户无法从当前 workspace 历史创建一个团队可引用的稳定分支名。

**方案：** 增加 `big branch create` 和 `big branch list`。`create` 只创建命名 branch 记录并设置 head 指针；`list` 展示分支及 head。默认 `--from` 使用当前 workspace-private ref 的 head，也允许显式指定 branch/ref 或 version ID。

## 边界

**本切片实现：**
- `big branch create <branch-name> [--from <source-ref>]`
- `big branch list [--all]`
- branch 元数据记录 kind、head、source_ref、source_version、owner、created_at
- workspace-private ref 仍可作为 source ref，但默认 `branch list` 不展示 workspace ref，除非使用 `--all`

**本切片不实现：**
- `big checkout`
- 目录物化或目录切换
- Linux groups / ACL 权限模型
- reset / restore
- branch path template

## 验收

- 给定当前 workspace 已有 commit，当执行 `big branch create feature/place` 时，系统创建命名 branch，并将其 head 指向当前 workspace ref 的 head version。
- 给定显式 source version，当执行 `big branch create feature/from-old --from <version>` 时，系统创建命名 branch 并指向该 version。
- 给定不同用户 workspace 的默认 commit 历史，创建命名 branch 不改变这些 workspace-private ref 的 head。
- 给定执行 `big branch list`，系统默认显示 `main` 和命名 branch；执行 `big branch list --all` 时额外显示 workspace-private ref。

## 验证

- `python -m pytest`：已通过。
- 在 `.manual-lab/data/IsolationChip/user/alice/APR` 上执行 `big branch create feature/place`：已创建命名 branch，head 指向 alice workspace head。
- 执行 `big branch list`：默认只显示 `main` 和 `feature/place`。
- 执行 `big branch list --all`：额外显示 `workspace/default/alice/APR` 和 `workspace/default/shaqsnake/APR`。
