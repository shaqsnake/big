---
title: '原型显式原地 restore'
type: 'feature'
created: '2026-06-14'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-reset.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
---

# 原型显式原地 restore

## Intent

**问题：** MVP 规划要求 checkout 和 reset 都不得隐式改写源工作目录；只有用户显式执行 `big restore --in-place <version>` 时，才允许在确认 quiet state 后受控恢复当前稳定目录。原型之前只有 pointer-only `reset` 和 copy-only checkout，缺少可验证的 restore 边界、dirty 检查和 restore journal。

**方案：** 增加 `big restore <version> --in-place`。命令解析当前 workspace-private 或 checkout branch，要求目标 version 为当前 head 或其祖先且 `retention_state=resident`；先校验当前 head 的 tracked 文件没有 dirty state，再生成 restore plan。执行时必须传入 `--confirm RESTORE`，使用同目录临时文件从 CAS copy-only 物化并校验，逐文件替换，写入 `.big/restore-journals/<journal>.json`、`.big-workspace.json`、branch event 和 audit hash-chain。

## Boundaries

- 本切片不实现 Linux groups/ACL 检查。
- 本切片尚未实现受管 lease 子系统，因此输出 `active_lease_check: not-implemented`；用户仍必须通过 `--confirm RESTORE` 表示已确认目录静默。
- 本切片只支持恢复到当前 head 或祖先版本，不支持跨血缘原地改写。
- 本切片只支持 `resident` 目标版本；`recipe_only` 目标继续通过 inputs-only checkout 表达降级物化。
- 默认拒绝删除当前目录中目标版本不存在的文件；用户复核 plan 后可以显式传入 `--delete-missing`。
- Linux/WSL 路径优先使用 `os.replace`/`Path.replace` 的同目录替换语义；Windows 测试环境在该调用失败时使用覆盖复制作为兼容 fallback。

## Acceptance

- Given 当前 workspace 的 head 为 v2，且 v1 是 v2 的祖先
- When 执行 `big restore v1 --in-place --plan`
- Then 输出当前 head、目标 version、workspace generation、dirty 状态、active lease 边界、add/overwrite/delete/keep 数量、changed_files、bytes 和 `materialization: plan-only`。

- Given 当前 workspace 存在 tracked dirty 文件
- When 执行 `big restore v1 --in-place --confirm RESTORE`
- Then 命令拒绝执行，输出 dirty 文件摘要，不改写文件、不移动 branch head。

- Given restore plan 需要删除目标版本不存在的文件
- When 未传入 `--delete-missing`
- Then 命令拒绝执行，并提示用户复核 plan 后显式启用删除。

- Given 当前 workspace clean，且用户传入 `--confirm RESTORE`
- When 执行 `big restore v1 --in-place --confirm RESTORE`
- Then 系统从 CAS 恢复新增/覆盖文件，必要时按 `--delete-missing` 删除多余文件，写入 restore journal，更新 workspace generation，并将当前 branch head 从 v2 移动到 v1。

- Given restore 成功完成
- When 执行 `big status`、`big branch events`、`big audit verify`
- Then status 显示 `generation`、`restored_from`、`restore_journal`；branch events 显示 restore 事件；audit hash-chain 校验通过。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/RestoreSmoke --repo-id RestoreSmoke --reset`
- `python -m big restore --help`
