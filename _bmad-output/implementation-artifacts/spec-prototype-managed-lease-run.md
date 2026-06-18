---
title: '原型受管执行 lease'
type: 'feature'
created: '2026-06-14'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-restore-in-place.md'
---

# 原型受管执行 lease

## Intent

**问题：** Story 2.6 要求显式原地 restore 能拒绝活动受管 lease，避免 BIG 自己启动的流程命令仍在读写 workspace 时被 restore 原地改写。本切片之前，原型只有 active lease 检查占位输出，无法验证该保护边界。

**方案：** 增加 `big run -- <command>`。命令在当前 BIG workspace 中创建 `.big/leases/<lease>.json`，记录 repo、branch、workspace、actor、host、runner pid、child pid、命令和开始时间；子命令退出后删除 lease，并回显 exit code。`big restore --in-place` 在 dirty 检查后扫描同一 workspace 的 active lease，发现后拒绝执行并输出 lease 摘要。

## Boundaries

- 本切片不是 EDA flow 编排器，不替代 PDS、脚本系统或调度系统。
- 本切片只覆盖 BIG 启动的受管命令；手工从外部 shell 直接启动的 EDA 写入进程不会自动生成 lease。
- 本切片不做 Linux groups/ACL 校验，不实现 lease 续租、超时回收、强制抢占或远端进程终止。
- 本切片不向 audit hash-chain 写入运行事件；lease 是运行期保护信号，不是制品 version。
- 原型先使用 `subprocess` 捕获子命令输出后回放；后续真实 EDA 长任务需要补 streaming/PTY 行为。

## Acceptance

- Given 工程师位于已初始化 BIG workspace
- When 执行 `big run -- python -c 'print("managed smoke")'`
- Then BIG 创建活动 lease，执行子命令，回显子命令输出、`exit_code: 0` 和 `lease_status: released`。

- Given `big run` 子命令正常结束
- When 检查 `.big/leases/`
- Then 不再残留该 lease JSON 文件。

- Given 当前 workspace 存在 active lease JSON
- When 执行 `big restore <version> --in-place --plan`
- Then restore 拒绝执行，输出 `active_lease_check: failed`、`active_leases`、lease id、actor、host、pid、命令摘要和等待建议。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/LeaseSmoke --repo-id LeaseSmoke --reset`
- `python -m big run --help`
