---
title: '原型 Candidate outbox 入队'
type: 'feature'
created: '2026-06-16'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-promote-lifecycle.md'
---

# 原型 Candidate outbox 入队

## Intent

**问题：** 架构要求 Candidate 状态迁移、审计和 outbox 事件同事务提交，但当前原型在 `big promote --to Candidate` 后只输出 `candidate_outbox: not-implemented`。用户无法验证“Candidate 已可靠入队，后续交付系统可幂等消费”的最小语义。

**方案：** 在 SQLite metadata adapter 中增加本地 `outbox_event` 表。`big promote <version> --to Candidate` 从非 Candidate 状态成功迁移到 Candidate 时，在同一个 metadata transaction 内写入 lifecycle event、audit event 和 `artifact.candidate_marked` outbox event。新增只读命令 `big outbox list [--full] [--all]` 查看 pending 事件。

## Boundaries

- 本切片只实现本地事务 outbox 记录，不实现 outbox worker、外部消息投递、delivery staging 或版本化发布目录。
- outbox payload 只包含后续交付所需的最小不可变引用：version、branch、manifest hash、recipe hash、状态迁移和 reason。
- `big promote --to Candidate` 的 no-op 不重复创建 outbox 事件。
- 直接晋升到 `Pinned` 或 `Golden` 不补发 Candidate 事件；原型保持显式 Candidate transition 才触发 Candidate outbox。
- `published_at` 预留给后续 worker，当前不会自动更新。

## Acceptance

- Given 一个 `Exploring/resident` version
- When 执行 `big promote <version> --to Candidate --message 'ready for review'`
- Then CLI 输出 `candidate_outbox: queued` 和 `outbox_event: oe...`
- And metadata 在同一个事务中保存 lifecycle event、audit event 和 `artifact.candidate_marked` outbox event。

- Given Candidate outbox 已入队
- When 执行 `big outbox list --full`
- Then 输出 pending event、version id、event type 和 payload JSON。

- Given version 已经是 `Candidate`
- When 再次执行 `big promote <version> --to Candidate`
- Then 命令返回 `promote: no-op`
- And 不创建新的 Candidate outbox event。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/CandidateOutboxSmoke --repo-id CandidateOutboxSmoke`
- `python -m big outbox list --help`
