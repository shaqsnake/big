---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/ux-design-specification.md'
  - '_bmad-output/planning-artifacts/research-technical-architecture.md'
  - '_bmad-output/planning-artifacts/prd-validation-report.md'
workflowType: 'architecture'
project_name: 'BIG'
user_name: 'shaqsnake'
date: '2026-05-30'
lastStep: 8
status: 'complete'
completedAt: '2026-06-01'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (38 FR, 8 domains):**

| Domain | FR Range | MVP | Growth | Architecture Focus |
|--------|----------|-----|--------|--------------------|
| 制品集版本管理 | FR1-7, FR33 | 8 | 0 | 数据模型核心、配方哈希、输入校验 |
| 分支管理 | FR8-14 | 7 | 0 | 一分支一目录、分支指针移动、derived_from 语义边 |
| 血缘追溯 | FR15-17 | 1 | 2 | DAG 查询引擎、跨分支链接 |
| 分层存储 | FR19-23 | 3 | 2 | 生命周期状态机、存储策略迁移、Golden 冗余 |
| 仓库管理 | FR24-28 | 2 | 3 | GC 回收、统计监控、归档导出 |
| 系统集成 | FR29-32 | 1 | 3 | 子进程编排器、Python API、双向集成 |
| 跨流程版本管理 | FR34-36 | 1 | 2 | 跨分支依赖声明、变更预警 |
| DSO 存储优化 | FR37-39 | 0 | 3 | PPA 排名淘汰策略、存储水位管理、寻优分组 |

MVP 共 22 个 FR，Growth 共 16 个 FR。架构必须为 Growth 阶段的 FastCDC、流水线引擎、GUI、DSO 集成预留扩展点。

**Non-Functional Requirements (21 NFR, 5 dimensions):**

| Dimension | Key NFRs | Architecture Driver |
|-----------|----------|---------------------|
| 性能 | NFR1 读吞吐≥70% NAS直读; NFR2 带宽≥1GB/s; NFR4 commit额外开销<10%; NFR5 checkout<2x cp | CAS 直读设计（不用 FUSE）、异步哈希、硬链接物化 |
| 安全 | NFR7 权限检查100%; NFR8 审计不可篡改; NFR9 数据完整性100% | 分支级 ACL、append-only 审计日志、SHA-256 校验 |
| 可靠性 | NFR11 Golden 零丢失; NFR12 非Golden <0.01%; NFR13 Golden ≥2副本 | Golden 双写、CAS chunk 引用计数、副本一致性校验 |
| 可扩展性 | NFR15 ≥100万文件; NFR16 ≥1PB; NFR17 ≥10万版本历史; NFR21 ≥500 DSO cases | 元数据索引独立于存储池、分布式元数据就绪、分组聚合查询 |
| 集成 | NFR18 Python API; NFR19 子进程退出码捕获; NFR20 路径透明性 | Python SDK 层、子进程管理器、工作区路径虚拟化 |

### Scale & Complexity

- Primary domain: **系统级开发者工具** — CLI 核心 + CAS 存储引擎 + Electron GUI 可视化 + Python API 集成
- Complexity level: **高** — 领域模型非标准（制品集双中心）、I/O 性能硬约束、TB/PB 级数据规模、环形版本图语义修正为 DAG+语义边
- Estimated architectural components: **6 个核心子系统** — CLI 命令层、核心业务逻辑层、CAS 存储引擎、元数据管理、GUI 前端（Electron+Vue3）、Python API 层

### Technical Constraints & Dependencies

| Constraint | Source | Architecture Impact |
|------------|--------|---------------------|
| CentOS 生产环境 | PRD 开发者工具需求 | 不依赖新版内核特性；编译安装流程 |
| NAS 基础设施 | PRD 核心约束 | CAS 直读必须等于读 NAS 文件；不用 FUSE；一分支一目录映射到 NAS 路径 |
| Python 主要语言 (MVP) | PRD 语言策略 | 核心逻辑用 Python；I/O 热路径（FastCDC/CAS 拼接）预留 C/Rust 扩展点 |
| 无容器部署 | PRD 安装策略 | 编译安装包；不依赖 Docker/K8s |
| EDA 工具路径不变性 | PRD 领域约束 | checkout 后目录结构完全一致；硬链接/symlink 替换内容不改路径 |
| SSH 远程 CLI | UX 平台策略 | CLI 无 X11 依赖；纯文本输出适配终端宽度 |
| 现有 pds_xxx 系统双向集成 | PRD 集成架构 | 子进程编排模型；Python API 供 pds_xxx 调用 |
| 无 Git 依赖 | PRD 反模式 | BIG 自管理元数据和存储，不依赖外部 VCS |
| 数据模型不阻碍分布式 | PRD 跨站点约束 | 元数据和存储层分离；预留 Commit-Edge 扩展点 |

### Cross-Cutting Concerns Identified

| Concern | Impact Scope | Architecture Strategy |
|---------|-------------|----------------------|
| CAS 内容寻址存储 | 所有文件 I/O、commit、checkout、GC | 独立存储引擎层，文件级 CAS (MVP) → FastCDC 块级 (Growth) |
| 数据完整性与审计 | commit、promote、权限变更、Golden 操作 | SHA-256 写校验 + append-only 审计日志 + 定期全仓扫描 |
| 生命周期状态迁移 | commit、promote、GC、DSO 淘汰 | 状态机模型 + 存储策略回调 + 阶段跃迁事件 |
| 路径不变性保证 | checkout、branch switch | 工作区管理层——硬链接/symlink 在原路径替换文件内容 |
| 分支级访问控制 | 所有写操作、分支创建 | ACL 结合 Linux group 体系，分支为权限边界 |
| 跨分支依赖追踪 | lineage 查询、变更预警 | DAG 跨分支边 + 依赖声明注册 + 事件驱动预警 |
| 配方哈希与缓存 | pipeline 执行、commit 去重 | hash(all_dependencies) 作为缓存 Key，命中时跳过执行或复用输出 |
| 异步进度反馈 | commit（哈希计算）、checkout（大规模文件替换） | 事件总线 + 进度条（CLI ANSI / GUI Progress 组件） |

## Starter Template Evaluation

### Primary Technology Domain

BIG 是复合型系统级开发者工具，包含四个独立但共享核心逻辑的技术域：

1. **CLI 工具** — Python，面向工程师日常操作
2. **CAS 存储引擎** — Python（MVP）/ Python+C/Rust（Growth），核心 I/O 层
3. **GUI 前端** — Electron + Vue 3 + TypeScript + Vite，可视化与交互层
4. **Python SDK** — Python，系统集成接口

没有单一 Starter 覆盖全部，按层评估。

### CAS 存储引擎方案详细对比

**关键领域洞察：配方的参数本质上是文件**

芯片 EDA 流程中，工具参数不是简单键值对，而是 TCL 脚本和 YAML 配置文件（如 `floorplan.tcl`、`constraints.sdc`、`pdn_config.yaml`）。这意味着输入文件和参数文件在架构层面没有本质差异——都是文件、都需要 CAS 寻址去重、都需要纳入配方哈希计算。这一洞察对数据模型和 CAS 设计产生根本影响。

#### 方案总览

| 方案 | 最新版本 | 类型 | 去重粒度 | NAS 直读 | BIG 适配度 |
|------|---------|------|---------|---------|-----------|
| **A. 自建文件级 CAS** | — | 自建 | 文件级 | 原生直读 (1.0x) | MVP 完美 |
| **B. python-cas** | 1.7.2 | 库 | 对象级 | 需适配 | 中 |
| **C. Dulwich (Git Object Store)** | 1.2.5 | 库 | 对象级 (deflate) | 1.5-3x | 低 |
| **D. fastcdc + 自建 Pack** | 1.7.0 | 库+自建 | 块级 CDC | 1.3-1.5x | Growth 最优 |
| **E. LakeFS** | 1.81.1 (SDK) | 服务 | 对象级 | S3 网关延迟 | 低 |
| **F. B2SDK** | 2.12.0 | 服务+库 | 块级 CDC | 网络延迟 | 中低 |

#### A. 自建文件级 CAS（MVP 推荐）

**架构：** 文件 SHA-256 → `.big/cas/objects/ab/cd/abcd1234...`，两级目录哈希分片，文件直接存储在 NAS 路径上。</p>

**核心设计——统一依赖模型：**

```
ArtifactSet {
  dependencies: [FileRef],   # 输入文件 + 参数文件，统一 CAS 寻址
  outputs: [FileRef]         # 产出文件，CAS 寻址
}

FileRef {
  path: str,           # 相对路径
  cas_hash: str,       # SHA-256 内容哈希
  semantic_role: str,  # "input" | "param" | "config" | "output" —— 仅 UX 标签
  size: int,
}

recipe_hash = SHA-256(
  sorted([(ref.path, ref.cas_hash) for ref in dependencies])
)
```

关键点：输入文件和参数文件（TCL/YAML）统一走 CAS，区别仅在 `semantic_role` 标签。配方哈希基于所有依赖文件的 `(path, cas_hash)` 对，任何参数文件的内容变化都会导致配方哈希变化，缓存正确性有确定性保证。

| 维度 | 评价 |
|------|------|
| **NAS 直读性能** | 读放大 ≈ 1.0x — CAS 文件就在 NAS 上，直接 open() 读 |
| **参数文件去重** | MVP 文件级：相同 TCL/YAML 100% 去重；不同版本间各自存储完整副本 |
| **实现复杂度** | 极低 — 核心约 300 行 Python（含参数文件统一处理） |
| **MVP 适配度** | 完美 — 满足 22 个 MVP FR，NFR1/NFR2/NFR4 可达标 |
| **Growth 演进** | 加 fastcdc 块级层；参数文件的小修改场景天然适合 CDC 去重 |
| **风险** | 无 — 最简方案，零外部依赖 |

#### B. python-cas (1.7.2)

通用 CAS 抽象层，提供 MemoryCAS、FileCAS、RedisCAS 后端。

| 维度 | 评价 |
|------|------|
| NAS 直读 | FileCAS 可实现直读，但存储布局不支持硬链接物化 |
| 参数文件去重 | 对象级，与方案 A 等价 |
| BIG 适配问题 | 无 CDC 支持；API 抽象不匹配统一依赖模型；缺引用计数/GC/生命周期分层；社区活跃度低 |
| Growth 演进 | 无法演进到块级，需替换 |

**结论：抽象不匹配，不可演进。排除。**

#### C. Dulwich (1.2.5)

纯 Python Git 实现，提供 loose objects + packfiles 存储。

| 维度 | 评价 |
|------|------|
| NAS 直读 | packfiles 需 inflate 解压，读放大 1.5-3x |
| 参数文件去重 | 文本类 TCL 可能受益于行级 delta；二进制无效 |
| BIG 适配问题 | **致命**：SHA-1 哈希违反 NFR9；PRD 反模式"不模仿 Git"；EDA 二进制无 delta 效果；无生命周期分层 |
| Growth 演进 | 无法演进到 FastCDC |

**结论：与 PRD 核心约束冲突。排除。**

#### D. fastcdc (1.7.0) + 自建 Pack 格式（Growth 推荐）

**架构：** fastcdc 库对文件做内容定义分块，块以 Pack 文件格式存储，索引记录文件→chunk 映射。</p>

**参数文件的特殊收益：** TCL/YAML 参数文件的不同版本间通常只改几行，FastCDC 只需存储变化的 chunk。一个 50KB 的 TCL 文件改了 3 行，只存 ~10KB 新 chunk（而非完整 50KB 副本）。这对 DSO 场景（100+ case 共享大部分参数文件、只微调几行）尤其有价值。

**Growth 阶段的双层架构：**

```
热路径: 文件级 CAS cache → 硬链接物化到工作区（读放大 1.0x）
冷路径: fastcdc 块级 Pack → 物化时先还原为完整文件到 cache，再硬链接
```

| 维度 | 评价 |
|------|------|
| NAS 直读 | 冷数据读放大 1.3-1.5x（首次物化后缓存为热数据则 1.0x） |
| 参数文件去重 | **最优** — 50KB TCL 改 3 行，只存 ~10KB 差异 chunk |
| 实现复杂度 | 高 — Pack 格式设计、chunk 索引、并发写入、GC |
| MVP 适配度 | **不推荐 MVP** — 复杂度高且 EDA 去重基准数据未建立 |
| Growth 演进 | 在 MVP 文件级 CAS 上加装块层，数据零迁移 |

**结论：Growth 阶段首选，MVP 阶段不适用。**

#### E. LakeFS (SDK 1.81.1)

数据湖版本管理服务，Git-like 模型，底层依赖 S3/GCS。

| 问题 | 影响 |
|------|------|
| 需部署服务器 + PostgreSQL | 违反"编译安装、无容器"约束 |
| 依赖 S3 接口 | BIG 部署环境是 NAS 文件系统不是对象存储 |
| Git-like 模型 | 与 PRD 反模式约束冲突 |
| 无 CDC 块级去重 | 与方案 A 同等去重能力但架构更重 |

**排除。**

#### F. B2SDK (2.12.0)

Backblaze 云备份 SDK，内置 CDC 分块和增量上传。

| 问题 | 影响 |
|------|------|
| 数据在云端 | 需网络下载，违反 NFR1 NAS 直读约束 |
| 框架绑定 Backblaze | 不适配 NAS 本地场景 |
| SHA-1 哈希 | 不满足 NFR9 SHA-256 要求 |

**排除。**

#### 对比矩阵

| 维度 | A. 自建文件级 | B. python-cas | C. Dulwich | D. fastcdc+Pack | E. LakeFS | F. B2SDK |
|------|:-----------:|:-----------:|:---------:|:-------------:|:---------:|:-------:|
| NAS 直读 ≥70% | **1.0x** | ~1.0x | 1.5-3x | 1.0-1.5x | 网络延迟 | 网络延迟 |
| 参数文件增量去重 | 整文件 | 整文件 | 行级delta(文本) | **块级CDC** | 整对象 | 块级CDC |
| MVP 实现成本 | **极低** | 低 | 中 | 高 | 高 | 中 |
| Growth 可演进 | **是** | 否 | 否 | — | 否 | 否 |
| 无外部依赖 | **是** | 是(+1) | 是(+1) | 是(+1) | 否 | 否 |
| 符合 PRD 约束 | **完全** | 部分 | 违反 | 完全 | 违反 | 违反 |
| SHA-256 完整性 | **是** | 可配置 | 否(SHA-1) | **是** | 自定义 | 否(SHA-1) |

### 推荐路径

**MVP：方案 A（自建文件级 CAS + 统一依赖模型）**
- 输入文件和参数文件（TCL/YAML）统一走 CAS，区别仅在语义标签
- 配方哈希 = `SHA-256(sorted((path, cas_hash) for all dependencies))`
- 零外部依赖，核心 ~300 行 Python
- 同步建立 EDA 文件去重基准测试（包含参数文件的增量修改样本）

**Growth：方案 A + 方案 D（文件级热缓存 + fastcdc 块级冷存储）**
- 参数文件的微小修改场景天然适合 CDC 去重，优先验证
- DSO 场景（100+ case 共享参数文件）可获最大去重收益
- 基准测试数据指导 FastCDC 参数选择

核心优势：**MVP 零风险起步 → Growth 无缝叠加 → 数据零迁移 → 参数文件增量去重自然承接**

### CLI 框架评估

| 选项 | 优势 | 劣势 | 结论 |
|------|------|------|------|
| Click (~8.1) | 生态最成熟、装饰器风格、嵌套子命令原生支持、Tab 补全 | 异步支持弱 | **选用** |
| Typer (~0.12) | 类型注解驱动、自动帮助 | 底层仍是 Click，复杂命令定制受限 | 备选 |
| argparse | 零依赖 | 样板代码多、嵌套笨拙 | 排除 |

选择理由：BIG 命令体系有清晰的嵌套结构（`big pipeline run/status`、`big repo init/config/stats`），Click 的 `group` + `command` 天然匹配。行业标准，工程师熟悉度高，符合"最少认知负荷"原则。

### Electron GUI 框架评估

| 选项 | 优势 | 劣势 | 结论 |
|------|------|------|------|
| electron-vite (~2.x) | 专为 Electron+Vue 设计、Vite HMR、main/preload/renderer 分层 | 社区项目 | **选用** |
| Electron Forge (~7.x) | 官方工具链 | Vue 非原生、配置繁琐 | 排除 |
| 手动搭建 | 完全控制 | 重复造轮子 | 排除 |

选择理由：electron-vite 与 UX 设计规格（Vue 3 + Vite + Electron + TypeScript）完全对齐，一条命令生成项目骨架，main/preload/renderer 安全隔离架构开箱即用。

### 元数据存储

SQLite（嵌入式、零运维、单文件部署），匹配 CentOS NAS 单机场景。百万文件+十万版本规模下通过索引优化满足 NFR17 查询性能。

### Selected Starters

**CLI 项目（Python）：**

- 框架：Click ~8.1
- 项目结构：标准 Python 包（src layout），pyproject.toml 管理
- 初始化：手动创建

**GUI 项目（Electron + Vue 3）：**

- 框架：electron-vite ~2.x
- 初始化命令：

```bash
npm create @quick-start/electron big-gui -- --template vue-ts
```

- 架构决策由 Starter 提供：
  - **进程隔离：** main process（Node.js）+ renderer process（Vue 3）+ preload bridge
  - **构建工具：** Vite（HMR < 300ms）
  - **TypeScript：** 严格模式，全项目类型覆盖
  - **代码组织：** src/main/ + src/preload/ + src/renderer/ 三层分隔

**CAS 引擎 + 核心业务逻辑：**

- 自定义 Python 包，作为 CLI 和 SDK 的共享核心
- 包结构：`big.core`（统一依赖数据模型、CAS 引擎、元数据管理、生命周期状态机）
- 存储后端：文件系统 CAS pool + SQLite 元数据库（统一依赖字典表索引）

**注意：** 使用上述命令初始化 GUI 项目应作为首个实现 Story。

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- 元数据存储架构（SQLite + DAG 存储模式）
- 统一依赖数据模型（输入+参数文件统一 CAS）
- CLI/GUI/SDK 与核心逻辑的通信边界

**Important Decisions (Shape Architecture):**
- 权限模型设计
- 工作区状态管理
- CAS 写入完整性保证
- 日志与配置架构

**Deferred Decisions (Post-MVP):**
- FastCDC 参数选择（需基准数据）
- 闭包表引入时机
- HTTP API schema 细化
- 分布式元数据迁移路径

### Data Architecture

#### SQLite 作为元数据存储的深度论证

**行业验证：Fossil SCM 的先行证明**

SQLite 之父 Richard Hipp 同时创造了 Fossil SCM——一个完全基于 SQLite 存储 VCS 元数据（包括 DAG）的版本控制系统，运行 15+ 年。Fossil 的核心设计：

- **邻接表 + 递归 CTE**：`plink(pid, cid)` 表存储 DAG 边，不使用闭包表。Hipp 判断在 Fossil 的 append-mostly 工作负载下，闭包表的维护成本大于查询收益。
- **整数 RID 外键**：所有图边用整数 `rid` 引用，SHA 哈希只存在 `blob` 表。整数比较在 SQLite 中远快于字符串比较（JOIN 性能差异约 5-10x）。
- **元数据可重建**：Schema 分两层——Schema1（不可变：blob/delta）和 Schema2（可重建：plink/mlink/event/leaf）。`fossil rebuild` 可从 Schema1 完全重建 Schema2。

**Git 的反思：为什么它加了 commit-graph 文件**

Git 不用数据库，但它的经历说明纯对象数据库的局限：

| 问题 | 对象数据库 | commit-graph 文件 |
|------|-----------|-------------------|
| 父节点查找 | SHA 哈希→二分搜索 O(log N) | 整数位置→O(1) |
| 拓扑排序 | 需遍历全图 | generation number 提前终止 |
| `git log -- path` | 逐 commit 检查 tree | Bloom filter 跳过 90% 无关节点 |
| merge-base 计算 | 分钟级（1M+ commits） | 亚秒级 |

Git 花了多年加了二进制 commit-graph 文件，本质上在重建一个简化的数据库索引。SQLite 从一开始就具备这些能力。

**SQLite 递归 CTE 实测性能（本机 benchmark）**

100K 节点 + 4477 跨分支边，磁盘数据库：

| 操作 | 耗时 | 对应 NFR |
|------|------|---------|
| 血缘追溯 depth 30 | **0.3ms** | NFR3: <30s（超标 10 万倍） |
| 正向影响分析 depth 15 | **0.1ms** | FR17 影响分析 |
| 分支日志（筛选 20 条） | **0.1ms** | FR3 查看历史 |
| 配方哈希缓存查找 | **<0.01ms** | FR7 配方缓存命中 |
| 单次 commit 写入 | **1.6ms** | NFR4: <10% 开销 |
| 全分支深度 500 追溯 | **0.3ms** | 极端场景 |

数据库文件：100K 版本 + 10 万条边 = **16.9 MB**。

**Python 集成：零门槛**

`sqlite3` 是 Python 标准库模块，零安装、零配置、零依赖：

```python
import sqlite3

conn = sqlite3.connect('.big/metadata.db')
conn.execute('WITH RECURSIVE lineage(...) SELECT ...')
```

无需 pip install，无需运维守护进程，数据库文件随仓库走。

**SQLite 并发与 NAS 部署**

| 场景 | SQLite 表现 | BIG 匹配度 |
|------|-----------|-----------|
| 单写者 + 多读者 | 完美（WAL 模式） | CLI 操作天然单写 |
| 10 人同分支 commit | 排队写入，每次 <10ms | NFR6 要求 10 人并发，满足 |
| NAS 文件系统 | 使用 rollback journal（不支持 WAL 的共享内存） | 不影响 BIG 读写模式 |

**图数据库 vs SQLite 的临界点分析**

学术研究（Vicknair 2010, Barros 2015, Jouili 2013）共识：

| 遍历深度 | 关系数据库（有索引） | 图数据库 |
|---------|-------------------|---------|
| 1-2 跳 | 等效或更快 | 持平 |
| 3-5 跳 | 可竞争 | 开始领先 |
| 6+ 跳 | 显著落后 | 10-100x 更快 |

BIG 的查询模式以**深度优先线性链**为主（沿 derived_from 回溯），分支因子极低，不是社交网络式的广度多跳遍历。这正是 SQLite 递归 CTE 最高效的场景，图数据库的优势无法体现。

**结论：SQLite 存储 DAG，邻接表 + 递归 CTE 模式，借鉴 Fossil 的整数外键、双向索引、元数据可重建设计。**

#### 核心表结构设计

借鉴 Fossil 的 Schema1/Schema2 分层思想，BIG 的 SQLite 表分为两层：

**Schema1 — 不可变核心（不可重建，不可删除）：**

```sql
-- 制品集版本：DAG 节点
CREATE TABLE artifact_set(
    id INTEGER PRIMARY KEY,           -- 整数 RID，图边引用此列
    branch_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    recipe_hash TEXT NOT NULL,         -- 统一依赖配方哈希
    lifecycle TEXT NOT NULL DEFAULT 'Exploring',
    created_at REAL NOT NULL,
    author TEXT NOT NULL
);
CREATE INDEX idx_recipe ON artifact_set(recipe_hash);
CREATE INDEX idx_branch_lifecycle ON artifact_set(branch_id, lifecycle);

-- DAG 边：邻接表（借鉴 Fossil plink）
CREATE TABLE plink(
    pid INTEGER NOT NULL REFERENCES artifact_set(id),
    cid INTEGER NOT NULL REFERENCES artifact_set(id),
    is_derived BOOLEAN NOT NULL DEFAULT 0,  -- 0=线性父节点, 1=derived_from 语义边
    depth INTEGER NOT NULL DEFAULT 1,
    UNIQUE(pid, cid)
);
CREATE INDEX plink_rev ON plink(cid, pid);   -- 血缘回溯（子→父）
CREATE INDEX plink_fwd ON plink(pid, cid);   -- 影响分析（父→子）

-- 统一依赖字典表（去重：同一文件被多个制品集引用）
CREATE TABLE file_ref(
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    cas_hash TEXT NOT NULL,           -- SHA-256
    size INTEGER NOT NULL,
    semantic_role TEXT NOT NULL DEFAULT 'input',  -- UX 标签，非架构差异
    UNIQUE(path, cas_hash)
);
CREATE INDEX idx_cas_hash ON file_ref(cas_hash);

-- 制品集→依赖 关联表
CREATE TABLE dependency(
    artifact_set_id INTEGER NOT NULL REFERENCES artifact_set(id),
    file_ref_id INTEGER NOT NULL REFERENCES file_ref(id),
    PRIMARY KEY(artifact_set_id, file_ref_id)
);

-- 制品集→产出 关联表
CREATE TABLE output(
    artifact_set_id INTEGER NOT NULL REFERENCES artifact_set(id),
    file_ref_id INTEGER NOT NULL REFERENCES file_ref(id),
    PRIMARY KEY(artifact_set_id, file_ref_id)
);
```

**Schema2 — 可重建元数据（可从 Schema1 + CAS 完全重建）：**

```sql
-- 分支
CREATE TABLE branch(
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    owner TEXT NOT NULL,
    group_name TEXT NOT NULL,
    mode INTEGER NOT NULL DEFAULT 420,  -- 类 Linux 权限位
    head_id INTEGER REFERENCES artifact_set(id),
    created_at REAL NOT NULL
);

-- 工作区状态（替代 .big/HEAD 文件方案）
CREATE TABLE workspace(
    key TEXT PRIMARY KEY,              -- 'current_branch', 'current_version', etc.
    value TEXT NOT NULL
);

-- 审计日志（append-only，不可篡改）
CREATE TABLE audit_log(
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    detail TEXT,
    timestamp REAL NOT NULL
);

-- 叶子节点缓存（借鉴 Fossil leaf 表，加速分支顶端查询）
CREATE TABLE leaf(
    artifact_set_id INTEGER PRIMARY KEY REFERENCES artifact_set(id)
);
```

**关键设计决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| DAG 存储模式 | 邻接表 + 递归 CTE | Fossil 验证的模式；BIG 的深窄 DAG 形态无需闭包表 |
| 外键类型 | 整数 RID | 整数比较比 SHA 字符串快 5-10x（Fossil 实践） |
| 边类型区分 | `is_derived` 布尔列 | 线性父节点与 derived_from 语义边共存一表，同一个递归 CTE 可同时遍历 |
| 工作区状态 | SQLite workspace 表 | 统一元数据管理，减少文件格式解析负担 |
| 审计日志 | SQLite 表（append-only） | 统一存储，SQLite 触发器可设为只读保护 |
| 输入/参数统一 | file_ref 字典表 + semantic_role 标签 | 输入文件和参数文件（TCL/YAML）结构完全相同，区别仅 UX 展示 |
| 配方哈希 | `recipe_hash` 列存于 artifact_set | 避免每次查询时重新计算，commit 时一次性写入 |
| 叶子缓存 | 预计算 leaf 表 | 10 万+ 版本时 branch head 查询加速 |

**Growth 阶段可选优化路径：**

| 触发条件 | 优化手段 |
|---------|---------|
| 递归 CTE 追溯逼近 30s 阈值 | 加 depth 列限制深度 + 预计算叶子表 |
| 10 万+ 版本正向影响分析慢 | 引入闭包表 `closure(ancestor, descendant, depth)` |
| 极端规模（百万级） | 迁移至 PostgreSQL（SQL 语法几乎不变） |

### Authentication & Security

#### 权限模型：类 Linux 文件权限

PRD 要求分支级权限，概念 ≤ 5 个（NFR10），与 Linux group 对齐：

```sql
-- 分支权限：直接类比 Linux 文件权限
-- branch.owner = 创建者（类文件 owner）
-- branch.group_name = Linux group 映射
-- branch.mode = 权限位（类 chmod）
--   420 (0644 octal) = owner 读写 / group 读 / other 无
--   440 (0660 octal) = owner 读写 / group 读写 / other 无
```

权限检查逻辑：

```python
import os, stat

def check_write_permission(branch, username):
    """类 Linux 文件权限检查"""
    if username == branch.owner:
        return bool(branch.mode & stat.S_IWUSR)
    groups = os.getgrouplist(username)  # 获取用户所属 Linux group
    if branch.group_name in groups:
        return bool(branch.mode & stat.S_IWGRP)
    return bool(branch.mode & stat.S_IWOTH)
```

5 个核心概念：**用户（owner）、组（group）、读（r）、写（w）、所有者（owner）**——完全对齐 Linux 心智模型，零学习成本。

#### CAS 写入完整性保证

```python
import hashlib, os, tempfile

def cas_write(source_path, cas_root):
    """CAS 写入：计算→临时写入→回读校验→原子 rename"""
    # 1. 流式计算 SHA-256
    sha = hashlib.sha256()
    with open(source_path, 'rb') as f:
        while chunk := f.read(1 << 20):  # 1MB chunks
            sha.update(chunk)
    cas_hash = sha.hexdigest()

    # 2. 构造 CAS 路径
    cas_path = os.path.join(cas_root, 'objects', cas_hash[:2], cas_hash)

    # 3. 已存在则跳过（去重）
    if os.path.exists(cas_path):
        return cas_hash

    # 4. 写入临时文件
    os.makedirs(os.path.dirname(cas_path), exist_ok=True)
    tmp_path = cas_path + '.tmp.' + str(os.getpid())
    with open(source_path, 'rb') as src, open(tmp_path, 'wb') as dst:
        while chunk := src.read(1 << 20):
            dst.write(chunk)

    # 5. 回读校验
    verify_sha = hashlib.sha256()
    with open(tmp_path, 'rb') as f:
        while chunk := f.read(1 << 20):
            verify_sha.update(chunk)
    if verify_sha.hexdigest() != cas_hash:
        os.unlink(tmp_path)
        raise IntegrityError(f"CAS write verification failed for {cas_hash}")

    # 6. 原子 rename
    os.rename(tmp_path, cas_path)
    return cas_hash
```

### API & Communication Patterns

#### 三层级通信架构

```
┌─────────────────────────────────────────────┐
│                  GUI (Electron)              │
│          Vue 3 + Ant Design Vue             │
│              TanStack Query                  │
├─────────────────────────────────────────────┤
│           preload / IPC bridge               │
└──────────────┬──────────────────────────────┘
               │ HTTP API (localhost)
┌──────────────▼──────────────────────────────┐
│           Python Core Layer                  │
│   big.core (CAS引擎 / 元数据 / 状态机)       │
├─────────────────────────────────────────────┤
│  HTTP Server (FastAPI)  │  CLI (Click)       │
│  - GUI 专用接口          │  - 进程内直接调用   │
│  - localhost only        │  - 无 IPC 开销     │
├─────────────────────────┴───────────────────┤
│           Python SDK (import big)            │
│         直接调用 big.core 函数               │
└─────────────────────────────────────────────┘
```

**决策理由：**

| 通信方式 | 适用场景 | 选择 |
|---------|---------|------|
| CLI ↔ 核心 | 进程内函数调用 | **直接调用** — MVP 最简，无 IPC 开销 |
| GUI ↔ 核心 | 跨语言（JS→Python）| **本地 HTTP API** — schema 稳定，GUI/CLI 共用 |
| SDK ↔ 核心 | Python 进程内 | **直接 import** — SDK 即核心层的 Python 包 |

**HTTP API 设计原则（Growth 阶段细化，MVP 仅实现核心端点）：**

- 仅监听 `localhost`，无远程访问
- FastAPI 自动生成 OpenAPI schema，GUI 端可用类型安全的客户端
- MVP 端点：`/api/branches`, `/api/artifacts/{id}`, `/api/lineage/{id}`, `/api/stats`

### Frontend Architecture

**状态管理：Pinia（Vue 3 官方推荐）**

全局状态需求明确：当前分支、选中版本、存储指标、生命周期筛选器——跨组件共享场景多，Pinia 是 Vue 3 生态标准。

**数据获取：TanStack Query（Vue Query）**

血缘图和存储指标需要实时性好；自动轮询和缓存减少手动管理；错误重试和 stale-while-revalidate 提升用户体验。

### Infrastructure & Deployment

**构建产物：**

| 产物 | 格式 | 安装方式 |
|------|------|---------|
| CLI + SDK | Python wheel | `pip install big-0.1.0-py3-none-any.whl` |
| GUI | Electron 安装包 | AppImage（CentOS 7+）/ rpm |
| 核心公共依赖 | 随 CLI wheel 一同安装 | pip 自动解析 |

**配置管理：**

```toml
# .big/config.toml（仓库级，优先级最高）
[cas]
type = "file"
path = ".big/cas/objects"

[storage]
golden_replicas = 2
golden_paths = ["/nas/golden-backup-1", "/nas/golden-backup-2"]
high_watermark = "85%"

[pipeline]
default_template = "rtl-to-backend"
```

```toml
# ~/.bigconfig.toml（全局，优先级次之）
[user]
name = "shaqsnake"

[defaults]
lifecycle = "Candidate"
```

优先级：仓库 `.big/config.toml` > 全局 `~/.bigconfig.toml` > 内置默认值。

**日志：**

- Python `logging` 模块，结构化输出
- 文件日志：`~/.big/logs/big-YYYYMMDD.log`（自动轮转，保留 30 天）
- CLI stderr：简洁人类可读格式
- `--verbose` / `--debug` 控制输出详细程度

### Decision Impact Analysis

**实施顺序：**

1. `big.core` 包骨架（数据模型 + CAS 引擎 + SQLite 初始化）
2. CLI 核心命令（init / commit / checkout / log / branch）
3. Python SDK（import big 对外暴露）
4. HTTP API 服务端（FastAPI，Growth 阶段与 GUI 并行）
5. GUI 初始化（electron-vite 脚手架）
6. GUI 核心视图（版本树 + 配方详情）

**跨组件依赖关系：**

```
big.core ←──── CLI (Click)
    ↑
    ├── Python SDK (import big)
    │
    └── HTTP API (FastAPI) ←──── GUI (Electron + Vue 3)
```

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 28 areas where AI agents could make different choices

### Naming Patterns

**Database Naming Conventions:**

| 规则 | 约定 | 示例 |
|------|------|------|
| 表名 | snake_case，复数概念用单数（实体名） | `artifact_set`, `plink`, `file_ref` |
| 列名 | snake_case | `cas_hash`, `recipe_hash`, `is_derived` |
| 主键 | `id`（单列）或 `表名_id`（外键引用时） | `id`, `branch_id`, `artifact_set_id` |
| 外键 | `引用表单数_id` | `branch_id`, `file_ref_id` |
| 布尔列 | `is_` / `has_` 前缀 | `is_derived`, `is_prim` |
| 时间列 | `_at` 后缀，REAL 类型（Julian day 或 Unix epoch） | `created_at`, `timestamp` |
| 索引 | `idx_表名_列名` | `idx_artifact_set_recipe_hash` |
| 唯一约束 | 内联 `UNIQUE` 而非命名约束 | `UNIQUE(pid, cid)` |

**API Naming Conventions:**

| 规则 | 约定 | 示例 |
|------|------|------|
| URL 路径 | kebab-case，复数名词 | `/api/artifact-sets`, `/api/branches` |
| URL 路径参数 | kebab-case | `/api/artifact-sets/{id}` |
| 查询参数 | snake_case | `?branch_id=1&lifecycle=candidate` |
| HTTP 动词 | 标准 REST 语义 | GET 查询, POST 创建, PATCH 部分更新 |
| HTTP 状态码 | 精确使用 | 200 成功, 201 创建, 404 不存在, 409 冲突, 422 校验失败 |

**Code Naming Conventions:**

| 层 | 约定 | 示例 |
|---|------|------|
| Python 包/模块 | snake_case | `big/core/cas_engine.py` |
| Python 类 | PascalCase | `ArtifactSet`, `FileRef`, `CASEngine` |
| Python 函数/方法 | snake_case | `commit_artifact_set()`, `compute_recipe_hash()` |
| Python 常量 | UPPER_SNAKE | `DEFAULT_LIFECYCLE`, `CAS_HASH_ALGO` |
| Python 私有方法 | `_` 前缀 | `_validate_inputs()`, `_write_cas_object()` |
| Vue 组件 | PascalCase 文件 + 组件名 | `LineageTree.vue` → `<LineageTree>` |
| Vue 组合式函数 | `use` 前缀 + camelCase | `useArtifactSet()`, `useLineage()` |
| TypeScript 类型/接口 | PascalCase | `ArtifactSet`, `FileRef` |
| TypeScript 变量/函数 | camelCase | `artifactId`, `fetchLineage()` |
| CSS 类名 | BEM: `block__element--modifier` | `lineage-tree__node--golden` |

### Structure Patterns

**Project Organization:**

```
big/                           # 仓库根目录
├── src/big/                   # Python 核心包（src layout）
│   ├── core/                  # 核心业务逻辑（CLI/SDK/GUI 共享）
│   │   ├── models.py          # 数据模型定义
│   │   ├── cas.py             # CAS 存储引擎
│   │   ├── metadata.py        # SQLite 元数据管理
│   │   ├── lifecycle.py       # 生命周期状态机
│   │   ├── lineage.py         # 血缘追溯查询
│   │   └── workspace.py       # 工作区管理
│   ├── cli/                   # CLI 命令入口
│   │   ├── main.py            # Click group 入口
│   │   ├── commit.py
│   │   ├── checkout.py
│   │   ├── log_cmd.py         # 避免 log.py 与 stdlib 冲突
│   │   └── branch_cmd.py
│   ├── sdk/                   # Python SDK 入口
│   │   └── __init__.py        # export big.commit(), big.checkout() 等
│   └── api/                   # HTTP API 服务（Growth 阶段）
│       └── server.py
├── big-gui/                   # Electron + Vue 3 独立项目
│   ├── src/main/              # Electron main process
│   ├── src/preload/           # preload bridge
│   └── src/renderer/          # Vue 3 应用
│       ├── components/        # 通用组件
│       ├── views/             # 页面级组件
│       ├── composables/       # 组合式函数
│       ├── stores/            # Pinia stores
│       └── types/             # TypeScript 类型定义
├── tests/                     # 测试目录
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── conftest.py            # 共享 fixtures
├── pyproject.toml             # Python 项目配置
└── docs/                      # 文档
```

**关键规则：**

| 规则 | 说明 |
|------|------|
| core 是唯一真相源 | CLI/SDK/API 不能包含业务逻辑，只能调用 core |
| CLI 命令文件命名 | `{command}_cmd.py` 避免 Python 标准库命名冲突 |
| 测试位置 | `tests/` 顶层目录，不与源码混放 |
| GUI 独立项目 | `big-gui/` 有自己的 package.json，不与 Python 混合 |
| 类型定义集中 | Python 类型在 `models.py`，TS 类型在 `renderer/types/` |

### Format Patterns

**API Response Formats:**

```python
# 成功响应
{
    "data": { ... },           # 业务数据
    "meta": {                  # 可选元数据
        "page": 1,
        "per_page": 20,
        "total": 150
    }
}

# 错误响应
{
    "error": {
        "code": "COMMIT_VALIDATION_FAILED",
        "message": "输入文件完整性校验失败",
        "detail": "缺失文件: rtl/top.v, sdc/timing.sdc",
        "suggestion": "检查 --inputs 路径模式是否覆盖所有必需输入"
    }
}
```

**Data Exchange Formats:**

| 规则 | 约定 |
|------|------|
| JSON 字段命名 | snake_case（与 Python/SQL 一致） |
| 日期时间 | ISO 8601 字符串：`2026-05-30T14:30:00Z` |
| 布尔值 | `true` / `false`（JSON 原生，不使用 0/1） |
| 空值 | 显式 `null`（而非省略字段） |
| 哈希值 | 小写十六进制字符串：`"a1b2c3d4..."` 不缩写 |
| 路径 | POSIX 风格相对路径：`"rtl/top.v"` 不使用反斜杠 |
| 文件大小 | 整数字节数 |

### Communication Patterns

**Event System Patterns:**

| 规则 | 约定 | 示例 |
|------|------|------|
| 事件名 | `domain.action` — 小写点分 | `artifact_set.committed`, `lifecycle.promoted` |
| 事件载荷 | `{type, timestamp, payload}` 三字段固定结构 | 见下方 |
| 事件版本 | payload 内嵌 `version` 字段 | `"version": 1` |
| 进度事件 | `domain.action.progress` 子类型 | `cas.hashing.progress` |

```python
# 标准事件载荷结构
{
    "type": "artifact_set.committed",
    "timestamp": "2026-05-30T14:30:00Z",
    "payload": {
        "version": 1,
        "id": 42,
        "branch": "fp-exploration",
        "recipe_hash": "a1b2c3d4...",
        "lifecycle": "Candidate"
    }
}

# 进度事件载荷
{
    "type": "cas.hashing.progress",
    "timestamp": "2026-05-30T14:30:01Z",
    "payload": {
        "version": 1,
        "current": 1500,
        "total": 5000,
        "elapsed_seconds": 3.2
    }
}
```

**State Management Patterns:**

| 规则 | 约定 |
|------|------|
| Pinia store 命名 | `use{Domain}Store` — `useArtifactStore`, `useLineageStore` |
| 状态更新 | 不可变更新（Vue reactive 自动处理） |
| 异步操作 | 在 actions 中处理，不直接修改 state |
| 数据获取 | 通过 TanStack Query，不走 Pinia actions |
| Store 职责 | 仅存 UI 状态（选中项、筛选器、当前分支），不缓存 API 数据 |

### Process Patterns

**Error Handling Patterns:**

| 层 | 处理方式 |
|---|---------|
| core | 抛出自定义异常类（`big.core.errors.CommitValidationError` 等），包含 `message` + `suggestion` + `detail` |
| CLI | 捕获异常 → 格式化输出（✗ 红色 + 原因 + 建议操作），退出码 1 |
| HTTP API | 捕获异常 → 映射为标准错误响应格式 + 适当 HTTP 状态码 |
| SDK | 直接传播 core 异常，由调用方决定处理策略 |
| GUI | HTTP API 返回的错误 → Alert 内联展示 + 操作按钮 |

**自定义异常层次：**

```
BigError
├── ValidationError          # 422: 输入校验失败
│   ├── InputIntegrityError  # commit 时输入文件缺失/损坏
│   └── RecipeConflictError  # 配方哈希冲突
├── StateError               # 409: 状态不允许操作
│   ├── LifecycleError       # 生命周期跃迁违规
│   └── WorkspaceDirtyError  # checkout 时未提交变更
├── PermissionError          # 403: 权限不足
├── NotFoundError            # 404: 实体不存在
└── StorageError             # 500: CAS/元数据写入失败
    ├── IntegrityError       # CAS 写入校验失败
    └── ConcurrencyError     # SQLite 写入冲突
```

**Loading State Patterns:**

| 场景 | CLI | GUI |
|------|-----|-----|
| commit 哈希计算 | 进度条 `████░░░░ 60%` | Progress 组件（环形/条形） |
| checkout 文件替换 | 进度条 + 文件计数 | Progress + 文件列表实时更新 |
| API 数据加载 | — | Spin + 骨架屏（匹配实际布局） |
| 长时间运算（>5s） | 定期输出状态更新 | 预估剩余时间（可选） |
| 慢操作（≤1s） | 无进度指示 | 无进度指示 |

### Enforcement Guidelines

**All AI Agents MUST:**

- 所有数据库操作通过 `big.core.metadata` 模块执行，禁止直接写 SQL（除 metadata 模块本身）
- 所有 CAS 操作通过 `big.core.cas` 模块执行，禁止直接读写 `.big/cas/objects/`
- CLI 命令只做参数解析 + 调用 core 函数 + 格式化输出，不包含业务逻辑
- 新增数据库表必须同时更新 Schema2 分类，并在 `tests/` 中添加 rebuild 验证测试
- API 端点必须在 `big.api.server` 中注册路由，保持一致的响应格式
- GUI 组件中不允许直接 `fetch`，必须通过 TanStack Query 的 `useQuery` / `useMutation`
- 所有错误消息必须包含"做了什么"（message）+"为什么"（detail）+"接下来怎么办"（suggestion）

**Pattern Enforcement:**

- Python: ruff 格式化 + mypy 类型检查 + 自定义 ruff 规则禁止 `big.core` 外部直接 import sqlite3
- TypeScript: ESLint + Prettier + 严格 tsconfig
- 测试覆盖：核心模块（core/）≥ 90%，CLI/API ≥ 70%
- CI 检查：ruff + mypy + pytest + eslint + tsc --noEmit

### Pattern Examples

**Good Examples:**

```python
# core 层：业务逻辑在这里
def commit_artifact_set(message, inputs, params, outputs, branch):
    dependencies = [_resolve_file_ref(f, 'input') for f in inputs]
    dependencies += [_resolve_file_ref(f, 'param') for f in params]
    recipe_hash = compute_recipe_hash(dependencies)
    # ... CAS 写入、元数据更新 ...
    return artifact_set

# CLI 层：薄壳，只做 I/O
@cli.command()
@click.option('-m', '--message', required=True)
@click.option('--inputs', multiple=True)
def commit(message, inputs):
    try:
        result = core.commit_artifact_set(message, inputs, ...)
        click.echo(f"✓ Committed as {result.id} [{result.lifecycle}]")
    except InputIntegrityError as e:
        click.echo(f"✗ Commit failed: {e.message}")
        click.echo(f"  Suggestion: {e.suggestion}")
        sys.exit(1)
```

**Anti-Patterns:**

```python
# 反模式：CLI 包含业务逻辑
@cli.command()
def commit(message):
    conn = sqlite3.connect('.big/metadata.db')  # 禁止：直接操作数据库
    cas_hash = hashlib.sha256(open(path).read().encode()).hexdigest()  # 禁止：绕过 CAS 模块
    conn.execute('INSERT INTO artifact_set ...')  # 禁止：SQL 散落各处

# 反模式：错误消息无建议
click.echo(f"Error: commit failed")  # 缺少原因和建议

# 反模式：GUI 直接 fetch
const res = await fetch('/api/artifact-sets')  # 禁止：必须用 TanStack Query
```

## Project Structure & Boundaries

### Complete Project Directory Structure

```
big/                                # 仓库根目录
├── pyproject.toml                  # Python 项目配置（依赖、构建、元数据）
├── README.md                       # 项目说明
├── LICENSE                         # 开源许可证
├── Makefile                        # 开发常用命令快捷入口
├── .github/
│   └── workflows/
│       ├── ci.yml                  # ruff + mypy + pytest + eslint + tsc
│       └── release.yml             # 发布流水线（wheel + Electron 打包）
├── src/
│   └── big/                        # Python 核心包（src layout）
│       ├── __init__.py             # 版本号 + 公共 API 导出
│       ├── core/                   # 核心业务逻辑（CLI/SDK/GUI 共享）
│       │   ├── __init__.py
│       │   ├── models.py           # 数据模型（ArtifactSet, FileRef, Branch）
│       │   ├── cas.py              # CAS 存储引擎（文件级 + FastCDC 扩展点）
│       │   ├── metadata.py         # SQLite 元数据管理（Schema1/Schema2）
│       │   ├── lifecycle.py        # 生命周期状态机 + 存储策略回调
│       │   ├── lineage.py          # 血缘追溯查询（递归 CTE）
│       │   ├── workspace.py        # 工作区管理（硬链接/symlink 物化）
│       │   ├── branch.py           # 分支管理（创建/切换/指针移动）
│       │   ├── repo.py             # 仓库初始化与配置
│       │   ├── errors.py           # 自定义异常层次（BigError 子类）
│       │   ├── events.py           # 事件总线（domain.action 格式）
│       │   ├── config.py           # 配置管理（仓库级/全局/默认）
│       │   ├── audit.py            # 审计日志（append-only 写入）
│       │   ├── permission.py       # 权限检查（类 Linux 文件权限）
│       │   ├── gc.py               # GC 回收（引用计数 + 生命周期淘汰）
│       │   ├── storage.py          # 分层存储策略（Exploring→Golden）
│       │   ├── pipeline.py         # 子进程编排器（Growth 阶段）
│       │   ├── cross_branch.py     # 跨分支依赖声明与预警（Growth）
│       │   └── dso.py              # DSO 存储优化策略（Growth）
│       ├── cli/                    # CLI 命令入口（薄壳层）
│       │   ├── __init__.py
│       │   ├── main.py             # Click group 入口（big --help）
│       │   ├── init_cmd.py
│       │   ├── commit_cmd.py
│       │   ├── checkout_cmd.py
│       │   ├── log_cmd.py          # 避免 log.py 与 stdlib 冲突
│       │   ├── branch_cmd.py
│       │   ├── promote_cmd.py
│       │   ├── lineage_cmd.py
│       │   ├── repo_cmd.py
│       │   └── pipeline_cmd.py
│       ├── sdk/                    # Python SDK 入口
│       │   └── __init__.py         # export big.commit(), big.checkout() 等
│       └── api/                    # HTTP API 服务（Growth 阶段）
│           ├── __init__.py
│           ├── server.py           # FastAPI 应用 + 路由注册
│           ├── routes/
│           │   ├── branches.py
│           │   ├── artifacts.py
│           │   ├── lineage.py
│           │   └── stats.py
│           └── deps.py             # 依赖注入（get_db_conn, get_cas_engine）
├── big-gui/                        # Electron + Vue 3 独立项目
│   ├── package.json
│   ├── electron.vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── src/
│   │   ├── main/                   # Electron main process
│   │   │   ├── index.ts            # 窗口创建、IPC 注册
│   │   │   └── ipc.ts              # preload ↔ main 通信处理
│   │   ├── preload/                # preload bridge
│   │   │   └── index.ts            # contextBridge 暴露安全 API
│   │   └── renderer/               # Vue 3 应用（renderer process）
│   │       ├── index.html
│   │       ├── src/
│   │       │   ├── App.vue
│   │       │   ├── main.ts
│   │       │   ├── components/     # 通用组件
│   │       │   │   ├── LineageTree.vue
│   │       │   │   ├── StorageGauge.vue
│   │       │   │   ├── DiffPanel.vue
│   │       │   │   ├── TerminalPanel.vue
│   │       │   │   └── LifecycleBadge.vue
│   │       │   ├── views/          # 页面级组件
│   │       │   │   ├── DashboardView.vue
│   │       │   │   ├── LineageView.vue
│   │       │   │   ├── BranchView.vue
│   │       │   │   └── RepoSettingsView.vue
│   │       │   ├── composables/    # 组合式函数
│   │       │   │   ├── useArtifactSet.ts
│   │       │   │   ├── useLineage.ts
│   │       │   │   └── useBranch.ts
│   │       │   ├── stores/         # Pinia stores
│   │       │   │   ├── useArtifactStore.ts
│   │       │   │   ├── useLineageStore.ts
│   │       │   │   └── useAppStore.ts
│   │       │   └── types/          # TypeScript 类型定义
│   │       │       ├── artifact.ts
│   │       │       ├── lineage.ts
│   │       │       └── api.ts
│   │       └── env.d.ts
│   └── resources/                  # 应用图标等静态资源
├── tests/                          # 统一测试目录
│   ├── conftest.py                 # 共享 fixtures（tmp_repo, tmp_cas）
│   ├── unit/                       # 单元测试
│   │   ├── test_cas.py
│   │   ├── test_metadata.py
│   │   ├── test_lifecycle.py
│   │   ├── test_lineage.py
│   │   ├── test_workspace.py
│   │   ├── test_permission.py
│   │   └── test_models.py
│   ├── integration/                # 集成测试
│   │   ├── test_commit_flow.py
│   │   ├── test_checkout_flow.py
│   │   ├── test_branch_flow.py
│   │   └── test_cross_branch.py
│   └── e2e/                        # 端到端测试
│       └── test_cli_main.py
├── docs/                           # 项目文档
│   ├── architecture.md             # 架构说明（面向使用者）
│   ├── cli-reference.md            # CLI 命令参考
│   ├── sdk-guide.md                # SDK 使用指南
│   └── migration-guide.md          # 从 pds_xxx 迁移指南
└── scripts/                        # 开发辅助脚本
    ├── setup-dev.sh                # 开发环境初始化
    └── benchmark-cas.py            # CAS 去重基准测试
```

### Architectural Boundaries

| 调用方 | 被调用方 | 通信方式 | 方向约束 |
|--------|---------|---------|---------|
| CLI (`big.cli`) | Core (`big.core`) | 进程内函数调用 | CLI 可调用 Core，Core 不可导入 CLI |
| SDK (`big.sdk`) | Core (`big.core`) | Python import 直接调用 | SDK 可调用 Core，Core 不可导入 SDK |
| API (`big.api`) | Core (`big.core`) | 进程内函数调用 | API 可调用 Core，Core 不可导入 API |
| GUI (`big-gui`) | API (`big.api`) | HTTP 请求（localhost） | GUI 仅通过 API 访问 Core，禁止绕过 |
| Core 内部各模块 | `big.core.metadata` | 通过 metadata 模块操作 SQLite | 禁止 core 外部直接写 SQL |
| Core 内部各模块 | `big.core.cas` | 通过 cas 模块读写 CAS pool | 禁止直接读写 `.big/cas/objects/` |

**核心原则：big.core 是唯一业务逻辑层，CLI/SDK/API 只是 I/O 适配壳。**

### Requirements to Structure Mapping

| FR 类别 | 核心模块 | CLI 命令 | API 端点 | GUI 视图 |
|---------|---------|---------|---------|---------|
| 制品集版本管理 (FR1-7, FR33) | `core/artifact_set.py`, `core/cas.py` | `commit_cmd.py` | `/api/artifacts` | `DashboardView` |
| 分支管理 (FR8-14) | `core/branch.py` | `branch_cmd.py` | `/api/branches` | `BranchView` |
| 血缘追溯 (FR15-17) | `core/lineage.py` | `lineage_cmd.py` | `/api/lineage` | `LineageView` |
| 分层存储 (FR19-23) | `core/lifecycle.py`, `core/storage.py` | `promote_cmd.py` | `/api/artifacts/{id}/lifecycle` | `DashboardView`（状态标签） |
| 仓库管理 (FR24-28) | `core/repo.py`, `core/gc.py` | `repo_cmd.py` | `/api/stats` | `RepoSettingsView` |
| 系统集成 (FR29-32) | `core/pipeline.py` | `pipeline_cmd.py` | — | `TerminalPanel` |
| 跨流程版本管理 (FR34-36) | `core/cross_branch.py` | `branch_cmd.py`(扩展) | `/api/cross-branch` | `LineageView`（跨分支） |
| DSO 存储优化 (FR37-39) | `core/dso.py` | — | `/api/dso` | `DashboardView`（水位） |

### Cross-Cutting Concerns Locations

| 关注点 | 核心位置 | CLI 入口 | API 入口 | GUI 入口 |
|--------|---------|---------|---------|---------|
| CAS 内容寻址 | `core/cas.py` | 所有写命令 | 所有写端点 | 透明（通过 API） |
| 数据完整性审计 | `core/audit.py` | 写操作自动触发 | 写端点自动触发 | 透明 |
| 生命周期状态迁移 | `core/lifecycle.py` | `promote_cmd.py` | `/api/artifacts/{id}/lifecycle` | `LifecycleBadge` |
| 路径不变性保证 | `core/workspace.py` | `checkout_cmd.py` | `/api/checkout` | 透明 |
| 分支级权限控制 | `core/permission.py` | 写操作自动检查 | 中间件拦截 | 登录态隐含 |
| 跨分支依赖追踪 | `core/cross_branch.py` | `branch_cmd.py` | `/api/cross-branch` | `LineageView` |
| 配方哈希与缓存 | `core/artifact_set.py` | `commit_cmd.py` | `/api/artifacts` | `DashboardView` |
| 异步进度反馈 | `core/events.py` | 进度条输出 | SSE 推送 | `Progress` 组件 |

### Integration Points

**内部通信流：**

```
┌──────────────────────────────────────────────────────┐
│ 用户操作                                              │
├──────────┬─────────────────────┬─────────────────────┤
│  CLI     │      SDK            │     GUI              │
│  Click   │   import big        │  Electron            │
│    │     │      │              │     │                │
│    ▼     │      ▼              │     ▼                │
│ big.core ├──────►big.core      │  HTTP ◄────► FastAPI │
│ (函数)   │ (函数)              │ (localhost)          │
│          │                     │      │               │
│          ▼                     ▼      ▼               │
│     ┌─────────────────────────────────┐              │
│     │        big.core                 │              │
│     │  ┌─────┐ ┌──────┐ ┌──────────┐ │              │
│     │  │ CAS │ │SQLite│ │Lifecycle │ │              │
│     │  │pool │ │  DB  │ │ 咨询委员 │ │              │
│     │  └──┬──┘ └──┬───┘ └────┬─────┘ │              │
│     └─────┼───────┼──────────┼───────┘              │
│           │       │          │                       │
│           ▼       ▼          ▼                       │
│     ┌──────────────────────────────┐                │
│     │      NAS 文件系统             │                │
│     │  .big/cas/  |  .big/metadata │                │
│     └──────────────────────────────┘                │
└──────────────────────────────────────────────────────┘
```

**外部集成点：**

| 外部系统 | 集成方式 | BIG 入口 | 方向 | 阶段 |
|---------|---------|---------|------|------|
| EDA 工具（Innovus 等） | 子进程调用 | `big.core.pipeline` | BIG→EDA | Growth |
| pds_xxx 系统 | Python API 调用 BIG SDK | `big.sdk` | pds→BIG | Growth |
| DSO 系统 | 提交结果至 BIG API | `big.api.routes/artifacts` | DSO→BIG | Growth |
| NAS 文件系统 | 直接读写 | `big.core.cas` + `big.core.workspace` | 双向 | MVP |
| Linux 用户/组 | os.getgrouplist() | `big.core.permission` | BIG→OS | MVP |
| 审计/合规 | 日志导出 | `big.core.audit` | BIG→外部 | MVP |

### Data Flow — Commit Scenario

```
用户执行: big commit -m "floorplan v3" --inputs "rtl/*" --params "tcl/*" --outputs "results/*"

1. 参数解析          CLI (commit_cmd.py)
   │  ← Click 装饰器解析选项参数
   ▼
2. 业务逻辑调用      core/artifact_set.py :: commit()
   │
   ├── 3a. 输入文件扫描    core/cas.py :: batch_hash()
   │       └── 流式 SHA-256 计算每个文件
   │       └── 进度事件: cas.hashing.progress
   │
   ├── 3b. 参数文件扫描    core/cas.py :: batch_hash()
   │       └── 统一 CAS 处理（semantic_role='param'）
   │
   ├── 3c. 产出文件扫描    core/cas.py :: batch_hash()
   │       └── 统一 CAS 处理（semantic_role='output'）
   │
   ├── 4. CAS 写入         core/cas.py :: cas_write()
   │       └── 对每个文件: 临时写入 → 回读校验 → 原子 rename
   │       └── 已存在文件跳过（去重）
   │
   ├── 5. 配方哈希计算      core/artifact_set.py :: compute_recipe_hash()
   │       └── SHA-256(sorted((path, cas_hash) for dependencies))
   │
   ├── 6. 元数据写入        core/metadata.py :: create_artifact_set()
   │       └── SQLite 事务: artifact_set + file_ref + dependency/output
   │       └── plink 边写入 + leaf 表更新
   │       └── 审计日志追加
   │
   ├── 7. 生命周期初始化    core/lifecycle.py :: initialize()
   │       └── 默认 Exploring 状态 + 存储策略回调
   │
   └── 8. 结果返回
           └── CLI: ✓ Committed as #42 [Exploring]
               └── GUI: artifact_set.committed 事件推送
```

### File Organization Patterns

| 类别 | 约定 | 示例 |
|------|------|------|
| Python 模块 | 一个领域概念一个文件 | `lifecycle.py`, `lineage.py`, `workspace.py` |
| CLI 命令 | `{command}_cmd.py` | `commit_cmd.py`, `log_cmd.py` |
| API 路由 | 一个资源一个路由文件 | `routes/branches.py`, `routes/artifacts.py` |
| Vue 组件 | PascalCase 单文件组件 | `LineageTree.vue`, `StorageGauge.vue` |
| Vue 组合式 | `use` 前缀 + camelCase | `useArtifactSet.ts`, `useLineage.ts` |
| Pinia Store | `use{Domain}Store` | `useArtifactStore.ts`, `useAppStore.ts` |
| 测试文件 | 与源文件同命名 | `test_cas.py` 对应 `cas.py` |
| 类型定义 | 领域名.ts | `artifact.ts`, `lineage.ts`, `api.ts` |

### Development Workflow Integration

**开发环境启动：**

```bash
# Python 核心 + CLI 开发
make dev                    # pip install -e ".[dev]" + pre-commit install

# GUI 开发
cd big-gui && npm install && npm run dev     # Vite HMR + Electron

# 运行测试
make test                   # pytest tests/ -v
make lint                   # ruff + mypy + eslint + tsc --noEmit
```

**CI 流水线：**

```yaml
# .github/workflows/ci.yml 关键步骤
- ruff check src/big/
- ruff format --check src/big/
- mypy src/big/ --strict
- pytest tests/ -v --cov=big.core --cov-fail-under=80
- cd big-gui && npm ci && npm run lint && npm run typecheck && npm run test
```

**发布流水线：**

```bash
# Python wheel
python -m build             # 生成 dist/big-0.1.0-py3-none-any.whl

# Electron 安装包
cd big-gui && npm run build:linux    # 生成 dist/big-gui-0.1.0.AppImage
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
所有技术选型彼此兼容——Python 作为核心语言统一了 CLI/SDK/API 三层，SQLite 嵌入式嵌入零运维，Click + FastAPI 同为 Python 生态，Electron + Vue 3 独立项目与 Python 端仅通过 HTTP 松耦合。版本间无已知冲突。

**Pattern Consistency:**
命名约定在 DB（snake_case）、API（kebab-case URL / snake_case 参数）、Python（PascalCase 类 / snake_case 函数）、Vue（PascalCase 组件 / useCamelCase 组合式函数）之间各自一致，含义无歧义。事件系统 `domain.action` 点分格式贯穿 CLI/GUI 反馈路径。错误层次结构覆盖所有核心异常场景，每层处理策略明确。

**Structure Alignment:**
项目结构精确支撑架构决策——core/ 是唯一业务逻辑层，CLI/SDK/API 为薄壳适配层，GUI 通过 HTTP API 隔离。核心模块数量与 FR 域映射完整，每一类需求对应的文件路径可从文档直接定位。

### Requirements Coverage Validation

**Functional Requirements Coverage:**

| FR | 简述 | 架构支撑模块 | 状态 |
|----|------|------------|------|
| FR1 | 创建制品集版本 | `core/artifact_set.py`, `core/cas.py`, `core/metadata.py` | ✅ |
| FR2 | commit校验输入完整性 | `core/cas.py` 流式SHA-256+回读校验, `InputIntegrityError` | ✅ |
| FR3 | 查看分支版本历史 | `core/metadata.py`, `core/branch.py`, leaf缓存 | ✅ |
| FR4 | 查看配方详情 | `core/metadata.py` file_ref+dependency关联查询 | ✅ |
| FR5 | 对比两版本配方差异 | `core/artifact_set.py` recipe_hash对比, `DiffPanel` | ✅ |
| FR6 | checkout到指定版本 | `core/workspace.py` 硬链接物化 | ✅ |
| FR7 | 计算配方哈希 | `compute_recipe_hash()`, `idx_recipe` 索引 | ✅ |
| FR8 | 创建命名分支 | `core/branch.py`, branch表 | ✅ |
| FR9 | 分支间切换 | `core/workspace.py` + `core/branch.py` | ✅ |
| FR10 | 独立目录访问分支 | 一分支一目录映射NAS路径 | ✅ |
| FR11 | 切换分支路径不变 | `core/workspace.py` 硬链接原地替换 | ✅ |
| FR12 | 设置分支权限 | `core/permission.py` owner/group/mode | ✅ |
| FR13 | 分支指针回退 | `core/branch.py` head_id移动 | ✅ |
| FR14 | derived_from语义边 | plink表 `is_derived` 列 | ✅ |
| FR33 | 选择性checkout子集 | `core/workspace.py` --subset | ✅ |
| FR15 | 逆向追溯血缘链 | `core/lineage.py` 递归CTE | ✅ |
| FR16 | 血缘链参数变更 | 递归CTE + recipe_hash差异 | ⚠️ 部分覆盖 |
| FR17 | 正向追溯下游影响 | `core/lineage.py` 递归CTE正向 | ✅ |
| FR19 | 生命周期自动分层 | `core/lifecycle.py` 状态机 + 回调 | ✅ |
| FR20 | Exploring只保留配方 | `core/storage.py` 策略回调 | ✅ |
| FR21 | 手动晋升制品集 | `core/lifecycle.py` promote操作 | ✅ |
| FR22 | Golden只读保护 | lifecycle + 二次确认 | ⚠️ 部分覆盖 |
| FR23 | Golden多副本冗余 | config.toml golden_replicas/paths | ⚠️ 部分覆盖 |
| FR24 | 初始化仓库 | `core/repo.py`, .big/目录 | ✅ |
| FR25 | 配置分层存储策略 | `core/config.py` 三级优先级 | ✅ |
| FR26 | 仓库存储统计 | `core/repo.py` stats查询 | ✅ |
| FR27 | GC回收孤立存储 | `core/gc.py` 引用计数+生命周期 | ✅ |
| FR28 | 导出Golden归档 | CLI archive export | ⚠️ 部分覆盖 |
| FR29 | Pipeline调用外部 | `core/pipeline.py` 子进程编排 | ✅ |
| FR30 | Python API | `big.sdk` import big.core | ✅ |
| FR31 | pds_xxx双向交互 | pipeline + SDK | ✅ |
| FR32 | CLI内置帮助 | Click --help 自动生成 | ✅ |
| FR34 | 跨分支链接依赖 | plink跨分支边 | ⚠️ 部分覆盖 |
| FR35 | 声明跨流程依赖 | `core/cross_branch.py` | ✅ (Growth) |
| FR36 | 上游变更预警 | 事件驱动 | ⚠️ 部分覆盖 |
| FR37 | DSO自动创建版本 | SDK批量commit | ⚠️ 部分覆盖 |
| FR38 | PPA排名淘汰 | `core/dso.py` 策略 | ⚠️ 部分覆盖 |
| FR39 | 存储水位线淘汰 | config high_watermark | ⚠️ 部分覆盖 |

**Non-Functional Requirements Coverage:**

| NFR | 指标 | 架构支撑机制 | 状态 |
|-----|------|------------|------|
| NFR1 | 读吞吐≥70% NAS直读 | 文件级CAS直读 1.0x | ✅ |
| NFR2 | 带宽≥1GB/s | CAS直接写NAS路径 | ✅ |
| NFR3 | 血缘<30s | 递归CTE 0.3ms/depth30 | ✅ |
| NFR4 | commit开销<10% | SQLite 1.6ms/事务 | ⚠️ 批量并发待验证 |
| NFR5 | checkout<2x cp | 硬链接物化 | ✅ |
| NFR6 | 10人并发commit | rollback journal排队<10ms | ⚠️ NAS锁延迟待测 |
| NFR7 | 权限100% | permission.py全拦截 | ✅ |
| NFR8 | 审计不可篡改 | append-only audit_log | ⚠️ 触发器可被DBA绕过 |
| NFR9 | 完整性100% | SHA-256写入校验 | ✅ |
| NFR10 | 概念≤5 | owner/group/r/w/owner | ✅ |
| NFR11 | Golden零丢失 | 双写多副本 | ⚠️ 一致性协议未定义 |
| NFR12 | 非Golden<0.01% | CAS去重+定期扫描 | ✅ |
| NFR13 | Golden≥2副本 | golden_replicas配置 | ⚠️ 校验修复未定义 |
| NFR14 | 单chunk不影响其他 | CAS对象独立存储 | ✅ |
| NFR15 | ≥100万文件 | 元数据索引独立存储 | ✅ |
| NFR16 | ≥1PB | CAS直接写NAS | ✅ |
| NFR17 | ≥10万版本 | 递归CTE 100K实测 | ✅ |
| NFR18 | Python API | big.sdk import | ✅ |
| NFR19 | 子进程退出码 | pipeline.py捕获 | ✅ |
| NFR20 | 路径透明性 | 硬链接/symlink+一分支一目录 | ✅ |
| NFR21 | ≥500 DSO cases | dso.py分组聚合 | ⚠️ 分组模型未定义 |

### Implementation Readiness Validation

**Decision Completeness:**
关键决策均有版本号和选型理由。CAS引擎路径清晰（文件级→块级），SQLite表结构完整定义，异常层次覆盖 5 类 10 种。事件系统格式固定。✅

**Structure Completeness:**
项目目录树完整到文件级别，FR类别与模块映射明确，集成点和数据流已文档化。✅

**Pattern Completeness:**
28 个冲突点已逐一给出约定。Good/Anti-Pattern 示例覆盖核心场景。强制准则定义了 ruff/mypy 规则和覆盖率门槛。✅

### Gap Analysis Results

**Critical Gaps（阻断 MVP 或 Growth 关键路径）：**

1. **DSO 数据模型缺失**：artifact_set 表缺少 `group_id`（寻优分组）和 `metadata_json`（PPA 指标等非文件型数据）字段。FR37/FR38/FR39 全部依赖此模型。
   - 建议方案：在 artifact_set 表增加 `group_id TEXT` 和 `metadata_json TEXT` 字段，Growth 阶段实现。

2. **FR34 MVP 实现路径矛盾**：PRD 标记 FR34 为 MVP，但架构模块映射将其归入 Growth 阶段的 `cross_branch.py`。需要明确 MVP 阶段跨分支 plink 边的写入入口。
   - 建议方案：MVP 阶段在 `commit_cmd.py` 增加 `--cross-branch-input` 选项，后端逻辑直接写入 plink 表跨分支边（不依赖 cross_branch.py 模块）。

3. **Golden 只读保护不完整**：二次确认仅防误操作，不防恶意操作。需要三重防护：CAS 层文件权限 0444 + 元数据层 lifecycle 字段拦截写操作 + GC 跳过 Golden 引用的 CAS 对象。
   - 建议方案：在 `core/storage.py` 的 Golden 策略中定义三重防护逻辑，MVP 阶段实现前两层。

**Important Gaps（影响 Growth 阶段质量）：**

4. **Golden 副本一致性保障**：需要定义同步双写/异步复制的语义、定期校验频率、不一致时的修复策略。建议 Growth 阶段实现同步双写 + 每 24 小时校验 + 不一致时从主副本覆盖修复。

5. **NAS 并发写入性能基线**：rollback journal 下 10 人同时 commit 的锁等待时间未在 NAS 环境实测。建议 MVP 完成后立即建立 NAS 并发基准测试，定义 `busy_timeout` 和重试策略。

6. **审计日志防篡改加强**：SQLite 触发器方案无法防 DBA 权限篡改。建议增加日志哈希链（每条记录存前一条 hash），使篡改可检测。

7. **Exploring 节点 checkout 降级策略**：输出文件回收后 checkout 到 Exploring 节点的行为未定义。建议：检测到目标节点 lifecycle=Exploring 且输出 CAS 对象不存在时，仅物化配方依赖文件并输出明确提示。

8. **FR28 归档格式未定义**：需要定义归档清单格式（JSON manifest + SHA-256 校验和）、是否保留 DAG 元数据、是否支持反向导入恢复。

**Nice-to-Have Gaps（提升系统健壮性）：**

9. **FR16 参数变更细粒度提取**：当前仅支持配方级 recipe_hash 差异，无法自动定位哪个参数文件变了什么。Growth 阶段可扩展为对 semantic_role='param' 的文件做文本 diff。

10. **水位检测触发机制**：建议 commit 后轻量检测 + 定时全量扫描（60s 间隔）的混合策略。

11. **FR36 预警持久化**：预警信息需要持久化到 alert 表或 audit_log，避免进程重启后丢失。

12. **SDK 类型导出完整性**：`big.sdk.__init__.py` 的完整导出列表和类型标注需要在实现时明确。

### Conflict Detection

| 冲突点 | 描述 | 建议 |
|--------|------|------|
| FR34 阶段标签 | PRD 标 MVP，架构归 Growth | MVP 在 commit 命令直接支持跨分支边写入 |
| WAL vs NAS | WAL 不支持 NAS，rollback journal 高并发写性能有张力 | NAS 环境实测 + busy_timeout 调优 |
| CAS 幂等 vs Golden 保护 | CAS 写入幂等（已存在跳过），真正威胁是删除和元数据篡改 | 三重防护：文件权限 + lifecycle 拦截 + GC 跳过 |
| Exploring 回收 vs 血缘完整 | 中间节点输出回收后 checkout 物理层断裂 | 定义降级策略：仅物化依赖 + 明确提示 |
| 统一文件模型 vs PPA 指标 | PPA 不是文件，不走 CAS | artifact_set 增加 metadata_json 字段 |

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**

- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**

- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**

- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY WITH MINOR GAPS

3 项 Critical Gap 均有明确修补方案，不影响 MVP 核心功能交付。FR34 阶段标签矛盾可通过 MVP commit 命令直接支持跨分支边来解决。DSO 数据模型缺失属于 Growth 阶段需求（FR37-39 均标记 Growth），不影响 MVP 交付节奏。Golden 只读保护的三重防护方案可在 MVP 实现前两层时同步补齐。

**Confidence Level:** high

**Key Strengths:**
- SQLite DAG 存储方案经 Fossil SCM 验证 + 100K 节点实测，性能超标 10 万倍
- 统一依赖模型优雅解决了"参数即文件"的领域洞察，降低数据模型复杂度
- 三层级通信架构（函数调用/import/HTTP）完美匹配 MVP→Growth 的演进路径
- 28 个冲突点 + Good/Anti-Pattern 示例为 AI Agent 实施一致性提供强保障
- CAS 双层演进路径（文件级→块级）零迁移、零风险

**Areas for Future Enhancement:**
- DSO 场景数据模型（Growth 阶段补齐）
- 审计日志哈希链防篡改（Growth 阶段增强）
- NAS 并发写入性能基线（MVP 后立即建立）
- Golden 副本一致性协议（Growth 阶段深化）
- FastAPI HTTP API 完整 Schema（Growth 阶段与 GUI 并行细化）

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**

```bash
# 1. 初始化 Python 包骨架
mkdir -p src/big/core src/big/cli src/big/sdk src/big/api
touch src/big/__init__.py src/big/core/__init__.py

# 2. 初始化 GUI 项目
npm create @quick-start/electron big-gui -- --template vue-ts

# 3. 核心模块开发顺序
#    models.py → cas.py → metadata.py → lifecycle.py → workspace.py → branch.py
#    → artifact_set.py → lineage.py → permission.py → audit.py → errors.py
```
