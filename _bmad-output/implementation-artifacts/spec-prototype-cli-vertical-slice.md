---
title: '原型 CLI 垂直切片'
type: 'feature'
created: '2026-06-08'
status: 'implemented'
context:
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="用户确认过的意图，除非重新协商，否则不要修改">

## 意图

**问题：** BIG 已经有规划产物，但还没有可运行的原型。当前需要一个小型本地 CLI 切片，让用户可以手工验证仓库初始化、CAS 捕获、版本元数据，以及历史、详情、差异查看命令。

**方案：** 构建一个 Python Click 包，提供 `big repo init`、`big commit`、`big log`、`big show` 和 `big diff`。同时提供自动化测试、`manual-lab` 手工实验目录和中文手工测试说明。

## 边界与约束

**始终遵守：** 使用文件级 SHA-256 CAS，写入只读不可变 CAS 对象；将元数据访问保持在 `MetadataRepository` 端口之后；`params` 仍作为未来范围处理。原型可以使用本地 SQLite 保存元数据，但不能把共享 NAS SQLite 描述为生产架构。

**需要先确认：** 添加 checkout/reset/restore 行为、实现 Linux groups 授权接入，或修改 `recipe_hash` 合约。

**不得引入：** 不通过可写 hardlink/symlink 暴露 CAS；不在本切片中引入 `big service`、GUI、FastCDC、DSO、生命周期自动化，或 3DIC 多 work root 实现。

## I/O 与边界场景矩阵

| 场景 | 输入 / 状态 | 期望输出 / 行为 | 错误处理 |
|------|-------------|-----------------|----------|
| 初始化仓库 | `big repo init <root> --repo-id DemoChip` | 创建 `big.toml`、`.big/cas`、`.big/metadata` 和 main 分支元数据 | 已存在配置时保持幂等 |
| 提交文件 | 在 workspace 内执行 `big commit --step place --inputs ... --outputs ...` | 将文件捕获到 staging/CAS，创建 version，并更新分支 head | input/output pattern 未匹配到文件时失败 |
| 查看信息 | `big log`、`big show <version>`、`big diff old new` | 显示版本历史、manifest 摘要和 FileRef 差异 | version 未找到或前缀歧义时失败 |

</frozen-after-approval>

## 代码地图

- `pyproject.toml`：Python 包元数据和 `big` 控制台入口。
- `src/big/config.py`：`big.toml` 发现、仓库配置加载、work root 解析。
- `src/big/cas.py`：稳定 staging 复制、SHA-256 哈希计算、不可变 CAS 发布。
- `src/big/metadata.py`：`MetadataRepository` 端口和 SQLite 适配器。
- `src/big/cli.py`：原型的 Click 命令面。
- `tests/test_cli_prototype.py`：端到端 CLI 覆盖。
- `manual-lab/`：被忽略的本地手工测试 workspace，包含类似 EDA 的样例文件。
- `docs/manual-test-prototype.md`：面向用户的手工测试步骤。

## 任务与验收

**执行项：**
- [x] `pyproject.toml`：添加包配置和脚本入口。
- [x] `src/big/*`：实现配置、CAS、元数据和 CLI。
- [x] `tests/test_cli_prototype.py`：测试 init、commit、log、show、diff，以及缺失 input 的错误路径。
- [x] `manual-lab/` 和 `docs/manual-test-prototype.md`：提供本地手工测试环境。

**验收标准：**
- 给定一个全新的 lab root，当执行 `big repo init` 时，系统创建 `big.toml` 和 `.big/` 内部目录。
- 给定样例 inputs/outputs，当执行 `big commit` 时，系统创建一个 version，并写入 CAS 对象。
- 给定两个 version，当执行 `big diff` 时，系统可以显示 input/output 哈希变化。

## 验证

**命令：**
- `python -m pytest`：已通过，2 个测试。
- `$env:PYTHONPATH='D:\Code\App\big\src'; python -m big --help`：已通过，CLI help 可正常渲染。
- 在 `manual-lab/data/ManualChip/user/alice/APR` 上进行手工验证：已通过 `repo init`、两次 `commit`、`log`、`show --full` 和 `diff --verbose`。
