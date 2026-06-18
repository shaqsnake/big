---
title: '原型生命周期评审状态晋升'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-candidate-outbox.md'
---

# 原型生命周期评审状态晋升

## Intent

**问题：** 当前原型创建 version 时已经写入 `review_state=Exploring` 和 `retention_state=resident`，但还不能验证 FR19/FR21 中“评审状态和驻留状态独立管理、PD Lead 手动晋升评审状态”的最小路径。

**方案：** 增加 `big promote <version> --to <state>`，只更新目标 version 的 `review_state`，保留 `retention_state` 不变，并写入 `lifecycle_events` 事件表。增加 `big lifecycle events <version>` 作为只读查看入口。状态顺序为 `Exploring -> Candidate -> Pinned -> Golden`，原型阶段不支持降级；晋升到 `Golden` 必须显式传入 `--confirm GOLDEN`。

## Boundaries

- 本切片不移动 branch head，不修改工作目录，不写 CAS，不回收对象。
- 本切片只做 review_state 晋升；retention_state 降级和 recipe_only checkout 投影由 `spec-prototype-recipe-only-checkout.md` 单独覆盖，仍不实现 GC 或归档。
- Candidate 晋升的事务 outbox 入队由 `spec-prototype-candidate-outbox.md` 覆盖；本切片本身不实现 outbox worker、delivery staging 或统一发布目录。
- `big promote` 的写权限由 `spec-prototype-branch-acl.md` 覆盖：当前身份必须对目标 version 所属 branch/ref 有 write 权限；本切片本身不定义 PD Lead 角色模型。
- `lifecycle_events` 是最小状态事件记录，不等同于最终 NFR8 要求的服务端 append-only hash-chain 审计日志。

## Acceptance

- Given 一个新提交的 `Exploring/resident` version
- When 执行 `big promote <version> --to Candidate --message 'ready for review'`
- Then version 的状态变为 `[Candidate/resident]`，并记录一条 `Exploring->Candidate` lifecycle event。

- Given 一个 `Candidate/resident` version
- When 再次执行 `big promote <version> --to Candidate`
- Then 命令返回成功并输出 `promote: no-op`，不新增状态变化。

- Given 一个 `Candidate/resident` version
- When 执行 `big promote <version> --to Exploring`
- Then 命令失败，并提示原型不支持降级。

- Given 一个非 Golden version
- When 执行 `big promote <version> --to Golden` 且没有 `--confirm GOLDEN`
- Then 命令失败；提供确认后才允许晋升。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/PromoteSmoke --repo-id PromoteSmoke --reset`
- `python -m big promote --help`
- `python -m big lifecycle events --help`
