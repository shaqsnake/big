---
title: '原型外部 success marker 检查'
type: 'feature'
created: '2026-06-16'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
---

# 原型外部 success marker 检查

## Intent

**问题：** 工程师通常通过 PDS 或其他流程系统运行 EDA step。BIG 不应该要求这些系统写 `.big` 目录、实现 BIG 专用 running/failed 状态机，或与 BIG 深度耦合；但 commit 时仍需要一个轻量信号，确认外部 step 已按项目约定成功结束。

**方案：** 在 `big.toml` 中增加 `[step_markers].success` pattern，并在 `big commit --require-marker` 时解析 success marker。marker 可以位于当前 flow workspace 之外的外部流程目录；存在且是文件时才继续 capture；缺失时拒绝 commit，并只提示 configured step success marker not found 与解析后的路径。

## Boundaries

- 本切片不实现 running marker、failed marker、外部流程状态机或流程系统插件。
- marker 路径归外部流程系统约定和拥有，不要求 `.big`、`big` 前缀或 BIG 专用目录。
- 支持的占位符仅限 `{step}`、`{user}`、`{flow}`、`{workspace}` 和 `{work_root}`。
- `--require-marker` 只影响 commit 前置检查；文件捕获仍使用现有 stable copy 与文件级 CAS。
- 未启用 `--require-marker` 时保持原有 best-effort commit 行为。

## Acceptance

- Given `big.toml` 未配置 `[step_markers].success`
- When 用户执行 `big commit --require-marker`
- Then BIG 拒绝 commit，并提示配置缺失。

- Given `big.toml` 配置 `success = "../markers/{flow}/{step}.done"` 但 marker 不存在
- When 用户执行 `big commit --step place --require-marker`
- Then BIG 拒绝 commit，并输出 `configured step success marker not found` 和解析后的 marker 路径。

- Given marker 文件存在
- When 用户执行 `big commit --step place --require-marker`
- Then commit 成功，CLI 输出 `success_marker: found` 和 `success_marker_path`。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/SuccessMarkerSmoke --repo-id SuccessMarkerSmoke`
- `python -m big commit --help`
