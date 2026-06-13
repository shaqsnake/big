---
title: '原型 shell 集成'
type: 'feature'
created: '2026-06-13'
status: 'in-progress'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/spec-prototype-checkout-materialize.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture.md'
---

# 原型 shell 集成

## Intent

**问题：** CLI 子进程不能直接改变父 shell 的当前目录。`big checkout <branch>` 已经能物化用户私有目录并输出 `cd: cd -- <target-path>`，但日常体验仍需要用户复制执行 `cd`。

**方案：** 增加 `big shell-init bash|zsh`，输出一个轻量 shell wrapper。用户执行 `eval "$(big shell-init bash)"` 后，`big checkout <branch>` 仍调用真实 CLI 并打印原始输出；当 checkout 成功且不是 `--plan` 时，wrapper 从 `cd:` 行读取目标目录并执行 `cd -- "$target"`。

## Boundaries

- 只支持 Bash/Zsh；Fish、Csh 和 PowerShell 暂不支持。
- wrapper 只拦截 `checkout`，其他 `big` 命令透传给真实 CLI。
- `big checkout <branch> --plan` 只打印计划，不自动切目录。
- 不改变 checkout 物化、CAS、metadata 或 branch 语义。

## Acceptance

- Given 已安装 `big` console script 的 Bash/Zsh 环境
- When 执行 `eval "$(big shell-init bash)"`
- Then 当前 shell 中出现 `big()` wrapper，其他命令仍透传。

- Given wrapper 已启用
- When 执行 `big checkout feature/place`
- Then CLI 原始输出仍可见，checkout 成功物化或复用目录后，当前 shell 进入输出中的 target path。

- Given wrapper 已启用
- When 执行 `big checkout feature/place --plan`
- Then 只输出 plan，不创建目录，不切换当前目录。
