---
title: '原型 repo-wide admin policy'
type: 'feature'
created: '2026-06-18'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-repo-stats.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-repo-verify.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-branch-acl.md'
---

# 原型 repo-wide admin policy

## Intent

**问题：** `big repo stats` 和 `big repo verify` 是仓库维护/管理员视角，会遍历完整 metadata/CAS，而不是按 branch ACL 过滤后的普通用户视图。此前原型只能用 `scope: repo-wide` 和 `acl_filter: no` 标注边界，还不能在项目配置中限制谁能执行这类 repo-wide 命令。

**方案：** 在中心 `big.toml` 增加可选 `[admin].groups = ["group:<linux-group>", ...]`。未配置时保持原型现有开放行为；配置后，`big repo stats` 与 `big repo verify` 要求当前进程可见 Linux groups 命中其中任意一个 group，否则拒绝执行。group principal 必须使用 `group:<linux-group>` 形式；当 `[acl].validate_groups = true` 时，复用 Linux/NSS group resolver 校验 group 是否存在。

## Boundaries

- 本切片只覆盖 repo-wide 维护命令：`big repo stats` 和 `big repo verify`。
- 本切片不改变 branch/read/write ACL 语义，不展开或缓存 Linux group 成员。
- 本切片不覆盖 `audit verify`、`repo init`、配置修改、全局管理员审计、sudo/提权流程或服务端策略。
- 未配置 `[admin].groups` 时，命令继续输出 `admin_policy: none` 并保持可执行，方便本地原型和手工实验。
- 配置 `[admin].groups` 后，命令输出 `admin_policy: groups`；无权限时在输出仓库统计或完整性结果前拒绝。

## Acceptance

- Given `big.toml` 未配置 `[admin].groups`
- When 用户执行 `big repo stats` 或 `big repo verify`
- Then 命令保持可执行，并输出 `admin_policy: none`。

- Given `big.toml` 配置 `[admin].groups = ["group:repo_admins"]`
- When 当前进程 groups 不包含 `repo_admins`
- Then `big repo stats` 和 `big repo verify` 拒绝执行，并提示 repo admin access 被拒绝。

- Given `big.toml` 配置 `[admin].groups = ["group:repo_admins"]`
- When 当前进程 groups 包含 `repo_admins`
- Then `big repo stats` 和 `big repo verify` 正常执行，并输出 `admin_policy: groups`。

## Verification

- `python -m pytest`
- `python -m big repo stats --help`
- `python -m big repo verify --help`
