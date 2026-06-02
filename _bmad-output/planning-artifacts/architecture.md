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
revisedAt: '2026-06-02'
revisionReason: 'EDA process isolation + metadata + GUI review: stable branch dirs, explicit restore, repository port, Candidate outbox delivery, public API clients'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Architecture Revision Baseline (2026-06-02)

本节覆盖文档中与其冲突的早期结论，是进入 Epic/Story 拆分前的权威实现基线。

### Corrected MVP Boundaries

| Area | Corrected decision | MVP invariant |
|------|--------------------|---------------|
| CAS | NAS 上的 SHA-256 文件级 CAS 只读且不可变 | 禁止把可写 hardlink/symlink 暴露给 EDA 工作区；对象发布后 chmod 0444，并在读取、scrub、复用时校验摘要 |
| Private branch workdir | 用户私有根目录 + 每分支稳定目录 | 用户在 `/data/<project>/user/<username>/<branch>/` 下工作；一个物理目录在可能仍有 EDA 进程使用时不得改绑到另一分支。内部登记 branch、version、generation 和目录状态 |
| Branch checkout | 切换目录，不重写源目录 | `big checkout <branch>` 解析或物化目标分支的稳定目录，再通过 shell 集成进入目标目录；旧目录保持不动，旧 EDA 进程继续读写旧分支 |
| Version restore | 原地恢复是显式受控操作 | 历史版本默认物化为新的兄弟分支目录；仅显式 `big restore --in-place <version>` 才允许在静默目录中执行 copy-only 增量替换、journal 恢复与 lease 校验 |
| Commit snapshot | commit 必须发布一致快照 | 先将输入、参数、输出复制到 staging 并流式计算摘要；复制前后校验 inode/size/mtime，发生变化则重试或失败；全部对象发布成功后才提交 manifest |
| Metadata | NAS 只承载对象，不承载多客户端直接写入的 SQLite 文件 | MVP 增加单机 `bigd` 元数据服务；SQLite 数据库保存在 `bigd` 本地磁盘并使用 WAL。元数据仓储通过 port 抽象，后续可换 PostgreSQL。CLI/SDK 通过公共 API 写入 |
| Delivery | Candidate 触发受控交付，不复制活跃工作目录 | Candidate 状态迁移与 outbox 事件同事务提交；流水线只从不可变 manifest/CAS 物化到发布 staging，校验后发布版本化交付目录 |
| GUI | GUI 是可替换客户端，不是核心组件 | 官方 GUI 仅作为可选参考客户端；CLI、SDK、官方 GUI 和外部定制 GUI 共用版本化公共 API、OpenAPI schema 与事件契约 |
| Lineage | 版本祖先关系与数据血缘关系分离 | `version_parent` 表达 commit/derived-from；`provenance_edge` 表达 consumes/produces/depends-on，不再用一个布尔值混合两类图 |
| Lifecycle | 评审状态与物理驻留状态分离 | `review_state=Exploring/Candidate/Pinned/Golden`；`retention_state=resident/recipe_only/archived/missing` |
| Recipe cache | recipe hash 是可追溯摘要，不默认等于可复用 cache key | Growth 阶段的 `action_hash` 必须包含命令、依赖摘要、参数、工具/PDK/库版本、选定环境变量、平台和 schema 版本 |
| Golden | “零丢失”改为可验证的运维目标 | 定义故障域隔离、RPO/RTO、不可变副本、每日 scrub、修复流程和恢复演练；未完成前不得宣称零丢失 |

### Explicit Non-Goals for MVP

- 不在多台客户端之间直接共享写入 NAS 上的 SQLite 数据库。
- 不在仍可能被 EDA 进程使用的目录中原地切换分支。
- 不使用可变 `current` symlink 作为分支隔离或正确性边界。
- 不承诺运行中的 EDA 工具在显式原地 restore 后自动读取到新版本。
- 不依赖 reflink/COW；目标 NAS 版本不支持这些能力。
- 不使用 writable hardlink 或 symlink 将 CAS 对象直接暴露给 EDA 工具。
- 不将 FastCDC、Pack、GUI、自动 recipe cache 复用提前到 MVP。

## Project Context Analysis

### Requirements Overview

**Functional Requirements (45 FR, 9 domains):**

| Domain | FR Range | MVP | Growth | Architecture Focus |
|--------|----------|-----|--------|--------------------|
| 制品集版本管理 | FR1-7, FR33 | 8 | 0 | 数据模型核心、配方哈希、输入校验 |
| 分支管理 | FR8-14 | 7 | 0 | 用户私有分支目录、分支指针移动、derived_from 语义边 |
| 血缘追溯 | FR15-17 | 1 | 2 | DAG 查询引擎、跨分支链接 |
| 分层存储 | FR19-23 | 3 | 2 | 生命周期状态机、存储策略迁移、Golden 冗余 |
| 仓库管理 | FR24-28 | 2 | 3 | GC 回收、统计监控、归档导出 |
| 系统集成 | FR29-32, FR45-46 | 1 | 5 | 子进程编排器、公共API、Candidate交付、可替换GUI |
| 跨流程版本管理 | FR34-36 | 1 | 2 | 跨分支依赖声明、变更预警 |
| DSO 存储优化 | FR37-39 | 0 | 3 | PPA 排名淘汰策略、存储水位管理、寻优分组 |
| 基础正确性 | FR40-44 | 4 | 1 | 不可变CAS、一致快照、bigd单写服务、workdir恢复日志、完整action hash |

MVP 共 27 个 FR，Growth 共 18 个 FR。架构必须为 Growth 阶段的 FastCDC、流水线引擎、可替换GUI、Candidate交付、DSO 集成和完整 action hash 预留扩展点。

**Non-Functional Requirements (22 NFR, 5 dimensions):**

| Dimension | Key NFRs | Architecture Driver |
|-----------|----------|---------------------|
| 性能 | NFR1 读吞吐≥70% NAS直读; NFR2 带宽≥1GB/s; NFR4 commit额外开销<10%; NFR5 checkout<2x cp | NAS 文件级 CAS、staging 流式写入、copy-only增量物化 |
| 安全 | NFR7 权限检查100%; NFR8 审计不可篡改; NFR9 数据完整性100% | 分支级 ACL、append-only 审计日志、SHA-256 校验 |
| 可靠性 | NFR11 Golden 可验证耐久性; NFR12 非Golden <0.01%; NFR13 Golden ≥2故障域副本 | 不可变副本、CAS 引用追踪、每日 scrub、恢复演练 |
| 可扩展性 | NFR15 ≥100万文件; NFR16 ≥1PB; NFR17 ≥10万版本历史; NFR21 ≥500 DSO cases | 元数据索引独立于存储池、分布式元数据就绪、分组聚合查询 |
| 集成 | NFR18 Python API; NFR19 子进程退出码捕获; NFR20 路径隔离; NFR22 公共API可替换性 | 公共API客户端、子进程管理器、稳定分支目录、OpenAPI与事件契约 |

### Scale & Complexity

- Primary domain: **系统级开发者工具** — CLI 核心 + CAS 存储引擎 + Electron GUI 可视化 + Python API 集成
- Complexity level: **高** — 领域模型非标准（制品集双中心）、I/O 性能硬约束、TB/PB 级数据规模、环形版本图语义修正为 DAG+语义边
- Estimated architectural components: **6 个核心子系统** — CLI 命令层、核心业务逻辑层、CAS 存储引擎、元数据管理、GUI 前端（Electron+Vue3）、Python API 层

### Technical Constraints & Dependencies

| Constraint | Source | Architecture Impact |
|------------|--------|---------------------|
| CentOS 生产环境 | PRD 开发者工具需求 | 不依赖新版内核特性；编译安装流程 |
| NAS 基础设施 | PRD 核心约束 | NAS 承载不可变 CAS 和工作区文件；不用 FUSE；元数据数据库不允许被多客户端直接写入 |
| 低版本 NAS | 用户确认的生产环境约束 | 不依赖 reflink/COW；新分支目录和显式原地restore使用普通copy物化；restore使用同目录临时文件 + 逐文件原子替换 |
| Python 主要语言 (MVP) | PRD 语言策略 | 核心逻辑用 Python；I/O 热路径（FastCDC/CAS 拼接）预留 C/Rust 扩展点 |
| 无容器部署 | PRD 安装策略 | 编译安装包；不依赖 Docker/K8s |
| EDA 工具路径隔离 | PRD 领域约束 | 分支目录使用稳定且不同的真实路径；分支checkout不改写源目录。显式原地restore默认要求目录静默，已有文件句柄需要工具重新打开 |
| SSH 远程 CLI | UX 平台策略 | CLI 无 X11 依赖；纯文本输出适配终端宽度 |
| 现有 pds_xxx 系统双向集成 | PRD 集成架构 | 子进程编排模型；Python API 供 pds_xxx 调用 |
| 无 Git 依赖 | PRD 反模式 | BIG 自管理元数据和存储，不依赖外部 VCS |
| 数据模型不阻碍分布式 | PRD 跨站点约束 | 元数据和存储层分离；预留 Commit-Edge 扩展点 |

### Cross-Cutting Concerns Identified

| Concern | Impact Scope | Architecture Strategy |
|---------|-------------|----------------------|
| CAS 内容寻址存储 | 所有文件 I/O、commit、checkout、GC | 独立存储引擎层，文件级 CAS (MVP) → FastCDC 块级 (Growth) |
| 数据完整性与审计 | commit、promote、权限变更、Golden 操作 | SHA-256 写校验 + append-only 审计日志 + 定期全仓扫描 |
| 生命周期状态迁移 | commit、promote、GC、DSO 淘汰 | 评审状态与驻留状态双状态机 + 存储策略回调 + 阶段跃迁事件 |
| 分支进程隔离 | branch checkout、历史版本restore | 分支checkout进入另一个稳定目录且不改写源目录；历史版本默认创建兄弟目录。仅显式原地restore检查dirty state与受管lease，并按journal恢复 |
| 分支级访问控制 | 所有写操作、分支创建 | ACL 结合 Linux group 体系，分支为权限边界 |
| 跨分支依赖追踪 | lineage 查询、变更预警 | 版本祖先图 + provenance 数据血缘图 + 依赖声明注册 + 事件驱动预警 |
| 配方哈希与缓存 | pipeline 执行、commit 去重 | MVP 保存 recipe hash 用于追溯；Growth 使用完整 action hash 作为缓存 Key |
| Candidate交付 | promote、统一发布目录、外部流水线 | 状态迁移、审计和outbox同事务提交；幂等消费不可变manifest；staging校验后发布版本化目录 |
| 异步进度反馈 | commit（哈希计算）、目录物化、流水线交付 | 事件总线 + 进度条（CLI ANSI / GUI Progress 组件） |

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

关键点：输入文件和参数文件（TCL/YAML）统一走 CAS，区别仅在 `semantic_role` 标签。`recipe_hash` 基于所有依赖文件的 `(path, cas_hash)` 对，可用于配方追溯和差异检测。它不是完整缓存 Key；安全复用输出还需 Growth 阶段的 `action_hash`，纳入命令、工具链、PDK、库版本、选定环境变量、平台和 schema 版本。

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
| NAS 直读 | FileCAS 可实现直读；工作目录使用普通copy增量物化 |
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
热路径: 文件级 CAS cache → copy-only增量物化到用户私有分支目录
冷路径: fastcdc 块级 Pack → 物化时先还原为只读完整文件 cache，再普通copy
```

| 维度 | 评价 |
|------|------|
| NAS 直读 | 冷数据读放大需真实基准验证；首次还原后可使用只读完整文件 cache |
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

核心优势：**MVP 低复杂度起步 → Growth 可按基准数据叠加 → 参数文件增量去重自然承接**

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

MVP 使用单机 `bigd` 元数据服务托管 SQLite。SQLite 数据库保存在 `bigd` 主机的本地磁盘并使用 WAL；CLI/SDK 通过公共 API 发起写入。NAS 仅承载不可变 CAS 对象、staging 文件和用户私有分支目录。百万文件+十万版本规模下，通过索引优化满足 NFR17 查询性能。

SQLite 适合单写服务内部使用，但不允许多台客户端直接打开 NAS 上的同一个数据库文件。应用层只依赖 `MetadataRepository` port，不直接依赖 SQLite；MVP 适配器为 `SqliteMetadataRepository`。若 `bigd` 单机吞吐、HA、多实例或多站点要求成为瓶颈，切换为 `PostgresMetadataRepository`。

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

**领域层 + 应用层 + adapters：**

- 自定义 Python 包；领域模型和服务端用例位于`big.domain`与`big.application`
- CLI、SDK、官方GUI和外部GUI通过`bigd /api/v1`共享服务端业务规则；CLI另有本地workdir adapter处理shell和NAS目录
- 基础设施位于`big.adapters`：NAS文件系统CAS、`bigd`本地SQLite元数据库、后续PostgreSQL和流水线runner

**注意：** MVP 首个实现 Story 应优先建立`bigd /api/v1`、不可变CAS、稳定分支目录checkout和显式restore边界。GUI属于Growth阶段的可选参考客户端。

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- 元数据存储架构（MetadataRepository port + SQLite MVP adapter + DAG 存储模式）
- 统一依赖数据模型（输入+参数文件统一 CAS）
- `bigd /api/v1`、CLI本地workdir adapter、SDK、官方GUI与外部GUI的通信边界

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

#### SQLite 作为 `bigd` 本地元数据存储的深度论证

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

**Python 集成：服务端零门槛**

`sqlite3` 是 Python 标准库模块，零安装、零配置、零依赖：

```python
import sqlite3

conn = sqlite3.connect('/var/lib/bigd/metadata.db')
conn.execute('WITH RECURSIVE lineage(...) SELECT ...')
```

无需额外 Python 依赖。数据库由单机 `bigd` 托管，不随仓库目录放到 NAS 上共享打开。

**SQLite 并发与 NAS 部署**

| 场景 | SQLite 表现 | BIG 匹配度 |
|------|-----------|-----------|
| `bigd` 单写者 + API 多客户端 | WAL 模式，事务串行化 | MVP 推荐模式 |
| 10 人同分支 commit | 由 `bigd` 排队并执行乐观并发检查 | 必须在真实 NAS 环境压测 |
| NAS 文件系统 | 不在 NAS 上直接共享 SQLite 文件 | 明确禁止 |
| HA / 多站点 | SQLite 单机不足 | 迁移 PostgreSQL |

**图数据库 vs SQLite 的临界点分析**

学术研究（Vicknair 2010, Barros 2015, Jouili 2013）共识：

| 遍历深度 | 关系数据库（有索引） | 图数据库 |
|---------|-------------------|---------|
| 1-2 跳 | 等效或更快 | 持平 |
| 3-5 跳 | 可竞争 | 开始领先 |
| 6+ 跳 | 显著落后 | 10-100x 更快 |

BIG 的查询模式以**深度优先线性链**为主（沿 derived_from 回溯），分支因子极低，不是社交网络式的广度多跳遍历。这正是 SQLite 递归 CTE 最高效的场景，图数据库的优势无法体现。

**结论：`bigd` 本地 SQLite 存储图元数据，采用邻接表 + 递归 CTE，借鉴 Fossil 的整数外键、双向索引和元数据可重建设计。SQLite 是单写服务内部实现细节，不是 NAS 共享数据库。**

#### 核心表结构设计

借鉴 Fossil 的 Schema1/Schema2 分层思想，BIG 的 SQLite 表分为两层：

**Schema1 — append-only权威记录（manifest发布后不可原地修改）：**

```sql
-- 制品集版本：DAG 节点
CREATE TABLE artifact_set(
    id INTEGER PRIMARY KEY,           -- 整数 RID，图边引用此列
    branch_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    recipe_hash TEXT NOT NULL,         -- 依赖与参数摘要，用于追溯，不默认等同于缓存 Key
    action_hash TEXT,                  -- Growth: 命令、依赖、工具链和平台的完整缓存 Key
    created_at REAL NOT NULL,
    author TEXT NOT NULL
);
CREATE INDEX idx_recipe ON artifact_set(recipe_hash);

-- 版本祖先图：commit 继承或从历史版本重新出发
CREATE TABLE version_parent(
    pid INTEGER NOT NULL REFERENCES artifact_set(id),
    cid INTEGER NOT NULL REFERENCES artifact_set(id),
    relation TEXT NOT NULL DEFAULT 'parent', -- parent | derived_from
    PRIMARY KEY(pid, cid, relation)
);
CREATE INDEX version_parent_rev ON version_parent(cid, pid);
CREATE INDEX version_parent_fwd ON version_parent(pid, cid);

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

-- 数据血缘图：跨流程输入输出关系，独立于版本祖先图
CREATE TABLE provenance_edge(
    id INTEGER PRIMARY KEY,
    upstream_artifact_set_id INTEGER NOT NULL REFERENCES artifact_set(id),
    downstream_artifact_set_id INTEGER NOT NULL REFERENCES artifact_set(id),
    relation TEXT NOT NULL,           -- consumes | depends_on | produces | supersedes
    file_ref_id INTEGER REFERENCES file_ref(id)
);
CREATE UNIQUE INDEX provenance_edge_unique ON provenance_edge(
    upstream_artifact_set_id, downstream_artifact_set_id, relation, COALESCE(file_ref_id, 0)
);
CREATE INDEX provenance_edge_rev ON provenance_edge(downstream_artifact_set_id, upstream_artifact_set_id);
CREATE INDEX provenance_edge_fwd ON provenance_edge(upstream_artifact_set_id, downstream_artifact_set_id);

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

**Schema2 — 服务端控制与派生元数据：**

该层包含可变控制状态和可重建索引。`leaf` 等派生索引可从 Schema1 重建；`artifact_state`、`branch`、`workdir`、`audit_log`、`outbox_event` 和 `delivery` 是服务端权威控制记录，必须纳入备份与恢复。`workdir` 是内部登记项，对用户不增加新的命令或心智模型；每行对应一个用户私有的稳定分支工作目录。

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

-- 评审状态与物理驻留状态分离；manifest本身保持append-only
CREATE TABLE artifact_state(
    artifact_set_id INTEGER PRIMARY KEY REFERENCES artifact_set(id),
    review_state TEXT NOT NULL DEFAULT 'Exploring',
    retention_state TEXT NOT NULL DEFAULT 'resident',
    updated_at REAL NOT NULL
);
CREATE INDEX idx_artifact_state_review ON artifact_state(review_state);
CREATE INDEX idx_artifact_state_retention ON artifact_state(retention_state);

-- 内部工作目录登记：用户看到的是自己的具体分支目录，不需要理解workdir概念
CREATE TABLE workdir(
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    host TEXT NOT NULL,
    root_path TEXT UNIQUE NOT NULL,
    branch_id INTEGER REFERENCES branch(id),
    checked_out_artifact_set_id INTEGER REFERENCES artifact_set(id),
    generation INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_expires_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 审计日志：服务端 append-only + 哈希链；定期导出到独立不可变介质
CREATE TABLE audit_log(
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    detail TEXT,
    timestamp REAL NOT NULL,
    prev_hash TEXT,
    entry_hash TEXT NOT NULL
);

-- 事务outbox：状态迁移、审计和待投递事件在同一个bigd事务中提交
CREATE TABLE outbox_event(
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    published_at REAL
);
CREATE INDEX idx_outbox_event_unpublished ON outbox_event(published_at, created_at);

-- Candidate交付记录：流水线幂等消费事件，只从不可变manifest/CAS发布版本化目录
CREATE TABLE delivery(
    id TEXT PRIMARY KEY,
    artifact_set_id INTEGER NOT NULL REFERENCES artifact_set(id),
    event_id TEXT UNIQUE NOT NULL REFERENCES outbox_event(id),
    target TEXT NOT NULL,
    status TEXT NOT NULL,             -- queued | running | published | failed
    release_path TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 叶子节点缓存（借鉴 Fossil leaf 表，加速分支顶端查询）
CREATE TABLE leaf(
    artifact_set_id INTEGER PRIMARY KEY REFERENCES artifact_set(id)
);
```

**关键设计决策：**

| 决策 | 选择 | 理由 |
|------|------|------|
| 图存储模式 | 两套邻接表 + 递归 CTE | `version_parent` 管祖先关系，`provenance_edge` 管数据依赖；避免把回退语义与跨流程依赖混为一谈 |
| 外键类型 | 整数 RID | 整数比较比 SHA 字符串快 5-10x（Fossil 实践） |
| 边类型区分 | 关系字段 + 独立图 | `parent/derived_from` 与 `consumes/depends_on/produces/supersedes` 分开遍历 |
| 分支目录状态 | 内部 `workdir` 表 | 用户只看到私有分支目录；内部记录 root、owner、host、当前branch/version、generation和受管lease，用于恢复与并发检查 |
| 元数据后端 | `MetadataRepository` port + SQLite/PostgreSQL adapter | SQLite 是 MVP 单机 `bigd` 的内部实现，不泄漏到应用层；需要 HA、多实例或多站点时可替换 |
| Candidate交付 | 事务outbox + 幂等delivery记录 | 状态迁移、审计和事件不丢失；流水线只消费不可变manifest，不从活跃工作目录复制 |
| 审计日志 | 服务端 append-only + 哈希链 | 检测篡改，并定期导出到独立不可变介质 |
| 输入/参数统一 | file_ref 字典表 + semantic_role 标签 | 输入文件和参数文件（TCL/YAML）结构完全相同，区别仅 UX 展示 |
| 配方与缓存哈希 | `recipe_hash` + `action_hash` | recipe hash 用于追溯；Growth 的 action hash 才可用于安全复用输出 |
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
import grp, os, pwd, stat

def check_write_permission(branch, username):
    """仅在 bigd 服务端执行的类 Linux 文件权限检查。"""
    if username == branch.owner:
        return bool(branch.mode & stat.S_IWUSR)
    primary_gid = pwd.getpwnam(username).pw_gid
    group_ids = os.getgrouplist(username, primary_gid)
    group_names = {grp.getgrgid(gid).gr_name for gid in group_ids}
    if branch.group_name in group_names:
        return bool(branch.mode & stat.S_IWGRP)
    return bool(branch.mode & stat.S_IWOTH)
```

权限判断只允许由可信 `bigd` 服务端执行，客户端不得提交可伪造的用户名作为授权依据。5 个核心概念：**用户（user）、组（group）、读（r）、写（w）、所有者（owner）**——对齐 Linux 心智模型。

#### CAS 写入完整性保证

```python
import hashlib, os, tempfile

def stage_and_publish(source_path, cas_root, expected_stat):
    """复制到 staging 并流式哈希；校验源文件稳定后发布只读 CAS 对象。"""
    sha = hashlib.sha256()
    objects_dir = os.path.join(cas_root, 'objects')
    staging_dir = os.path.join(cas_root, 'staging')
    os.makedirs(staging_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix='cas-', dir=staging_dir)
    with open(source_path, 'rb') as src, os.fdopen(fd, 'wb') as dst:
        while chunk := src.read(1 << 20):
            sha.update(chunk)
            dst.write(chunk)
        dst.flush()
        os.fsync(dst.fileno())

    # 源文件若在复制期间变化，拒绝发布混合快照。
    if stable_stat(source_path) != expected_stat:
        os.unlink(tmp_path)
        raise WorkdirChangedError(source_path)

    cas_hash = sha.hexdigest()
    cas_path = os.path.join(objects_dir, cas_hash[:2], cas_hash)
    os.makedirs(os.path.dirname(cas_path), exist_ok=True)

    # 已存在对象也必须按摘要验证，不能盲目信任共享存储。
    if os.path.exists(cas_path):
        verify_digest(cas_path, cas_hash)
        os.unlink(tmp_path)
        return cas_hash

    verify_digest(tmp_path, cas_hash)
    publish_no_replace(tmp_path, cas_path)  # 同一文件系统内原子发布；并发命中时校验既有对象
    os.chmod(cas_path, 0o444)
    fsync_parent(cas_path)
    return cas_hash
```

`publish_no_replace()` 必须使用 UUID 临时名和 create-if-absent 语义。manifest 与元数据提交是最后一步：只有全部 CAS 对象成功发布后，`bigd` 才能在单个事务中创建可见制品集。分支目录物化只允许使用普通copy，禁止 writable hardlink/symlink 指向 CAS。

#### Stable branch checkout：进入另一个目录，不改写源目录

生产 NAS 不支持 reflink/COW，因此 BIG 使用普通copy物化文件。但 branch checkout 的安全边界不是“原地替换得足够快”，而是“不要改写仍可能被 EDA 进程使用的目录”。

`big checkout <branch>` 的行为：

1. 解析 `/data/<project>/user/<username>/<branch>/` 下目标分支的稳定真实目录。禁止使用可变 `current` symlink 作为隔离边界。
2. 若目标目录尚不存在，则从目标 manifest 使用普通copy物化兄弟目录；若已经存在，则直接复用该目录。源分支目录始终保持不动。
3. 输出目标路径，并由一次性安装的 shell 集成进入该目录，例如 `eval "$(big shell-init bash)"` 后执行 `big checkout feature/fp-exploration`。未安装 shell 集成时，CLI 输出可直接执行的 `cd -- <target-path>`。
4. 原目录中的 EDA 进程保持原 cwd、已打开文件描述符和绝对路径，因此继续读写原分支；新 shell 在目标目录中启动的新进程只看到目标分支。

CLI 子进程无法修改父 shell 的 cwd，因此 shell wrapper 是一条 `big checkout` 体验成立的必要实现细节。它不引入新的日常命令，也不改变底层安全模型。

#### Explicit in-place restore：静默目录中的受控恢复

历史版本回退默认创建新的兄弟分支目录，例如 `big checkout <version> --new-branch fp-from-v2`。仅在用户明确要求 `big restore --in-place <version>` 时，BIG 才在当前目录执行copy-only增量替换：

1. 校验当前目录为已登记私有分支目录，并检查未提交修改与 BIG 管理的活动lease。
2. 明确提示手工启动的 EDA 写入进程无法可靠自动发现；严格受控流程应使用 `big run -- <eda-command>` 获取lease。原地restore要求目录静默。
3. 对比当前manifest与目标manifest，仅处理摘要变化、新增或删除路径。
4. 将目标CAS对象普通复制到同目录UUID临时文件，回读校验摘要后chmod为工作区可写权限，再逐文件`os.replace()`。
5. 在`.big/restore-journal.json`记录目标和逐文件进度。全部完成后更新`.big/HEAD`、服务端`checked_out_artifact_set_id`和`generation`。
6. 中断后支持继续执行或按manifest重新物化；不宣称多文件目录替换存在单一原子点。

`lease`、`generation`和journal用于显式restore、commit快照和受管工具执行，不用于制造“可以安全改写活跃目录”的错觉。

#### Candidate-driven delivery：从不可变制品发布

统一交付目录不从用户活跃工作目录复制。`big promote <artifact> --to Candidate` 在一个`bigd`事务中更新`artifact_state`、追加审计并写入`outbox_event`。流水线幂等消费`artifact.candidate_marked`事件，仅从不可变manifest/CAS物化到`/release/.staging/<delivery-id>/`，验证完成后发布不可变版本目录`/release/<release-id>/`并记录`delivery`状态。若需要稳定入口，只更新受控别名供新消费者使用，不原地修改已经发布的内容。

### API & Communication Patterns

#### Headless application boundary

```
┌─────────────────────────────────────────────────────────┐
│ CLI + local workdir client │ Python SDK │ custom GUI    │
│ official big-gui reference client     │ external system │
└───────────────────────────┬─────────────────────────────┘
                            │ public HTTP API / events
┌───────────────────────────▼─────────────────────────────┐
│                         bigd                            │
│ FastAPI /api/v1 + OpenAPI │ outbox worker │ auth/audit  │
├─────────────────────────────────────────────────────────┤
│ application use cases + ports                           │
│ MetadataRepository │ CASRepository │ DeliveryPublisher  │
├─────────────────────────────────────────────────────────┤
│ adapters                                                 │
│ SQLite/PostgreSQL │ NAS CAS │ pipeline runner            │
└─────────────────────────────────────────────────────────┘
```

**决策理由：**

| 通信方式 | 适用场景 | 选择 |
|---------|---------|------|
| CLI ↔ `bigd` | 日常操作、shell集成、目录物化 | **公共API + 本地workdir adapter** — 服务端保存权威元数据，CLI负责当前主机上的目录进入与文件物化 |
| SDK ↔ `bigd` | 自动化系统、流水线和DSO集成 | **公共API client** — SDK不直接导入数据库或服务端业务实现 |
| 官方GUI / 定制GUI ↔ `bigd` | 浏览、评审、晋升、监控 | **同一公共API + 事件流** — 不存在GUI专用端点，不允许直连数据库或导入`big.core` |
| `bigd` ↔ adapters | 元数据、CAS、交付流水线 | **application ports** — SQLite只是MVP adapter，后续可换PostgreSQL |

**公共API设计原则：**

- API 从MVP开始存在，版本前缀为`/api/v1`。监听地址、TLS和认证由部署配置决定，不把`localhost`写死为产品边界。
- FastAPI生成OpenAPI schema；CLI、Python SDK、官方GUI和外部定制GUI共享资源模型并可生成类型安全客户端。
- 禁止GUI专用业务端点。资源端点至少包括`/api/v1/branches`、`/api/v1/artifact-sets`、`/api/v1/lineage`、`/api/v1/review-transitions`、`/api/v1/deliveries`、`/api/v1/operations`、`/api/v1/capabilities`。
- 写请求支持`Idempotency-Key`，资源更新使用generation或ETag进行乐观并发检查。大规模commit、目录物化和交付返回异步operation资源。
- 对外事件采用CloudEvents兼容信封；MVP由SQLite outbox worker投递，后续可接消息系统。事件是集成契约，不绑定具体broker。

### Frontend Architecture

官方`big-gui`是独立、可选的参考客户端，不是BIG核心部署的必选组件。其他系统可以基于同一OpenAPI和事件契约提供自己的GUI；官方GUI不得直接操作NAS、SQLite或服务端Python模块。checkout涉及当前shell和本机目录，因此GUI只发起计划或展示等价CLI命令，本地CLI完成最终目录切换。

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
review_state = "Exploring"
```

优先级：仓库 `.big/config.toml` > 全局 `~/.bigconfig.toml` > 内置默认值。

**日志：**

- Python `logging` 模块，结构化输出
- 文件日志：`~/.big/logs/big-YYYYMMDD.log`（自动轮转，保留 30 天）
- CLI stderr：简洁人类可读格式
- `--verbose` / `--debug` 控制输出详细程度

### Decision Impact Analysis

**实施顺序：**

1. `big.domain` + `big.application` 骨架（数据模型、用例、ports）
2. `bigd` 服务端（FastAPI `/api/v1`、SQLite adapter、NAS CAS adapter、outbox worker）
3. CLI + 本地workdir adapter（init / commit / checkout / restore / log / branch / shell-init）
4. Python SDK（公共API client）
5. Candidate交付流水线adapter（不可变manifest → staging → 版本化发布目录）
6. 可选官方GUI初始化（electron-vite参考客户端）
7. 官方GUI核心视图（版本树 + 配方详情）

**跨组件依赖关系：**

```
CLI + local workdir adapter ──┐
Python SDK API client ────────┼──► bigd /api/v1 ──► application ports ──► adapters
official big-gui ─────────────┤
external custom GUI/system ──┘
```

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 28 areas where AI agents could make different choices

### Naming Patterns

**Database Naming Conventions:**

| 规则 | 约定 | 示例 |
|------|------|------|
| 表名 | snake_case，复数概念用单数（实体名） | `artifact_set`, `version_parent`, `provenance_edge`, `file_ref` |
| 列名 | snake_case | `cas_hash`, `recipe_hash`, `review_state` |
| 主键 | `id`（单列）或 `表名_id`（外键引用时） | `id`, `branch_id`, `artifact_set_id` |
| 外键 | `引用表单数_id` | `branch_id`, `file_ref_id` |
| 布尔列 | `is_` / `has_` 前缀 | `is_prim` |
| 时间列 | `_at` 后缀，REAL 类型（Julian day 或 Unix epoch） | `created_at`, `timestamp` |
| 索引 | `idx_表名_列名` | `idx_artifact_set_recipe_hash` |
| 唯一约束 | 内联 `UNIQUE` 而非命名约束 | `UNIQUE(pid, cid)` |

**API Naming Conventions:**

| 规则 | 约定 | 示例 |
|------|------|------|
| URL 路径 | 版本前缀 + kebab-case复数名词 | `/api/v1/artifact-sets`, `/api/v1/branches` |
| URL 路径参数 | kebab-case | `/api/v1/artifact-sets/{id}` |
| 查询参数 | snake_case | `?branch_id=1&lifecycle=candidate` |
| HTTP 动词 | 标准 REST 语义 | GET 查询, POST 创建, PATCH 部分更新 |
| HTTP 状态码 | 精确使用 | 200 成功, 201 创建, 404 不存在, 409 冲突, 422 校验失败 |

**Code Naming Conventions:**

| 层 | 约定 | 示例 |
|---|------|------|
| Python 包/模块 | snake_case | `big/adapters/nas_cas.py` |
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
├── src/big/                   # Python包（src layout）
│   ├── domain/                # 纯领域模型与策略
│   ├── application/           # 服务端用例与ports
│   ├── adapters/              # SQLite/PostgreSQL、NAS CAS、pipeline runner
│   ├── client/                # 公共API client + 本地workdir/shell集成
│   ├── cli/                   # CLI命令入口
│   │   ├── main.py            # Click group 入口
│   │   ├── commit.py
│   │   ├── checkout.py
│   │   ├── restore.py
│   │   ├── log_cmd.py         # 避免 log.py 与 stdlib 冲突
│   │   └── branch_cmd.py
│   ├── sdk/                   # 公共API客户端封装
│   └── bigd/                  # MVP权威HTTP API服务
│       └── server.py
├── big-gui/                   # 可选Electron + Vue 3参考客户端
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
| domain/application 是服务端真相源 | CLI/SDK/GUI不能复制服务端业务逻辑；routes只做协议适配，客户端统一调用公共API |
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
| 事件信封 | CloudEvents兼容：`specversion`, `id`, `source`, `type`, `time`, `data` | 见下方 |
| 事件版本 | `type` 后缀或data内嵌schema版本 | `"schema_version": 1` |
| 进度事件 | `domain.action.progress` 子类型 | `cas.hashing.progress` |

```python
# 标准事件载荷结构
{
    "specversion": "1.0",
    "id": "evt-018f...",
    "source": "/bigd/projects/proj_A",
    "type": "artifact_set.committed",
    "time": "2026-05-30T14:30:00Z",
    "data": {
        "schema_version": 1,
        "id": 42,
        "branch": "fp-exploration",
        "recipe_hash": "a1b2c3d4...",
        "review_state": "Exploring",
        "retention_state": "resident"
    }
}

# 进度事件载荷
{
    "specversion": "1.0",
    "id": "evt-0190...",
    "source": "/bigd/projects/proj_A",
    "type": "cas.hashing.progress",
    "time": "2026-05-30T14:30:01Z",
    "data": {
        "schema_version": 1,
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
| domain/application | 抛出自定义异常类（`big.domain.errors.CommitValidationError` 等），包含 `message` + `suggestion` + `detail` |
| CLI | 捕获异常 → 格式化输出（✗ 红色 + 原因 + 建议操作），退出码 1 |
| HTTP API | 捕获异常 → 映射为标准错误响应格式 + 适当 HTTP 状态码 |
| SDK | 将公共API错误映射为稳定SDK异常，由调用方决定处理策略 |
| GUI | HTTP API 返回的错误 → Alert 内联展示 + 操作按钮 |

**自定义异常层次：**

```
BigError
├── ValidationError          # 422: 输入校验失败
│   ├── InputIntegrityError  # commit 时输入文件缺失/损坏
│   └── RecipeConflictError  # 配方哈希冲突
├── StateError               # 409: 状态不允许操作
│   ├── LifecycleError       # 生命周期跃迁违规
│   └── WorkdirDirtyError    # 显式restore或commit快照时未提交变更
├── PermissionError          # 403: 权限不足
├── NotFoundError            # 404: 实体不存在
└── StorageError             # 500: CAS/元数据写入失败
    ├── IntegrityError       # CAS 写入校验失败
    └── ConcurrencyError     # bigd 发布冲突或 workdir generation 变化
```

**Loading State Patterns:**

| 场景 | CLI | GUI |
|------|-----|-----|
| commit 哈希计算 | 进度条 `████░░░░ 60%` | Progress 组件（环形/条形） |
| 新目录物化 / 显式restore | 进度条 + 文件计数 | Progress + 文件列表实时更新 |
| API 数据加载 | — | Spin + 骨架屏（匹配实际布局） |
| 长时间运算（>5s） | 定期输出状态更新 | 预估剩余时间（可选） |
| 慢操作（≤1s） | 无进度指示 | 无进度指示 |

### Enforcement Guidelines

**All AI Agents MUST:**

- 所有数据库操作仅允许在 `bigd` 服务端通过 `MetadataRepository` port 执行；CLI/SDK/GUI 通过公共 API 访问
- 所有 CAS 操作通过 `CASRepository` port 与NAS adapter执行，禁止客户端或GUI直接读写`.big/cas/objects/`
- 所有 CAS 对象发布后必须只读；分支目录仅允许普通copy物化，禁止使用 reflink/COW 假设和 writable hardlink/symlink
- commit 必须先完成 staging 快照并验证文件稳定性，再发布 manifest
- branch checkout 必须进入另一个稳定真实目录且不得改写源目录；显式原地restore才检查dirty state与受管lease并使用恢复journal。无法可靠发现手工启动的EDA进程
- CLI 命令只做参数解析、公共API调用、本地workdir操作与格式化输出，不包含服务端业务逻辑
- 新增数据库表必须明确属于 append-only权威记录、服务端控制记录或可重建派生索引，并在 `tests/` 中添加恢复或rebuild验证测试
- API 端点必须在 `bigd.api` 中注册版本化路由，保持一致的响应格式、幂等键和乐观并发规则
- GUI不得直接操作NAS、SQLite或导入服务端模块；官方GUI与外部定制GUI使用相同OpenAPI和事件契约
- GUI 组件中不允许直接 `fetch`，必须通过 TanStack Query 的 `useQuery` / `useMutation`
- 所有错误消息必须包含"做了什么"（message）+"为什么"（detail）+"接下来怎么办"（suggestion）

**Pattern Enforcement:**

- Python: ruff 格式化 + mypy 类型检查 + 自定义ruff规则禁止除SQLite adapter之外的模块直接`import sqlite3`
- TypeScript: ESLint + Prettier + 严格 tsconfig
- 测试覆盖：`domain/`与`application/`≥ 90%，CLI/API ≥ 70%
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
        click.echo(f"✓ Committed as {result.id} [{result.review_state}/{result.retention_state}]")
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
│   └── big/                        # Python 包（src layout）
│       ├── __init__.py             # 版本号
│       ├── domain/                 # 纯领域模型与策略，不依赖HTTP/SQLite/NAS
│       │   ├── models.py           # ArtifactSet, FileRef, Branch, Delivery
│       │   ├── lifecycle.py        # 评审与驻留状态机
│       │   ├── lineage.py          # 血缘图语义
│       │   └── errors.py           # 领域异常
│       ├── application/            # 服务端用例与ports
│       │   ├── ports.py            # MetadataRepository, CASRepository, DeliveryPublisher
│       │   ├── commit.py           # 一致快照发布用例
│       │   ├── checkout.py         # 分支目录解析与物化计划
│       │   ├── promote.py          # 状态迁移 + audit + outbox
│       │   └── delivery.py         # Candidate交付编排
│       ├── adapters/               # 可替换基础设施实现
│       │   ├── sqlite_metadata.py  # MVP: bigd本地SQLite WAL
│       │   ├── postgres_metadata.py# Growth: HA/多实例
│       │   ├── nas_cas.py          # NAS文件级CAS + FastCDC扩展点
│       │   └── pipeline_runner.py  # Growth: 外部命令与交付流水线
│       ├── client/                 # 公共API客户端 + 本地workdir能力
│       │   ├── api.py              # /api/v1 client
│       │   ├── workdir.py          # 稳定分支目录物化、显式restore journal
│       │   └── shell.py            # shell-init与checkout目录切换
│       ├── cli/                    # CLI 命令入口（薄壳层）
│       │   ├── __init__.py
│       │   ├── main.py             # Click group 入口（big --help）
│       │   ├── init_cmd.py
│       │   ├── commit_cmd.py
│       │   ├── checkout_cmd.py
│       │   ├── restore_cmd.py
│       │   ├── shell_cmd.py
│       │   ├── log_cmd.py          # 避免 log.py 与 stdlib 冲突
│       │   ├── branch_cmd.py
│       │   ├── promote_cmd.py
│       │   ├── lineage_cmd.py
│       │   ├── repo_cmd.py
│       │   └── pipeline_cmd.py
│       ├── sdk/                    # Python SDK：公共API客户端封装
│       │   └── __init__.py
│       └── bigd/                   # 权威服务端（MVP）
│           ├── __init__.py
│           ├── server.py           # FastAPI /api/v1 + OpenAPI
│           ├── outbox_worker.py    # 可靠事件投递
│           ├── routes/
│           │   ├── branches.py
│           │   ├── artifacts.py
│           │   ├── lineage.py
│           │   ├── deliveries.py
│           │   └── stats.py
│           └── deps.py             # 依赖注入（ports → adapters）
├── big-gui/                        # 可选Electron + Vue 3参考客户端
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
│   │   ├── test_workdir.py
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
| CLI (`big.cli`) | `big.client` + `bigd /api/v1` | 本地调用 + HTTP | CLI仅负责shell/workdir本地动作与API调用 |
| SDK (`big.sdk`) | `bigd /api/v1` | HTTP API client | SDK不可直接导入服务端application或adapter |
| 官方GUI / 外部GUI | `bigd /api/v1` | HTTP + 事件流 | 所有GUI共用公共契约，禁止绕过 |
| `bigd` routes | `big.application` | 进程内函数调用 | routes只做协议适配，业务规则在application/domain |
| `big.application` | ports | Python protocol/interface | 用例不可直接依赖SQLite、NAS或具体流水线 |
| adapters | 外部资源 | SQLite/PostgreSQL、NAS、子进程 | adapter实现port；不得反向导入UI或CLI |

**核心原则：`big.domain`和`big.application`是服务端业务真相源；CLI、SDK、官方GUI和外部GUI都是可替换客户端。SQLite、PostgreSQL、NAS和流水线runner都是adapter。**

### Requirements to Structure Mapping

| FR 类别 | 核心模块 | CLI 命令 | API 端点 | GUI 视图 |
|---------|---------|---------|---------|---------|
| 制品集版本管理 (FR1-7, FR33) | `application/commit.py`, `client/workdir.py` | `commit_cmd.py`, `checkout_cmd.py`, `restore_cmd.py` | `/api/v1/artifact-sets`, `/api/v1/operations` | `DashboardView` |
| 分支管理 (FR8-14) | `domain/models.py`, `application/checkout.py`, `client/workdir.py` | `branch_cmd.py`, `checkout_cmd.py` | `/api/v1/branches` | `BranchView` |
| 血缘追溯 (FR15-17) | `domain/lineage.py` | `lineage_cmd.py` | `/api/v1/lineage` | `LineageView` |
| 分层存储 (FR19-23) | `domain/lifecycle.py`, `application/promote.py` | `promote_cmd.py` | `/api/v1/review-transitions` | `DashboardView`（状态标签） |
| 仓库管理 (FR24-28) | application用例 + adapters | `repo_cmd.py` | `/api/v1/stats` | `RepoSettingsView` |
| 系统集成 (FR29-32, FR45-46) | `application/delivery.py`, `adapters/pipeline_runner.py` | `pipeline_cmd.py` | `/api/v1/deliveries`, `/api/v1/capabilities` | `TerminalPanel` |
| 跨流程版本管理 (FR34-36) | application用例 + provenance port | `branch_cmd.py`(扩展) | `/api/v1/cross-branch` | `LineageView`（跨分支） |
| DSO 存储优化 (FR37-39) | application用例 + storage adapter | — | `/api/v1/dso` | `DashboardView`（水位） |
| 基础正确性 (FR40-44) | `application/commit.py`, `client/workdir.py`, `bigd`, adapters | `commit_cmd.py`, `checkout_cmd.py`, `restore_cmd.py` | `/api/v1/artifact-sets`, `/api/v1/workdirs` | — |

### Cross-Cutting Concerns Locations

| 关注点 | 核心位置 | CLI 入口 | API 入口 | GUI 入口 |
|--------|---------|---------|---------|---------|
| CAS 内容寻址 | `CASRepository` port + `adapters/nas_cas.py` | 所有写命令 | 所有写端点 | 透明（通过API） |
| 数据完整性审计 | application用例 + MetadataRepository | 写操作自动触发 | 写端点自动触发 | 透明 |
| 生命周期状态迁移 | `domain/lifecycle.py`, `application/promote.py` | `promote_cmd.py` | `/api/v1/review-transitions` | `LifecycleBadge` |
| 分支进程隔离 | `client/workdir.py`, `client/shell.py` | `checkout_cmd.py`, `restore_cmd.py` | `/api/v1/workdirs` | 展示等价CLI命令 |
| 分支级权限控制 | application用例 | 写操作自动检查 | 中间件 + 用例拦截 | 登录态隐含 |
| 跨分支依赖追踪 | provenance port | `branch_cmd.py` | `/api/v1/cross-branch` | `LineageView` |
| Candidate交付 | `application/promote.py`, `application/delivery.py` | `promote_cmd.py` | `/api/v1/review-transitions`, `/api/v1/deliveries` | `LifecycleBadge` |
| 配方哈希与缓存 | `application/commit.py` | `commit_cmd.py` | `/api/v1/artifact-sets` | `DashboardView` |
| 异步进度反馈 | outbox + events | 进度条输出 | SSE/webhook | `Progress` 组件 |

### Integration Points

**内部通信流：**

```
┌──────────────────────────────────────────────────────┐
│ 用户操作                                              │
├──────────┬─────────────────────┬─────────────────────┤
│  CLI     │      SDK            │ official/custom GUI  │
│  Click   │  API client         │  Electron / Web      │
│    │     │      │              │     │                │
│    ▼     │      ▼              │     ▼                │
│ big.cli  ├──────► bigd API ◄───┼──── HTTP ───► FastAPI │
│         HTTP                    │              (bigd)   │
│          │                     │      │               │
│          ▼                     ▼      ▼               │
│     ┌─────────────────────────────────┐              │
│     │   bigd + application ports      │              │
│     │  ┌─────┐ ┌──────┐ ┌──────────┐ │              │
│     │  │ CAS │ │Meta  │ │Delivery  │ │              │
│     │  │port │ │port  │ │outbox    │ │              │
│     │  └──┬──┘ └──┬───┘ └────┬─────┘ │              │
│     └─────┼───────┼──────────┼───────┘              │
│           │       │                                  │
│           ▼       ▼                                  │
│     ┌───────────────┐    ┌──────────────────────┐    │
│     │ NAS 文件系统   │    │ bigd 本地磁盘        │    │
│     │ CAS/user dirs │    │ SQLite WAL metadata │    │
│     └───────────────┘    └──────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

**外部集成点：**

| 外部系统 | 集成方式 | BIG 入口 | 方向 | 阶段 |
|---------|---------|---------|------|------|
| EDA 工具（Innovus 等） | 子进程调用 | `adapters.pipeline_runner` / `big run` | BIG→EDA | Growth |
| pds_xxx 系统 | Python SDK调用公共API | `big.sdk` | pds→BIG | Growth |
| DSO 系统 | 提交结果至公共API | `/api/v1/artifact-sets` | DSO→BIG | Growth |
| 定制GUI | OpenAPI client + 事件订阅 | `/api/v1`, SSE/webhook | 双向 | Growth |
| 交付系统 | Candidate事件 + delivery状态 | outbox / `/api/v1/deliveries` | 双向 | Growth |
| NAS 文件系统 | 对象与分支目录文件读写 | `adapters.nas_cas` + `client.workdir` | 双向 | MVP |
| Linux 用户/组 | 服务端 NSS 查询 | permission adapter | bigd→OS | MVP |
| 审计/合规 | 日志导出 | MetadataRepository | BIG→外部 | MVP |

### Data Flow — Commit Scenario

```
用户执行: big commit -m "floorplan v3" --inputs "rtl/*" --params "tcl/*" --outputs "results/*"

1. 参数解析          CLI (commit_cmd.py)
   │  ← Click 装饰器解析选项参数
   ▼
2. 公共API调用        big.client.api → bigd /api/v1/artifact-sets
    │
    ├── 3a. 获取分支目录 lease 与快照边界    client/workdir.py
    │       └── 记录 workdir generation；检查dirty state、受管lease与文件稳定性
    │
    ├── 3b. 输入文件 staging    adapters/nas_cas.py :: stage_batch()
    │       └── 复制到 staging 时流式计算 SHA-256
    │       └── 进度事件: cas.hashing.progress
    │
    ├── 3c. 参数文件 staging    adapters/nas_cas.py :: stage_batch()
    │       └── 统一 CAS 处理（semantic_role='param'）
    │
    ├── 3d. 产出文件 staging    adapters/nas_cas.py :: stage_batch()
    │       └── 统一 CAS 处理（semantic_role='output'）
    │
    ├── 4. CAS 写入         adapters/nas_cas.py :: cas_write()
    │       └── 对每个文件: staging → 回读校验 → create-if-absent 原子发布 → chmod 0444
    │       └── 已存在对象仍需摘要校验
    │
    ├── 5. 配方哈希计算      application/commit.py :: compute_recipe_hash()
    │       └── SHA-256(sorted((path, cas_hash) for dependencies))
    │
    ├── 6. 元数据发布        bigd :: create_artifact_set()
    │       └── bigd 本地 SQLite 事务: artifact_set + file_ref + dependency/output
    │       └── version_parent / provenance_edge 写入 + leaf 表更新
    │       └── 哈希链审计日志追加
    │
    ├── 7. 生命周期初始化    domain/lifecycle.py :: initialize()
    │       └── review_state=Exploring + retention_state=resident
   │
   └── 8. 结果返回
           └── CLI: ✓ Committed as #42 [Exploring]
               └── GUI: artifact_set.committed 事件推送
```

### File Organization Patterns

| 类别 | 约定 | 示例 |
|------|------|------|
| Python 模块 | 一个领域概念一个文件 | `lifecycle.py`, `lineage.py`, `workdir.py` |
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
- pytest tests/ -v --cov=big --cov-fail-under=80
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
主要技术选型彼此兼容——Python统一CLI/SDK API client与`bigd`服务端，SQLite作为`MetadataRepository`的MVP本地adapter，NAS作为对象数据平面。Click + FastAPI同为Python生态，Electron + Vue 3官方GUI及外部定制GUI与服务端仅通过公共HTTP API和事件契约松耦合。不得把SQLite数据库放到NAS供多客户端直接写入。

**Pattern Consistency:**
命名约定在 DB（snake_case）、API（kebab-case URL / snake_case 参数）、Python（PascalCase 类 / snake_case 函数）、Vue（PascalCase 组件 / useCamelCase 组合式函数）之间各自一致，含义无歧义。事件系统 `domain.action` 点分格式贯穿 CLI/GUI 反馈路径。错误层次结构覆盖所有核心异常场景，每层处理策略明确。

**Structure Alignment:**
项目结构精确支撑架构决策——`domain/`和`application/`是服务端业务真相源，`bigd` routes、CLI、SDK和GUI为协议或客户端适配层，基础设施位于`adapters/`。核心模块数量与FR域映射完整，每一类需求对应的文件路径可从文档直接定位。

### Requirements Coverage Validation

**Functional Requirements Coverage:**

| FR | 简述 | 架构支撑模块 | 状态 |
|----|------|------------|------|
| FR1 | 创建制品集版本 | `application/commit.py`, `adapters/nas_cas.py`, MetadataRepository | ✅ |
| FR2 | commit校验输入完整性 | NAS CAS adapter流式SHA-256+回读校验, `InputIntegrityError` | ✅ |
| FR3 | 查看分支版本历史 | MetadataRepository, leaf缓存 | ✅ |
| FR4 | 查看配方详情 | MetadataRepository file_ref+dependency关联查询 | ✅ |
| FR5 | 对比两版本配方差异 | application用例recipe_hash对比, `DiffPanel` | ✅ |
| FR6 | checkout分支或从历史版本新建分支 | `client/workdir.py`稳定兄弟目录物化 + `client/shell.py` | ✅ |
| FR7 | 计算配方哈希 | `compute_recipe_hash()`, `idx_recipe` 索引 | ✅ |
| FR8 | 创建命名分支 | application用例, branch表 | ✅ |
| FR9 | 分支间切换 | `client/workdir.py`, `client/shell.py` | ✅ |
| FR10 | 私有稳定分支目录 | 用户私有root下的每分支真实目录；内部workdir登记 | ✅ |
| FR11 | 运行中进程隔离 | branch checkout不改写源目录；旧进程保留原cwd和fd | ✅ |
| FR12 | 设置分支权限 | permission policy owner/group/mode | ✅ |
| FR13 | 分支指针回退 | branch head_id移动 | ✅ |
| FR14 | derived_from语义边 | `version_parent.relation='derived_from'` | ✅ |
| FR33 | 选择性checkout子集 | `client/workdir.py` --subset | ✅ |
| FR15 | 逆向追溯血缘链 | lineage query用例 + MetadataRepository递归CTE | ✅ |
| FR16 | 血缘链参数变更 | 递归CTE + recipe_hash差异 | ⚠️ 部分覆盖 |
| FR17 | 正向追溯下游影响 | lineage query用例 + MetadataRepository递归CTE正向 | ✅ |
| FR19 | 生命周期自动分层 | `review_state` + `retention_state` 双状态机 + 回调 | ✅ |
| FR20 | Exploring可降级只保留配方 | `retention_state='recipe_only'`；默认保留grace period | ✅ |
| FR21 | 手动晋升制品集 | `application/promote.py` + domain lifecycle | ✅ |
| FR22 | Golden只读保护 | lifecycle + 二次确认 | ⚠️ 部分覆盖 |
| FR23 | Golden多副本冗余 | config.toml golden_replicas/paths | ⚠️ 部分覆盖 |
| FR24 | 初始化仓库 | repo用例 + `.big/`目录 | ✅ |
| FR25 | 配置分层存储策略 | config adapter三级优先级 | ✅ |
| FR26 | 仓库存储统计 | stats用例 | ✅ |
| FR27 | GC回收孤立存储 | storage adapter引用计数+生命周期 | ✅ |
| FR28 | 导出Golden归档 | CLI archive export | ⚠️ 部分覆盖 |
| FR29 | Pipeline调用外部 | pipeline runner adapter子进程编排 | ✅ |
| FR30 | Python SDK | `big.sdk`公共API client | ✅ |
| FR31 | pds_xxx双向交互 | pipeline + SDK | ✅ |
| FR32 | CLI内置帮助 | Click --help 自动生成 | ✅ |
| FR45 | Candidate可靠交付 | `application/promote.py`事务outbox + `application/delivery.py`幂等发布 | ✅ (Growth) |
| FR46 | 可替换GUI公共契约 | `/api/v1` + OpenAPI + CloudEvents兼容事件 | ✅ (Growth) |
| FR34 | 跨分支链接依赖 | `provenance_edge` 跨分支边 | ⚠️ 部分覆盖 |
| FR35 | 声明跨流程依赖 | provenance用例 | ✅ (Growth) |
| FR36 | 上游变更预警 | 事件驱动 | ⚠️ 部分覆盖 |
| FR37 | DSO自动创建版本 | SDK批量commit | ⚠️ 部分覆盖 |
| FR38 | PPA排名淘汰 | DSO策略用例 | ⚠️ 部分覆盖 |
| FR39 | 存储水位线淘汰 | config high_watermark | ⚠️ 部分覆盖 |
| FR40 | CAS只读不可变 | NAS CAS adapter只读发布 + 摘要校验 | ✅ |
| FR41 | commit一致快照 | staging复制 + stat稳定性校验 + manifest最后发布 | ✅ |
| FR42 | bigd单写元数据服务 | MetadataRepository port + 本地SQLite WAL adapter + API写入 | ✅ |
| FR43 | 稳定目录、显式restore journal与lease | `client/workdir.py`, `big run` | ✅ |
| FR44 | 完整action hash缓存Key | application commit用例Growth扩展 | ⚠️ Growth待细化 |

**Non-Functional Requirements Coverage:**

| NFR | 指标 | 架构支撑机制 | 状态 |
|-----|------|------------|------|
| NFR1 | 读吞吐≥70% NAS直读 | 文件级CAS直读 1.0x | ✅ |
| NFR2 | 带宽≥1GB/s | CAS直接写NAS路径 | ✅ |
| NFR3 | 血缘<30s | 递归CTE 0.3ms/depth30 | ✅ |
| NFR4 | commit开销<10% | staging流式写入 + bigd事务 | ⚠️ 真实NAS批量并发待验证 |
| NFR5 | checkout<2x cp | 新目录普通copy物化；显式restore使用增量copy + 同目录临时文件替换 | ⚠️ 按真实NAS压测 |
| NFR6 | 10人并发commit | bigd串行发布 + 乐观并发检查 | ⚠️ 真实NAS与bigd压测 |
| NFR7 | 权限100% | permission.py全拦截 | ✅ |
| NFR8 | 审计篡改可检测 | append-only audit_log哈希链 + 外部导出 | ⚠️ 外部不可变介质待接入 |
| NFR9 | 完整性100% | SHA-256写入校验 | ✅ |
| NFR10 | 概念≤5 | owner/group/r/w/owner | ✅ |
| NFR11 | Golden可验证耐久性 | 故障域隔离副本 + scrub + 恢复演练 | ⚠️ RPO/RTO与一致性协议待定义 |
| NFR12 | 非Golden<0.01% | CAS去重+定期扫描 | ✅ |
| NFR13 | Golden≥2副本 | golden_replicas配置 | ⚠️ 校验修复未定义 |
| NFR14 | 单chunk不影响其他 | CAS对象独立存储 | ✅ |
| NFR15 | ≥100万文件 | 元数据索引独立存储 | ✅ |
| NFR16 | ≥1PB | CAS直接写NAS | ✅ |
| NFR17 | ≥10万版本 | 递归CTE 100K实测 | ✅ |
| NFR18 | Python API | `big.sdk`公共API client | ✅ |
| NFR19 | 子进程退出码 | pipeline.py捕获 | ✅ |
| NFR20 | 路径隔离与透明性 | 稳定分支真实目录；branch checkout不改写源目录；显式restore单独受控 | ✅ |
| NFR21 | ≥500 DSO cases | dso.py分组聚合 | ⚠️ 分组模型未定义 |
| NFR22 | 公共API可替换性 | `/api/v1` + OpenAPI + 事件契约；官方GUI无专用端点 | ✅ |

### Implementation Readiness Validation

**Decision Completeness:**
关键正确性边界已明确：不可变CAS、staging快照、单写`bigd`、每分支稳定目录、显式原地restore、事务outbox交付、双图血缘、双状态生命周期和公共API边界。API schema细节仍需在Epic拆分前补齐。⚠️

**Structure Completeness:**
项目目录树完整到文件级别，FR类别与模块映射明确，集成点和数据流已文档化。✅

**Pattern Completeness:**
28 个冲突点已逐一给出约定。Good/Anti-Pattern 示例覆盖核心场景。强制准则定义了 ruff/mypy 规则和覆盖率门槛。✅

### Gap Analysis Results

**Critical Gaps（阻断 MVP 或 Growth 关键路径）：**

1. **DSO 数据模型缺失**：artifact_set 表缺少 `group_id`（寻优分组）和 `metadata_json`（PPA 指标等非文件型数据）字段。FR37/FR38/FR39 全部依赖此模型。
   - 建议方案：在 artifact_set 表增加 `group_id TEXT` 和 `metadata_json TEXT` 字段，Growth 阶段实现。

2. **FR34 MVP 实现路径矛盾**：PRD 标记 FR34 为 MVP，但架构模块映射将其归入 Growth 阶段的 `cross_branch.py`。需要明确 MVP 阶段跨分支血缘边的写入入口。
   - 建议方案：MVP 阶段在 `commit_cmd.py` 增加 `--cross-branch-input` 选项，后端逻辑直接写入 `provenance_edge`（不依赖 cross_branch.py 模块）。

3. **Golden 只读保护不完整**：二次确认仅防误操作，不防恶意操作。需要三重防护：CAS 层文件权限 0444 + 元数据层 `review_state` 拦截写操作 + GC 跳过 Golden 引用的 CAS 对象。
   - 建议方案：在storage policy adapter的Golden策略中定义三重防护逻辑，MVP阶段实现前两层。

**Important Gaps（影响 Growth 阶段质量）：**

4. **Golden 副本一致性保障**：需要定义同步双写/异步复制的语义、定期校验频率、不一致时的修复策略。建议 Growth 阶段实现同步双写 + 每 24 小时校验 + 不一致时从主副本覆盖修复。

5. **`bigd` 并发写入性能基线**：10 人同时 commit 的 API 排队、staging I/O 与乐观并发冲突率尚未在 NAS 环境实测。建议进入功能实现前建立基准测试，定义超时和重试策略。

6. **审计日志外部锚定**：服务端哈希链已纳入基线，但仍需定期导出到独立不可变介质，避免 DBA 同时改写日志和哈希链。

7. **Exploring 节点 checkout 降级策略**：输出文件回收后从Exploring节点创建兄弟分支目录的行为未定义。建议：检测到目标节点`retention_state=recipe_only`且输出CAS对象不存在时，仅物化配方依赖文件并输出明确提示。

8. **FR28 归档格式未定义**：需要定义归档清单格式（JSON manifest + SHA-256 校验和）、是否保留 DAG 元数据、是否支持反向导入恢复。

**Nice-to-Have Gaps（提升系统健壮性）：**

9. **FR16 参数变更细粒度提取**：当前仅支持配方级 recipe_hash 差异，无法自动定位哪个参数文件变了什么。Growth 阶段可扩展为对 semantic_role='param' 的文件做文本 diff。

10. **水位检测触发机制**：建议 commit 后轻量检测 + 定时全量扫描（60s 间隔）的混合策略。

11. **FR36 预警持久化**：预警信息需要持久化到 alert 表或 audit_log，避免进程重启后丢失。

12. **SDK 类型导出完整性**：`big.sdk.__init__.py` 的完整导出列表和类型标注需要在实现时明确。

13. **Shell集成兼容矩阵**：`big checkout`单命令体验依赖shell wrapper。EDA环境常见bash、csh/tcsh等不同shell；试点前需要盘点生产默认shell，并为所有纳入试点的shell提供wrapper。`big checkout --print-path`是通用底座，也是非交互流水线规范。

14. **统一交付目录命名与保留策略**：版本化`/release/<release-id>/`已确定，但稳定别名命名、同目标串行化规则、失败staging清理周期和发布目录保留策略仍需在Growth Story中定义。

### Conflict Detection

| 冲突点 | 描述 | 建议 |
|--------|------|------|
| FR34 阶段标签 | PRD 标 MVP，架构归 Growth | MVP 在 commit 命令直接支持跨分支边写入 |
| SQLite vs NAS | SQLite不由客户端在NAS上共享打开，也不成为应用层硬依赖 | `bigd`本地WAL adapter；application只依赖MetadataRepository port |
| branch checkout vs 活跃EDA进程 | 原地重写目录会让运行中进程观察到混合版本 | 每分支稳定真实目录；checkout只进入目标目录，原地覆盖单独使用显式restore |
| GUI vs 产品边界 | GUI直连core或使用专用端点会阻碍外部系统定制 | `/api/v1` + OpenAPI + 事件契约；官方GUI只是可选参考客户端 |
| Candidate vs 统一交付目录 | 从用户工作目录直接复制会受活跃进程写入影响 | 事务outbox触发流水线，只从不可变manifest/CAS发布版本化目录 |
| CAS 幂等 vs Golden 保护 | 既有 CAS 对象也必须校验；真正威胁是污染、删除和元数据篡改 | 只读对象 + 摘要校验 + review_state 拦截 + GC 跳过 |
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

**Overall Status:** REVISION REQUIRED BEFORE IMPLEMENTATION

外部校验发现原方案存在会破坏数据正确性的假设：writable hardlink/symlink会污染CAS，多客户端直接访问NAS SQLite风险不可接受，原地checkout会让运行中EDA进程在同一目录内观察到混合版本，后台commit若无staging快照会记录混合时点数据。上述约束已修正为不可变CAS、`bigd`单写服务、稳定分支目录、显式原地restore和一致快照；在补齐Epic、Story和验收测试前，不进入功能实现。

**Confidence Level:** medium

**Key Strengths:**
- `bigd`本地SQLite DAG存储可复用Fossil风格索引，并通过MetadataRepository port保留向PostgreSQL迁移路径
- 统一依赖模型优雅解决了"参数即文件"的领域洞察，降低数据模型复杂度
- CLI、SDK、官方GUI和外部定制GUI通过公共API与`bigd`解耦，NAS与元数据服务职责分离
- Candidate状态迁移通过事务outbox触发幂等交付，统一发布目录不依赖活跃工作区
- 28 个冲突点 + Good/Anti-Pattern 示例为 AI Agent 实施一致性提供强保障
- CAS 双层演进路径仍可保留，但 FastCDC 参数和 Pack 复杂度必须由真实 EDA 基准驱动

**Areas for Future Enhancement:**
- DSO 场景数据模型（Growth 阶段补齐）
- 审计日志外部不可变介质导出
- `bigd`并发写入、普通copy目录物化、显式restore和NAS吞吐基线（实现前建立）
- Golden RPO/RTO、副本一致性和恢复演练协议
- FastAPI `/api/v1`完整Schema、OpenAPI生成客户端和事件契约细化

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented
- Use implementation patterns consistently across all components
- Respect project structure and boundaries
- Refer to this document for all architectural questions

**First Implementation Priority:**

```bash
# 1. 初始化 Python 包骨架
mkdir -p src/big/domain src/big/application src/big/adapters src/big/client src/big/cli src/big/sdk src/big/bigd
touch src/big/__init__.py src/big/domain/__init__.py src/big/application/__init__.py

# 2. 核心模块开发顺序
#    domain/models.py → application/ports.py → adapters/sqlite_metadata.py
#    → adapters/nas_cas.py → bigd/server.py → client/workdir.py → client/shell.py
#    → application/commit.py → application/checkout.py → domain/lifecycle.py

# 3. Growth阶段再初始化GUI项目
# npm create @quick-start/electron big-gui -- --template vue-ts
```
