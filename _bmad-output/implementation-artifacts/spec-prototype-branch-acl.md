---
title: '原型分支 ACL 元数据与基础拦截'
type: 'feature'
created: '2026-06-15'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-branch-metadata.md'
---

# 原型分支 ACL 元数据与基础拦截

## Intent

**问题：** Story 2.1 要求分支访问权限绑定到公司现有 Linux groups，而不是维护大量用户名单。原型此前只有 branch owner 字段，没有 group ACL、继承、展示或 ACL 变更审计；即使有 ACL 元数据，也还不能阻止无权限用户读取 branch manifest 或写入 branch。

**方案：** 在 branch metadata 中增加 `owner_group`、`read_groups` 和 `write_groups`。`big branch create` 默认继承 source branch ACL；若 source branch 没有 ACL，则使用当前进程可见的 primary group 创建默认 owner/read/write group；也可以通过 `--acl-template <name>` 套用中心 `big.toml` 中的 `[[acl_templates]]`。当项目配置 `[acl] validate_groups = true` 时，模板应用和 `branch acl grant` 会通过当前进程可用的 Linux/NSS group resolver 校验 group 是否存在。新增 `big branch acl show <branch> [--effective]` 和 `big branch acl grant <branch> --group <linux-group> --read|--write`。`write` 隐含 `read`，ACL 变更写入 audit hash-chain。基础 enforcement 覆盖 `branch list`、`branch show`、`branch acl show`、`branch events`、`checkout`、`log`、`show`、`lineage`、`lifecycle events`、`verify`、`diff` 的 read 权限，以及 `commit`、`reset`、`restore`、`promote`、`lifecycle degrade`、`branch acl grant` 的 write 权限；其中 `branch list` 只显示当前身份有 read 权限的 branch，并用 `restricted` 计数表示被隐藏的条目数量。

## Boundaries

- 本切片实现 ACL 元数据、继承、ACL template 套用、展示、grant 审计和核心 CLI read/write 权限拦截。
- MVP 的 IdentityResolver 使用当前进程可见的 Linux/NSS groups；在非 Linux 测试环境中降级为当前用户名同名 group。
- 原型测试可通过 `BIG_IDENTITY_USER` 和 `BIG_IDENTITY_GROUPS` 覆盖当前身份，用于模拟不同 Linux group session。
- 本切片不展开或缓存 group 成员名单。
- 本切片支持 `[acl] validate_groups = true` 下的 Linux/NSS group 存在性强校验；默认关闭以便本地实验和无真实企业 group 的手测环境继续运行。
- 本切片不支持逐用户大规模授权，也不覆盖 repo-wide admin policy。
- `[[acl_templates]]` 里的 group principal 必须显式使用 `group:<linux-group>`；CLI 的 `branch acl grant --group` 仍允许输入裸 group 名并归一化为 `group:<linux-group>`。
- `branch acl grant --write` 会同时授予 read。

## Acceptance

- Given 当前 workspace 已有 head version
- When 执行 `big branch create feature/place`
- Then 新 branch 记录 head、source ref、owner、owner group、read groups 和 write groups。

- Given source branch 已有 ACL
- When 执行 `big branch create feature/child --from <source-branch>`
- Then child branch 继承 source branch 的 owner group、read groups 和 write groups。

- Given 中心 `big.toml` 配置了 `[[acl_templates]] name = "apr"`
- When 执行 `big branch create feature/apr --acl-template apr`
- Then 新 branch 套用模板中的 owner group、read groups 和 write groups，并输出 `acl_source: template:apr`。

- Given ACL template 中的 group 没有使用 `group:<linux-group>` 形式
- When 执行引用该模板的 `big branch create`
- Then 系统拒绝创建 branch，并提示模板 group principal 格式错误。

- Given 中心 `big.toml` 设置 `[acl] validate_groups = true`
- When ACL template 或 `branch acl grant` 引用了当前 Linux/NSS 无法解析的 group
- Then 系统拒绝写入，并输出无法解析的 `group:<linux-group>`；模板路径还会输出所属 template 名称。

- Given PD Lead 需要查看 ACL
- When 执行 `big branch acl show feature/place --effective`
- Then CLI 输出 owner group、read groups、write groups、当前用户、uid/gid、当前可见 groups、effective read/write 和命中的 group。

- Given PD Lead 执行 `big branch acl grant feature/place --group apr_team --write`
- When 命令成功
- Then `group:apr_team` 同时出现在 read groups 和 write groups，audit hash-chain 记录 `grant_acl` 事件。

- Given grant 命令没有指定 `--read` 或 `--write`
- When 用户执行命令
- Then 系统拒绝操作，不写入 ACL。

- Given 当前用户不在 branch owner/read/write groups 中，且不是 branch owner
- When 用户执行 `big branch show <branch>`、`big checkout <branch> --plan`、`big show <version>` 或 `big lifecycle events <version>`
- Then 系统拒绝操作，并在输出 manifest、FileRef 或 checkout target path 前返回权限不足错误。

- Given 当前用户不在某个 named branch 的 read/write groups 中，且不是 branch owner
- When 用户执行 `big branch list`
- Then 系统不显示该受限 branch 的名称、head 或 source ref，只输出 `restricted` 计数。

- Given 当前用户只有 read group
- When 用户执行 `big commit --branch <branch>` 或 `big branch acl grant <branch> --group pv_team --read`
- Then 系统拒绝操作，并返回 write 权限不足错误。

- Given 当前用户被授予 write group
- When 用户执行需要 write 权限的命令
- Then `write` 隐含 `read`，权限判断通过。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/AclSmoke --repo-id AclSmoke --reset`
- `python -m big branch acl --help`
