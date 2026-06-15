---
title: '原型分支 ACL 元数据'
type: 'feature'
created: '2026-06-15'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-branch-metadata.md'
---

# 原型分支 ACL 元数据

## Intent

**问题：** Story 2.1 要求分支访问权限绑定到公司现有 Linux groups，而不是维护大量用户名单。原型此前只有 branch owner 字段，没有 group ACL、继承、展示或 ACL 变更审计。

**方案：** 在 branch metadata 中增加 `owner_group`、`read_groups` 和 `write_groups`。`big branch create` 默认继承 source branch ACL；若 source branch 没有 ACL，则使用当前进程可见的 primary group 创建默认 owner/read/write group。新增 `big branch acl show <branch> [--effective]` 和 `big branch acl grant <branch> --group <linux-group> --read|--write`。`write` 隐含 `read`，ACL 变更写入 audit hash-chain。

## Boundaries

- 本切片只实现 ACL 元数据、继承、展示和 grant 审计；暂不对 checkout、commit、reset、restore、promote 等命令做权限拦截。
- MVP 的 IdentityResolver 使用当前进程可见的 Linux/NSS groups；在非 Linux 测试环境中降级为当前用户名同名 group。
- 本切片不展开或缓存 group 成员名单。
- 本切片不实现 ACL template、不实现 group 存在性强校验、不支持逐用户大规模授权。
- `branch acl grant --write` 会同时授予 read。

## Acceptance

- Given 当前 workspace 已有 head version
- When 执行 `big branch create feature/place`
- Then 新 branch 记录 head、source ref、owner、owner group、read groups 和 write groups。

- Given source branch 已有 ACL
- When 执行 `big branch create feature/child --from <source-branch>`
- Then child branch 继承 source branch 的 owner group、read groups 和 write groups。

- Given PD Lead 需要查看 ACL
- When 执行 `big branch acl show feature/place --effective`
- Then CLI 输出 owner group、read groups、write groups、当前用户、uid/gid、当前可见 groups、effective read/write 和命中的 group。

- Given PD Lead 执行 `big branch acl grant feature/place --group apr_team --write`
- When 命令成功
- Then `group:apr_team` 同时出现在 read groups 和 write groups，audit hash-chain 记录 `grant_acl` 事件。

- Given grant 命令没有指定 `--read` 或 `--write`
- When 用户执行命令
- Then 系统拒绝操作，不写入 ACL。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/AclSmoke --repo-id AclSmoke --reset`
- `python -m big branch acl --help`
