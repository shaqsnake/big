---
title: '原型显式部分 checkout'
type: 'feature'
created: '2026-06-14'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-recipe-only-checkout.md'
---

# 原型显式部分 checkout

## Intent

**问题：** MVP 规划要求百万文件级项目可以只物化当前需要的文件子集。原型此前只有 full checkout，以及 `recipe_only` 降级时自动 inputs-only checkout，尚不能让用户显式选择少量输入、脚本、报告或局部输出。

**方案：** 扩展 `big checkout`，增加 `--include <path-or-glob>`、`--exclude <path-or-glob>` 和 `--full`。没有 include/exclude 时仍执行完整 checkout；一旦出现显式选择规则，命令从目标 version manifest 中按 include 合并匹配文件，再应用 exclude，生成 `selection_profile` 和 `selection_hash`。目标目录使用 `<version>__partial__<selection-hash>`，避免和 full checkout 或其它选择集合混用。

## Boundaries

- 本切片只做 manifest 文件级选择，不实现懒加载、按需补齐、远端召回或文件系统透明投影。
- 本切片不改变默认 checkout 语义；普通 `big checkout <branch>` 仍 full checkout。
- `big checkout` 的 read 权限由 `spec-prototype-branch-acl.md` 覆盖；无权限时在解析目标、输出 checkout target path 或物化文件前拒绝。
- 本切片不在已有 partial 目录中补齐、删除或覆盖不同选择集合；不同 selection hash 对应不同目标目录。
- `recipe_only` version 默认仍使用 inputs-only checkout；显式 include/exclude 只在当前可物化 FileRef 集合内继续缩小选择范围。

## Acceptance

- Given 工程师执行 `big checkout feature/place` 且没有 include/exclude
- When checkout 目标 version 为 `resident`
- Then 系统保持 `checkout_scope: full`，目标路径仍为 `<safe-branch>/<version>`。

- Given 工程师执行 `big checkout feature/place --include 'inputs/**;reports/*.rpt' --exclude 'reports/place.rpt' --plan`
- When 目标 manifest 中存在匹配文件
- Then 输出 `checkout_scope: partial`、`selection: explicit`、`selection_hash`、include/exclude 摘要、匹配文件数、总字节数和目标路径 `<version>__partial__<selection-hash>`。

- Given 用户追加 `--full`
- When 输出 partial checkout plan
- Then CLI 展示本次选中的 FileRef 列表，包括 role、path、size 和 CAS hash 摘要。

- Given 用户执行不带 `--plan` 的 partial checkout
- When CAS 对象完整
- Then 系统只复制选中的 FileRef，写入 `.big-checkout.json`，marker 中记录 `materialization=partial` 和 `selection_profile`。

- Given 相同 branch、version 和 selection profile 的 partial checkout 已存在
- When 用户再次执行同一组 include/exclude
- Then 输出 `materialization: reused`，不覆盖已有目录。

- Given include pattern 没有匹配 manifest 中任何文件
- When 用户执行 partial checkout
- Then 命令拒绝执行，并输出未匹配 include pattern。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/PartialSmoke --repo-id PartialSmoke --reset`
- `python -m big checkout --help`
