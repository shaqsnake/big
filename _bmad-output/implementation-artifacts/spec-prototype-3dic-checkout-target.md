---
title: '原型 3DIC checkout 目标 root 归属'
type: 'feature'
created: '2026-06-19'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-3dic-workroots.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
---

# 原型 3DIC checkout 目标 root 归属

## Intent

**问题：** 3DIC 仓库中 `_3D`、`_Top`、`_Bottom`、`_MIX` 四个 work root 共享同一个 BIG metadata/CAS。此前 checkout 目标目录总是按当前命令所在 work root 生成；如果工程师站在 `_Bottom` 目录 checkout 一个来自 `_Top` 的 branch，物化目录会落到 `_Bottom`，容易混淆源数据归属。

**方案：** checkout 解析到目标 version 后，优先使用 version metadata 中记录的 `work_root_id`、`user_name` 和 `flow` 生成用户私有目标目录。旧 version 缺少这些字段时继续回退到当前 workspace，保持兼容。跨 root checkout 时 CLI 仍输出命令发起目录 `source_workspace`，并额外输出 `checkout_workspace` 表示目标 version 所属 workspace。

## Boundaries

- 本切片只修正 checkout 目标目录归属，不实现 3DIC 多 root 的 restore 联动。
- 本切片不自动跨 root 创建业务 workspace，只创建用户私有 `.big-checkouts/<flow>/<branch>/<version>` 物化目录。
- 本切片不改变 branch ACL、CAS、manifest 或 checkout copy-only 语义。
- 如果目标 version 引用的 `work_root_id` 未在当前仓库配置中登记，命令拒绝执行，避免物化到错误 root。

## Acceptance

- Given 3DIC 仓库登记了 `top` 和 `bottom` work root
- And `feature/top` 指向一个在 `top` work root 提交的 version
- When 用户站在 `bottom/user/alice/APR` 执行 `big checkout feature/top --plan`
- Then `target_path` 位于 `top/user/alice/.big-checkouts/APR/feature__top/<version>`。
- And 输出包含 `source_workspace: <bottom workspace>` 和 `checkout_workspace: <top workspace>`。

- Given 同一 checkout 不带 `--plan`
- When 物化成功
- Then `.big-checkout.json` 记录 `work_root_id: top`，进入目标目录后 `big status` 显示 `work_root: top ...` 和 `default_ref: feature/top`。

## Verification

- `python -m pytest tests/test_cli_prototype.py -k 3dic`
- `python -m pytest`
