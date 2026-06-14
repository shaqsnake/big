---
title: '原型 recipe_only 降级与 inputs-only checkout'
type: 'feature'
created: '2026-06-14'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-promote-lifecycle.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
---

# 原型 recipe_only 降级与 inputs-only checkout

## Intent

**问题：** 当前原型已经能区分 `review_state` 和 `retention_state`，但还不能验证“把低价值探索版本降级为 recipe_only 后，后续 checkout 不再默认物化大体量输出文件”的最小体验。用户需要看到该状态如何落入 metadata、audit、lifecycle events 和 checkout 输出。

**方案：** 增加 `big lifecycle degrade <version> --to recipe_only --confirm RECIPE_ONLY`。该命令只允许 `Exploring/resident` version 降级为 `Exploring/recipe_only`，写入 lifecycle event 和 audit hash-chain，不删除、不搬迁 CAS 对象。对 `recipe_only` version 执行 `big checkout <branch>` 时，只物化 `role=input` 的 FileRef，输出 `checkout_scope: inputs-only`、`omitted_outputs: ...`，并在 `.big-checkout.json` 中记录 `materialization=partial`。

## Boundaries

- 本切片不实现物理 GC、归档搬迁、远端召回或 CAS 对象删除。
- 本切片不允许降级 `Candidate`、`Pinned` 或 `Golden` version。
- 本切片不改变完整 `resident` version 的 checkout 行为；它们仍使用 `materialization=copy` 并复制 inputs 和 outputs。
- `recipe_only` checkout 的 partial 目录仍是用户私有物化目录，不作为共享发布目录。
- 当前原型只按 `role=input` 和 `role=output` 做粗粒度投影；后续 Story 1.4 细分类确定后再拆分 scripts、logs、reports、large artifacts 等类型。

## Acceptance

- Given 一个 `Exploring/resident` version
- When 执行 `big lifecycle degrade <version> --to recipe_only --confirm RECIPE_ONLY --message 'retire outputs'`
- Then version 状态变为 `[Exploring/recipe_only]`，并记录 `resident->recipe_only` lifecycle event 和 `degrade` audit event。

- Given 一个 `Candidate/resident`、`Pinned/resident` 或 `Golden/resident` version
- When 执行 `big lifecycle degrade <version> --to recipe_only --confirm RECIPE_ONLY`
- Then 命令失败，并提示当前原型只允许降级 Exploring version。

- Given 一个指向 `recipe_only` version 的命名 branch
- When 执行 `big checkout <branch> --plan`
- Then 输出 `retention: recipe_only`、`checkout_scope: inputs-only`、`omitted_outputs: <n>`、`materialization: plan-only`，且不创建目标目录。

- Given 一个指向 `recipe_only` version 的命名 branch
- When 执行 `big checkout <branch>`
- Then 目标目录只包含 input FileRef，对 output FileRef 不做物化，输出 `materialization: partial`，marker 记录 `omitted_outputs`。

- Given 已存在匹配 repo、branch、version 和 `materialization=partial` 的 checkout marker
- When 再次执行 `big checkout <branch>`
- Then 命令输出 `materialization: reused` 并复用已有目录。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/RecipeOnlySmoke --repo-id RecipeOnlySmoke --reset`
- `python -m big lifecycle degrade --help`
