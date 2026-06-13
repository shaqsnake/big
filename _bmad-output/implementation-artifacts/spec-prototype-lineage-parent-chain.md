---
title: '原型 version parent chain lineage'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-cli-vertical-slice.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-reset.md'
---

# 原型 version parent chain lineage

## Intent

**问题：** 原型已有 `big log`、`big show` 和 `big diff`，但用户从一个任意 version 出发时，还缺少一条直接查看祖先链的只读命令。`big log` 面向 branch head 的可达历史，不能覆盖“我手上只有某个 version ID，想看它从哪里来”的调试场景。

**方案：** 增加 `big lineage <version> [--limit N]`，读取 metadata 中现有的 `parent_id`，从目标 version 开始向前追溯 parent chain，并输出 depth、version、parent、branch、step、state、workspace 和 message。`--limit` 默认 20，用于避免长链或异常环导致输出失控。

## Boundaries

- 该命令只读 metadata，不写 CAS、不移动 branch head、不创建 branch event。
- 当前原型只展示 commit parent chain，不实现完整 provenance graph。
- 不引入 `derived_from`、`consumes`、EDA step 输入输出依赖边或跨 work root lineage；这些属于后续 Growth/Architecture 设计。
- version 解析复用现有 `MetadataRepository.get_version` 合约：支持完整 ID 或唯一前缀；未找到或前缀歧义时失败。

## Acceptance

- Given 一个包含两次连续 commit 的 workspace-private ref
- When 执行 `big lineage <second-version>`
- Then 输出 `entries: 2`，depth 0 为第二次 commit，depth 1 为第一次 commit。

- Given 同一个第二次 commit
- When 执行 `big lineage <second-version> --limit 1`
- Then 只输出 depth 0，并显示 `truncated: yes`。

- Given 不存在或不唯一的 version ref
- When 执行 `big lineage <version-ref>`
- Then 命令返回非 0，并提示 `Version not found or ambiguous`。

## Verification

- `python -m pytest`
- `python tools/run_manual_smoke.py --root manual-lab/data/LineageSmoke --repo-id LineageSmoke --reset`
- `python -m big lineage --help`
