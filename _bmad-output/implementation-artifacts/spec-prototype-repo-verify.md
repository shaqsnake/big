---
title: '原型仓库级 CAS 完整性校验'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-verify.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

# 原型仓库级 CAS 完整性校验

## Intent

**问题：** 原型已有 `big verify <version>`，但用户需要逐个 version 校验。为了支撑手工测试和 NFR14/NFR9 的完整性底线，需要一条仓库级只读命令扫描所有 manifest FileRef。

**方案：** 增加 `big repo verify [--full]`。命令遍历 metadata 中全部 FileRef，检查 CAS 对象存在、大小一致且 SHA-256 匹配；汇总输出版本数、FileRef 数、缺失数、大小不一致数、hash 不一致数和整体 integrity。`--full` 展开失败条目并包含 version id。当前原型将它明确标注为 `scope: repo-wide`、`acl_filter: no`，表示这是仓库维护/管理员视角，不是按 branch ACL 过滤后的普通用户视图。

## Boundaries

- 只读校验，不修复 CAS，不修改 manifest，不移动 branch head。
- 失败计数按 FileRef 统计；同一 CAS 对象被多个 version 引用时，会暴露每条受影响引用。
- 为避免误把部分可见性当作完整仓库健康状态，本命令保持 repo-wide 语义；repo-wide admin policy 尚未实现前，CLI 用 `scope` 与 `acl_filter` 字段显式提示该边界。
- 当前原型不做后台定时扫描、不做告警持久化、不实现 audit hash chain。

## Acceptance

- Given 仓库内所有 CAS 对象完整
- When 执行 `big repo verify`
- Then 输出 `scope: repo-wide`、`acl_filter: no` 和 `integrity: ok`，返回 0。

- Given 某个 manifest 引用的 CAS 对象缺失
- When 执行 `big repo verify --full`
- Then 输出 `integrity: failed`，列出受影响 version 和 FileRef，返回非 0。
