---
title: '原型 audit hash-chain'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-promote-lifecycle.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-repo-admin-policy.md'
---

# 原型 audit hash-chain

## Intent

**问题：** 原型已经有 `commit`、`branch create`、`reset` 和 `promote` 等写操作，但只有 branch/lifecycle 的局部事件记录，尚不能验证 NFR8 中“写操作可审计且篡改可检测”的最小闭环。

**方案：** 增加本地 `audit_events` 表。每个写操作在同一 SQLite 事务中追加一条 audit event，记录 action、entity、actor、created_at、payload 摘要、previous_hash 和 event_hash。`event_hash` 基于上一条 hash 与当前事件规范 JSON 计算。增加 `big audit log` 查看当前身份有 read 权限的最近事件，增加 `big audit verify` 顺序重算完整 hash-chain 并检测断链或事件篡改。

## Boundaries

- 覆盖当前原型中的写操作：`commit`、`branch create`、`branch acl grant`、`reset`、`restore`、`promote`、`lifecycle degrade`。
- audit payload 只保存摘要字段，不保存完整 FileRef 列表，避免百万文件 commit 让审计表膨胀。
- `audit log` 根据 event 的 branch、version 或 workspace payload 复用 branch read ACL；无权限事件不显示 action/entity/payload，只显示 `restricted` 计数。
- `audit verify` 是仓库级完整性检查，仍重算完整 hash-chain，不按 branch ACL 过滤事件数或 broken 结果；若中心 `big.toml` 配置了 `[admin].groups`，执行该命令需要命中 repo admin group。
- 本切片不实现外部不可变介质锚定、不实现导出、不实现服务端 append-only 存储。
- 本切片不改变 branch_events 或 lifecycle_events 的语义；audit 是独立的全局 hash-chain。
- 旧原型仓库只会从升级后新增 audit event，不回填历史写操作。

## Acceptance

- Given 用户执行一次 commit
- When 执行 `big audit log --full`
- Then 输出一条 `commit version <version>` audit event，并包含 branch、input_count、output_count 等摘要 payload。

- Given 当前身份没有某条 audit event 关联 branch/version 的 read 权限
- When 执行 `big audit log --full`
- Then 系统不显示该受限 event 的 action、entity 或 payload，只输出 `restricted` 计数。

- Given 多个写操作依次完成
- When 执行 `big audit verify`
- Then 输出 `scope: repo-wide`、`acl_filter: no`、`admin_policy: ...`、事件数、`broken: 0` 和 `integrity: ok`。

- Given `big.toml` 配置 `[admin].groups = ["group:repo_admins"]`
- When 当前进程 groups 不包含 `repo_admins` 并执行 `big audit verify`
- Then 命令在输出完整 hash-chain 结果前拒绝，并提示 repo admin access 被拒绝。

- Given audit event 的 payload 被手工篡改
- When 执行 `big audit verify --full`
- Then 命令返回非 0，并输出 `event_hash mismatch`。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/AuditSmoke --repo-id AuditSmoke --reset`
- `python -m big audit log --help`
- `python -m big audit verify --help`
