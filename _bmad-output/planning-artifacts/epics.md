---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/research-technical-architecture.md
  - _bmad-output/planning-artifacts/research/technical-compressed-file-storage-research-2026-06-03.md
  - chat/260517.md
  - chat/260519.md
  - chat/260520.md
  - chat/260521.md
  - chat/260522.md
  - chat/260525.md
  - chat/260526.md
  - chat/260528.md
  - chat/260529.md
  - chat/260530.md
  - chat/260601.md
notes:
  - chat 目录文档作为参考语境使用，不作为一等正式需求源。
  - 当前 PRD 验证报告已被 2026-06-02 的 PRD、架构、元数据、进程隔离与 API 边界修订覆盖。
  - Epic/Story 拆分完成后，需要重新回审 PRD、UX 与 Architecture 的一致性，再进入 implementation readiness validation。
  - 3DIC 当前物理工作目录是四个并行 root：<ProjectName>_3D、<ProjectName>_Top、<ProjectName>_Bottom、<ProjectName>_MIX；BIG 应建模为一个逻辑设计仓库挂接多个 work root，而不是把四个目录简单视为四个互不相关仓库。
---

# big - Epic 拆分

## 概览

本文档用于把 big 的 PRD、UX 设计规格与架构要求拆解为可实施的 Epic 与 Story。当前 Step 1 只保存需求库存；FR 覆盖映射和 Epic/Story 清单会在后续步骤补全。

## 需求库存

### 功能需求

FR1: [MVP] 工程师可以创建制品集版本，并指定输入文件、工具参数文件和输出文件。

FR2: [MVP] 工程师可以在 commit 时自动校验输入文件完整性，包括遗漏输入和错误输入检测。

FR3: [MVP] 工程师可以查看某个分支上的制品集版本历史。

FR4: [MVP] 工程师可以查看任意制品集版本的配方详情，包括输入文件哈希、工具参数和输出文件哈希。

FR5: [MVP] 工程师可以对比两个制品集版本的配方差异。

FR6: [MVP] 工程师可以执行 `big checkout <branch>` 进入目标分支的稳定真实目录，也可以执行 `big checkout <version> --new-branch <name>` 从历史版本物化新的兄弟分支目录；两类操作都不得改写源分支目录。

FR7: [MVP] 系统可以为每个制品集版本计算并记录用于追溯的 recipe hash，基于输入与参数身份；该 recipe hash 不默认等同于可复用输出的缓存 Key。

FR8: [MVP] PD Lead 可以在项目中创建命名分支。

FR9: [MVP] 工程师可以通过一条 `big checkout <branch>` 命令解析或物化目标分支目录，并通过 shell 集成进入该目录；未安装 shell 集成时，CLI 输出可执行的 `cd -- <target-path>` 命令。

FR10: [MVP] 工程师或自动化任务可以在管理员登记的 NAS work root 下维护稳定真实工作目录。普通项目可使用单一 root；3DIC 项目可登记 `/data/<ProjectName>_3D`、`/data/<ProjectName>_Top`、`/data/<ProjectName>_Bottom`、`/data/<ProjectName>_MIX` 四个并行 root，并在各 root 下沿用 `/user/<Username>/{APR,SYN,PV,STA,PI,...}` 工作习惯。逻辑 branch/version 由 BIG 元数据记录，物理 flow 目录不默认等同于 branch；禁止使用可变 `current` symlink 作为隔离边界。

FR11: [MVP] 工程师切换分支后，原目录中的 EDA 进程继续保持原 cwd、已打开文件描述符和绝对路径，新目录中新启动的进程使用目标分支。

FR12: [MVP] PD Lead 可以设置分支访问权限，包括用户、组、读权限和写权限。

FR13: [MVP] 系统可以通过移动分支指针到历史节点来表达回退操作，而不是创建逆向 commit。

FR14: [MVP] 系统可以记录制品集之间的 `derived_from` 语义关系，例如某版本从早期版本回退后重新生成。

FR15: [MVP] 工程师可以从任意制品集逆向追溯完整上游血缘链。

FR16: [Growth] 工程师可以查看血缘链上每个节点引入的参数变更。

FR17: [Growth] 工程师可以从任意制品集正向追溯下游影响范围，查看哪些制品集依赖它。

FR19: [MVP] 系统可以分别管理制品集评审状态（`Exploring`、`Candidate`、`Pinned`、`Golden`）和驻留状态（`resident`、`recipe_only`、`archived`、`missing`）。

FR20: [MVP] 系统可以在宽限期后将 Exploring 制品集降级为 `recipe_only`，回收输出文件，并明确提示该版本 checkout 时需要降级物化或重跑。

FR21: [MVP] PD Lead 可以手动将制品集晋升到更高生命周期评审阶段。

FR22: [Growth] 系统可以将 Golden 阶段制品集设置为只读，并禁止修改或删除。

FR23: [Growth] 系统可以为 Golden 阶段制品集存储多副本冗余备份。

FR24: [MVP] IT 管理员可以在 NAS 目录上初始化 BIG 版本仓库。

FR25: [Growth] IT 管理员可以配置分层存储策略，包括 Golden 副本数量和备份路径。

FR26: [MVP] IT 管理员可以查看仓库存储使用统计，包括总用量、CAS 去重比和各生命周期层级数据量。

FR27: [Growth] IT 管理员可以执行垃圾回收，释放被淘汰分支产生的孤立存储块。

FR28: [Growth] IT 管理员可以导出 Golden 制品集用于归档，并支持完整性校验。

FR29: [Growth] BIG 流水线 step 可以将 `pds_xxx` 等外部命令作为子进程执行。

FR30: [Growth] 外部系统可以通过基于版本化公共 HTTP API 的 Python SDK client 调用 BIG 版本管理操作；SDK 不得直接导入服务端数据库或业务实现。

FR31: [Growth] BIG 可以与现有自动化流程系统双向交互，包括 BIG 调用 `pds_xxx`，以及 `pds_xxx` 调用 BIG。

FR32: [MVP] 工程师可以通过 CLI 内置帮助获取每个命令的使用说明。

FR33: [MVP] 工程师可以选择性 checkout 制品集中的文件子集，而不是全量加载，以支持百万文件级项目。

FR34: [MVP] 工程师可以在血缘追踪中跨分支链接上下游制品集依赖，表达一个分支的输出被另一个分支作为输入。

FR35: [Growth] 工程师可以声明跨流程依赖关系，例如 `top_die_apr v3` 的输出 LEF 被 `bottom_die_apr v5` 依赖。

FR36: [Growth] 当跨流程依赖的上游版本发生变更时，系统可以标记受影响的下游版本并发出预警。

FR37: [Growth] BIG 可以与 DSO 系统集成，使 DSO 的每个 APR case 自动创建为带 PPA 指标的 BIG 制品集版本。

FR38: [Growth] 系统可以使用加权 PPA 得分驱动存储淘汰策略：保留 Top-K 设计的完整 DB，低排名 DB 保留 Exploring 评审状态并将驻留状态降级为 `recipe_only`；PPA 得分由 DSO 系统计算并随制品集提交，BIG 将其作为淘汰决策输入。

FR39: [Growth] 工程师可以配置存储水位线，当磁盘使用率达到阈值时自动触发淘汰策略回收空间。

FR40: [MVP] 系统必须将 CAS 对象发布为只读不可变文件，并且不得通过可写 hardlink 或 symlink 将 CAS 对象直接暴露给 EDA 工作区。

FR41: [MVP] 系统必须在 commit 时先建立一致 staging 快照，检测复制期间发生变化的文件，并在全部 CAS 对象发布成功后再原子提交 manifest。

FR42: [MVP] 系统必须通过由 `big` 命令按需启动的命令作用域 `bigd` 子进程处理 commit、branch 和 audit 写操作；该 `bigd` 在命令执行期间提供单写元数据边界，命令完成后退出。SQLite 仅作为 `bigd` 本地磁盘上的可替换 adapter，客户端不得共享打开 NAS 上的数据库文件，应用层只能依赖 `MetadataRepository` 接口。Growth 阶段需要常驻公共 API、事件流或多客户端服务化时，由新的 `big service` 能力承载。

FR43: [MVP] 系统必须在内部为用户私有稳定分支目录维护 owner、host、root、branch/version、generation、受管 lease 与显式 `restore journal`。branch checkout 不得改写源目录；手工启动的 EDA 写入进程无法可靠自动发现，因此 `big restore --in-place` 前停止写入属于使用契约，严格受控执行可通过 `big run -- <command>` 获取 lease。

FR44: [Growth] 系统必须使用完整 `action_hash` 作为可复用输出缓存 Key，至少包含命令、依赖摘要、参数、工具/PDK/库版本、选定环境变量、平台和 schema 版本。

FR45: [Growth] 当制品集标记为 Candidate 时，系统必须在同一事务中记录状态迁移、审计和可靠 `outbox` 事件；流水线幂等消费事件，只从不可变 manifest/CAS 物化到 staging，验证后发布版本化交付目录。

FR46: [Growth] 官方 GUI 和外部定制 GUI 必须通过同一版本化公共 API、OpenAPI schema 和事件契约接入；不得依赖 GUI 专用业务端点、直连数据库或导入服务端模块。

### 非功能需求

NFR1: 通过 BIG 读取文件的吞吐量必须不低于 NAS 直读的 70%，使用 dd/fio 基准和 EDA 工作负载回放，在至少 10 GB 数据集上测量。

NFR2: 存储层读写吞吐量必须至少达到 1 GB/s，在 CentOS + NAS 生产环境中使用 fio 顺序读写基准测量。

NFR3: 在含至少 1 万个制品集版本的仓库中，单次血缘链查询必须在 30 秒内完成。

NFR4: commit 额外开销必须低于纯文件哈希计算时间的 10%，且在 100+ case 的 DSO 批量 commit 场景下不得出现并发性能下降。

NFR5: 新分支物化或显式原地 restore 的完成延迟必须低于等量 `cp` 操作的 2 倍，使用低版本 NAS 上的 copy-only 物化，并覆盖 10 万级文件数据集。

NFR6: 系统必须支持 10 名工程师从各自私有目录并发向同一分支 commit，连续 100 轮无冲突、无数据损坏、无数据丢失。

NFR7: 所有版本管理操作必须经过权限检查；未授权操作拒绝率必须达到 100%，覆盖 CLI 命令和用户/组/角色组合。

NFR8: 所有写操作，包括 commit、promote 和权限变更，必须记录到服务端 append-only hash-chain 审计日志，并定期外部锚定，篡改必须可检测。

NFR9: CAS 文件内容哈希校验必须达到 100% 通过率，包括写入后回读校验和定期全仓库完整性扫描。

NFR10: 权限模型必须不超过 5 个核心概念，并与 Linux 风格的用户、组、读、写、所有者概念对齐。

NFR11: Golden 数据必须满足已定义的 RPO/RTO 目标，并在单一故障域失效时保持完整可读，通过故障模拟和季度恢复演练验证。

NFR12: 非 Golden 数据丢失率必须低于 0.01%，通过 CAS 对象损坏注入和 6 个月运行统计验证。

NFR13: Golden 数据必须在不同故障域中至少保留 2 份副本，通过副本分布检查、每日 scrub 和不一致修复验证。

NFR14: 单个 CAS 对象或 Growth 阶段单个 chunk 损坏时，系统必须可检测、可报告，且不影响无关数据。

NFR15: 系统必须支持单项目至少 100 万个文件的版本管理。

NFR16: 系统必须支持单项目至少 1 PB 数据的版本管理。

NFR17: 系统必须支持至少 10 万个制品集版本历史的查询。

NFR18: Python SDK 公共 API client 必须支持 commit、checkout、log、branch 等核心操作，行为与 CLI 等价。

NFR19: 流水线子进程执行必须能准确捕获正常、失败和大量输出 step 的退出码、stdout 与 stderr。

NFR20: BIG 管理的文件必须能通过用户私有稳定分支目录中的真实 NAS 路径直接访问；branch checkout 不得改变仍被运行中进程使用的目录，显式 restore 必须拒绝 dirty state 或活动受管 lease。

NFR21: 系统必须支持单模块至少 500 组 APR case 的 DSO 寻优分组版本管理与存储淘汰。

NFR22: CLI、SDK、官方 GUI 和外部定制 GUI 必须共享版本化公共 API 与事件契约，不得存在 GUI 专用业务端点。

### 附加要求

- Starter template：Python CLI/service 使用 Click 8.1、`src` layout 和 `pyproject.toml`；GUI 使用 Electron + Vue 3，通过 `electron-vite` 初始化，并采用严格 TypeScript、main/preload/renderer 进程分离和 Vite 开发流程。

- MVP 首个实现 Story 必须优先建立命令作用域 `bigd` 子进程的单写元数据边界、不可变文件级 NAS CAS、用户私有稳定分支目录 checkout，以及显式 restore 边界。GUI 与常驻 `big service /api/v1` 属于 Growth 阶段能力，不是 MVP 产品边界。

- 架构基线必须覆盖早期冲突结论：MVP 不允许多客户端共享写入 NAS 上的 SQLite 数据库，不允许在活跃 EDA 目录中原地切换分支，不使用可变 `current` symlink 作为隔离边界，不依赖 reflink/COW，不通过 writable hardlink/symlink 暴露 CAS 对象，也不把 FastCDC、Pack、GUI、自动 recipe cache 复用提前到 MVP。

- 元数据层必须使用 `MetadataRepository` 作为 port；MVP 用 SQLite WAL 作为命令作用域 `bigd` 子进程的本地 adapter，后续 `big service` 常驻服务模式可替换为 PostgreSQL 或其他 adapter。

- 版本祖先关系与数据血缘关系必须分开建模：`version_parent` 表达 commit/derived-from 祖先关系，`provenance_edge` 表达 consumes、produces、depends-on 数据关系。

- 评审状态和驻留状态必须是独立状态机，并支持 PRD 中定义的值：`Exploring`、`Candidate`、`Pinned`、`Golden`，以及 `resident`、`recipe_only`、`archived`、`missing`。

- commit 必须采用 staging-copy 语义：流式 SHA-256、复制前后 inode/size/mtime 稳定性检查、文件不稳定时重试或失败、回读校验、CAS 对象发布和最终 manifest 提交。

- MVP 的 CAS 存储必须使用 SHA-256 文件级不可变对象，发布为只读文件并直接位于 NAS 路径上。Growth 只有在 EDA benchmark 验证通过后，才可以引入 FastCDC 或 pack 格式。

- 归档与压缩文件处理必须遵循压缩研究：先去重再压缩，优先使用带跳过启发式的 per-object compression，默认避免面向用户可见数据的 whole-stream compression；除非命令显式选择语义/规范化归档再生成，否则 checkout 必须 byte-exact。

- 稳定分支 checkout 必须解析或物化兄弟目录，再依赖 shell 集成改变父 shell 的当前目录；没有 shell 集成时，CLI 必须输出 `cd -- <target-path>` 命令。

- 仓库边界应是逻辑设计仓库，而不是单个工程师私有仓库。管理员在项目族/设计项目层初始化 BIG 仓库，并登记一个或多个 NAS work root；3DIC 场景下四个物理 root（3D、Top、Bottom、MIX）共享同一个逻辑血缘、生命周期和存储治理空间。每个 work root 可放置轻量指针或配置，使用户在原有目录内执行 `big` 命令时能解析到同一个逻辑仓库。

- 显式原地 restore 必须是独立受控操作，包含 dirty 检查、受管 lease 检查、copy-only 物化、同目录临时文件、逐文件替换、`restore journal`、generation 更新，并提示用户重新打开文件或重启工具。

- Candidate 交付必须使用事务记录的 `outbox` 事件，并由流水线从不可变 manifest/CAS 幂等消费到 staging，随后验证并发布版本化交付目录。

- Growth 阶段的公共集成边界必须由 `big service /api/v1`、OpenAPI 和事件契约承载。CLI、SDK、官方 GUI 与外部定制 GUI 必须共享服务端业务规则；MVP 的 `bigd` 仅作为 `big` 命令按需启动的内部单写子进程。

- 安全实现必须包含类 Linux 权限概念、分支级 ACL enforcement、append-only audit hash chain，以及显式 Golden 操作保护。

- 可靠性实现必须在任何“零丢失”宣称前定义 Golden RPO/RTO、故障域隔离、不可变副本、每日 scrub、修复流程和恢复演练。

- 性能工作必须包含 NAS 专项基准：commit 开销、checkout 物化、并发 commit、读吞吐和 DSO 批量 commit 行为。

- 项目结构必须保持架构边界：领域/应用逻辑位于 Python core packages，CLI/SDK/API 是薄 adapter，GUI 是通过 HTTP API 通信的独立 client，业务逻辑不得泄漏到 GUI-only endpoint。

- Growth 需求必须预留扩展点：pipeline runner、FastCDC/chunk storage、DSO grouping 与 PPA metadata、`action_hash` 复用、OpenAPI schema 成熟、外部 GUI 定制和分布式元数据演进。

- Epic/Story 拆分完成后，必须重新回审 PRD、UX 与 Architecture，因为当前 PRD 验证报告已被 2026-06-02 的进程隔离和 API 边界修订覆盖。

### UX 设计需求

UX-DR1: CLI 和 GUI 必须共同维护同一心智模型：版本是输入、参数文件和输出的完整状态快照，而不是文件差异历史。

UX-DR2: `big commit` 必须是定义性交互：一条命令锁定当前状态，内部透明执行快照流程，manifest 发布后工作目录保持不变。

UX-DR3: 分支切换 UX 必须清楚传达 checkout 是进入另一个稳定兄弟目录，不修改旧目录，也不打扰正在运行的 EDA 进程。

UX-DR4: 显式原地 restore 的 UX 必须与 checkout 分离，并展示 dirty state 检查、活动 lease 检查、变化文件数、数据大小、`restore journal` 行为，以及重新打开文件或重启工具的提醒。

UX-DR5: CLI 输出必须使用渐进式披露：默认输出简洁摘要，`--verbose` 展开配方详情，`--full` 展开文件列表。

UX-DR6: 每个操作都必须以确定性反馈结束：成功使用绿色成功标记和摘要，失败使用红色失败标记、原因和可操作建议，警告展示风险和继续/取消选择，长操作展示可见进度。

UX-DR7: 生命周期状态必须使用 CLI/GUI 共享的颜色和文字标签体系：Exploring 灰色、Candidate 蓝色、Pinned 橙色、Golden 金色并增加额外视觉区分；状态必须通过文字表达，不能只依赖颜色。

UX-DR8: 评审状态和驻留状态必须独立展示，例如 `[Candidate/resident]`，不得折叠为单一状态。

UX-DR9: CLI 版本 ID 与 GUI 实体 ID 必须完全一致，使 CLI 输出可以作为 GUI 搜索锚点。

UX-DR10: GUI 导航必须支持 Ctrl+K 命令搜索、选中实体的 URL/前进后退状态，以及 GUI 节点或操作对应的等效 CLI 命令展示。

UX-DR11: 破坏性或不可逆操作必须确认。Golden 晋升必须输入 `GOLDEN`；显式 restore 丢弃变更必须显式选择；可逆操作不应增加确认摩擦。

UX-DR12: 搜索与过滤必须支持 CLI 默认 20 条摘要并通过 `--limit` 扩展，GUI 模糊匹配实时高亮，百万文件仓库使用索引搜索。

UX-DR13: 空状态必须包含下一步可执行动作；加载超过 2 秒必须显示进度或与实际布局匹配的骨架屏，避免视觉跳动。

UX-DR14: GUI 设计系统必须以 Ant Design Vue 4.x 为基础，通过 ConfigProvider 和 Design Token 定制，而不是 fork 基础组件。

UX-DR15: GUI 实现必须使用 Vue 3、TypeScript、Vite、Electron、Ant Design Vue，并在 Ant Design Vue 没有原生图组件的场景使用 G6 或 D3 渲染图。

UX-DR16: MVP GUI 布局在实现时必须使用结构化开发者工作台模式：左侧版本树、中央详情面板、底部可折叠日志/终端/审计面板。

UX-DR17: MVP GUI 核心视图必须包含版本树、配方详情、文件变更列表、生命周期 badge/tag、分支选择器、确认交互、tabs、进度指示、alert/notification、存储统计和配置表单，并使用 Ant Design Vue 组件。

UX-DR18: `LineageGraph` 在 MVP 中必须用递归 Tree 渲染血缘，支持节点展开和生命周期标记；Growth 阶段演进为 G6 DAG 图，支持缩放、平移、搜索、跨分支链接、键盘聚焦和屏幕阅读器语义。

UX-DR19: `StorageGauge` 必须展示磁盘使用率百分比、生命周期分段分布和阈值状态；MVP 使用 Progress circle，Growth 可使用自定义 SVG。

UX-DR20: `DiffPanel` 必须展示配方差异；MVP 的 CLI 使用 unified diff 格式，Growth GUI 使用双栏高亮差异。

UX-DR21: GUI 终端能力实现时，`TerminalPanel` 必须支持内嵌终端行为，包括 ANSI 颜色解析、命令历史和 Ctrl+C 中断。

UX-DR22: Growth GUI 必须包含 `DsoGroupOverview`，展示顶部摘要统计、排名表、Top-K 上下文、回收空间可见性和批量驻留操作。

UX-DR23: Growth GUI 必须包含 `LifecycleTimeline`，展示评审状态流转，并独立显示驻留状态变化。

UX-DR24: GUI 响应式目标仅面向桌面：compact <=1280px 时左侧面板折叠为 48px 图标栏并折叠底部面板，standard 1281-1919px 展示三栏，wide >=1920px 支持更大面板和中央并排内容。

UX-DR25: 无障碍必须达到 WCAG 2.1 AA：文本对比度、键盘覆盖、ARIA labels/roles、状态变化使用 `aria-live`、状态通过颜色+文字+图标传达、2px 焦点环、reduced-motion 支持、200% 字体缩放，以及图视图的语义隐藏 DOM。

UX-DR26: CLI 输出必须在 SSH 场景中可用，并能自适应终端宽度，不依赖 GUI 或 X11。

UX-DR27: 自定义 GUI 组件必须复用 Ant Design Vue token 的颜色、字体和间距；间距遵循 8px 网格；GUI 图标使用 Ant Design Icons；组件优先级为原生、组合、自定义。

UX-DR28: 视觉配色必须保持专业开发者工具的信息密度，并使用文档定义的语义色，包括主色深青蓝 `#0E7C86`、成功 `#52C41A`、警告 `#FA8C16`、错误 `#F5222D`、信息 `#1677FF` 和中性色文本/背景。

### FR 覆盖映射

FR1: Epic 1 - 可信制品集提交与仓库基线
FR2: Epic 1 - 可信制品集提交与仓库基线
FR3: Epic 3 - 版本历史、配方洞察与血缘追溯
FR4: Epic 3 - 版本历史、配方洞察与血缘追溯
FR5: Epic 3 - 版本历史、配方洞察与血缘追溯
FR6: Epic 2 - 安全分支工作区与受控恢复
FR7: Epic 1 - 可信制品集提交与仓库基线
FR8: Epic 2 - 安全分支工作区与受控恢复
FR9: Epic 2 - 安全分支工作区与受控恢复
FR10: Epic 2 - 安全分支工作区与受控恢复
FR11: Epic 2 - 安全分支工作区与受控恢复
FR12: Epic 2 - 安全分支工作区与受控恢复
FR13: Epic 2 - 安全分支工作区与受控恢复
FR14: Epic 3 - 版本历史、配方洞察与血缘追溯
FR15: Epic 3 - 版本历史、配方洞察与血缘追溯
FR16: Epic 3 - 版本历史、配方洞察与血缘追溯
FR17: Epic 3 - 版本历史、配方洞察与血缘追溯
FR19: Epic 4 - 生命周期评审与存储可见性
FR20: Epic 4 - 生命周期评审与存储可见性
FR21: Epic 4 - 生命周期评审与存储可见性
FR22: Epic 5 - Golden 治理、冗余与归档
FR23: Epic 5 - Golden 治理、冗余与归档
FR24: Epic 1 - 可信制品集提交与仓库基线
FR25: Epic 5 - Golden 治理、冗余与归档
FR26: Epic 4 - 生命周期评审与存储可见性
FR27: Epic 5 - Golden 治理、冗余与归档
FR28: Epic 5 - Golden 治理、冗余与归档
FR29: Epic 6 - 公共 API、自动化集成与 Candidate 交付
FR30: Epic 6 - 公共 API、自动化集成与 Candidate 交付
FR31: Epic 6 - 公共 API、自动化集成与 Candidate 交付
FR32: Epic 1 - 可信制品集提交与仓库基线
FR33: Epic 2 - 安全分支工作区与受控恢复
FR34: Epic 3 - 版本历史、配方洞察与血缘追溯
FR35: Epic 7 - 3DIC 跨流程依赖管理与影响预警
FR36: Epic 7 - 3DIC 跨流程依赖管理与影响预警
FR37: Epic 8 - DSO 寻优 case 管理与 PPA 驱动存储优化
FR38: Epic 8 - DSO 寻优 case 管理与 PPA 驱动存储优化
FR39: Epic 8 - DSO 寻优 case 管理与 PPA 驱动存储优化
FR40: Epic 1 - 可信制品集提交与仓库基线
FR41: Epic 1 - 可信制品集提交与仓库基线
FR42: Epic 1 - 可信制品集提交与仓库基线
FR43: Epic 2 - 安全分支工作区与受控恢复
FR44: Epic 6 - 公共 API、自动化集成与 Candidate 交付
FR45: Epic 6 - 公共 API、自动化集成与 Candidate 交付
FR46: Epic 6 - 公共 API、自动化集成与 Candidate 交付

## Epic 清单

### Epic 1：可信制品集提交与仓库基线
工程师和 IT 可以初始化仓库，并用 `big commit` 锁定输入、参数、输出的完整快照，形成不可变、可追溯的版本基础。
**FRs covered:** FR1, FR2, FR7, FR24, FR32, FR40, FR41, FR42

### Epic 2：安全分支工作区与受控恢复
工程师可以在已登记 NAS work root 下的稳定真实目录中切换分支、从历史版本创建新分支、选择性 checkout，并通过显式 restore 受控改写当前目录。
**FRs covered:** FR6, FR8, FR9, FR10, FR11, FR12, FR13, FR33, FR43

### Epic 3：版本历史、配方洞察与血缘追溯
工程师可以查看历史、配方详情、配方差异、回退语义、上游血缘、下游影响和基础跨分支依赖关系。
**FRs covered:** FR3, FR4, FR5, FR14, FR15, FR16, FR17, FR34

### Epic 4：生命周期评审与存储可见性
PD Lead 可以推动制品集从 Exploring 到更高评审阶段，系统可以独立管理驻留状态，并让 IT 查看存储使用情况。
**FRs covered:** FR19, FR20, FR21, FR26

### Epic 5：Golden 治理、冗余与归档
团队可以保护 Golden 制品集，配置冗余和分层策略，执行 GC，并导出可校验归档。
**FRs covered:** FR22, FR23, FR25, FR27, FR28

### Epic 6：公共 API、自动化集成与 Candidate 交付
外部系统、Python SDK、流水线和 GUI 可以通过常驻 `big service /api/v1` 的统一公共契约接入 BIG，并从 Candidate 事件可靠发布交付目录。
**FRs covered:** FR29, FR30, FR31, FR44, FR45, FR46

### Epic 7：3DIC 跨流程依赖管理与影响预警
3DIC PD Lead 和工程师可以在 3D、Top、Bottom、MIX 四个并行 work root 之间声明 top/bottom die、跨 APR flow、跨分支制品集依赖关系，并在上游版本变化时识别受影响下游版本。
**FRs covered:** FR35, FR36

### Epic 8：DSO 寻优 case 管理与 PPA 驱动存储优化
DSO 工程师可以让每个 APR case 自动形成 BIG 制品集版本，并按 PPA 排名与存储水位线保留 Top-K 完整 DB、淘汰低价值 DB。
**FRs covered:** FR37, FR38, FR39

## Epic 1：可信制品集提交与仓库基线

工程师和 IT 可以初始化仓库，并用 `big commit` 锁定输入、参数、输出的完整快照，形成不可变、可追溯的版本基础。

### Story 1.1：初始化逻辑 BIG 仓库与登记 NAS work roots

作为 IT 管理员，
我想要用 `big repo init` 初始化项目级逻辑 BIG 仓库，并为该项目登记一个或多个 NAS work root，
以便工程师继续在现有 `/data/.../user/<Username>/{APR,SYN,PV,STA,PI,...}` 目录中工作，同时 BIG 能用统一的项目级元数据、CAS、血缘和审计空间管理所有制品集版本。

**Acceptance Criteria:**

**Given** 一个普通 2D 项目的 NAS 根目录 `/data/<ProjectName>`
**When** IT 管理员执行 `big repo init /data/<ProjectName> --repo-id <ProjectName>`
**Then** 系统在 `/data/<ProjectName>` 下创建主 `big.toml` 和 `.big/` 仓库内部目录
**And** 将 `/data/<ProjectName>` 登记为该逻辑仓库的默认 work root
**And** 将 `integration` 缺省记录为 `2d`。

**Given** 一个 3DIC 项目存在四个并行 NAS 根目录：`/data/<ProjectName>_3D`、`/data/<ProjectName>_Top`、`/data/<ProjectName>_Bottom`、`/data/<ProjectName>_MIX`
**When** IT 管理员执行：
```bash
big repo init /data/<ProjectName>_3D \
  --repo-id <ProjectName> \
  --integration 3d \
  --work-root 3d=/data/<ProjectName>_3D \
  --work-root top=/data/<ProjectName>_Top \
  --work-root bottom=/data/<ProjectName>_Bottom \
  --work-root mix=/data/<ProjectName>_MIX
```
**Then** 系统在 `/data/<ProjectName>_3D` 下创建主 `big.toml` 和 `.big/` 仓库内部目录
**And** 在 `/data/<ProjectName>_Top`、`/data/<ProjectName>_Bottom`、`/data/<ProjectName>_MIX` 下创建指针型 `big.toml`
**And** 将 `_3D`、`_Top`、`_Bottom`、`_MIX` 四个 NAS root 绑定到同一个逻辑 BIG 仓库
**And** 将 `integration` 记录为 `3d`。

**Given** `/data/<ProjectName>_3D/big.toml` 是主配置
**When** 系统读取该配置
**Then** 该配置声明逻辑仓库 `repo_id`、`integration = "3d"`、仓库 home 和四个 work root
**And** `.big/` 仓库内部目录只位于 `/data/<ProjectName>_3D` 下。

**Given** `/data/<ProjectName>_Top/big.toml`、`/data/<ProjectName>_Bottom/big.toml` 或 `/data/<ProjectName>_MIX/big.toml` 是指针配置
**When** 系统读取该配置
**Then** 该配置声明相同 `repo_id`、指向 `/data/<ProjectName>_3D` 的仓库 home，以及对应的 `work_root_id`
**And** 指针配置不得创建自己的 `.big/` 仓库内部目录。

**Given** 工程师在任一已登记 work root 下的既有目录工作，例如 `/data/<ProjectName>_Top/user/<Username>/APR`
**When** 工程师执行 `big` 命令
**Then** 系统通过向上查找最近的 `big.toml` 解析出所属逻辑仓库、work root、用户和 flow workspace
**And** 四个 root 中任一子目录执行 `big` 命令都解析到同一个逻辑 BIG 仓库
**And** 物理目录名 `APR/SYN/PV/STA/PI` 不被默认解释为 branch，branch/version 由 BIG 元数据单独记录
**And** 在未显式 checkout 或指定命名 branch 前，当前上下文的默认提交目标是由 work root、用户和 flow workspace 派生的 workspace-private ref，例如 `workspace/<work_root_id>/<Username>/<Flow>`，不得默认汇聚到共享 `main`。

**Given** 一个需要写元数据的 `big` 命令
**When** 命令执行
**Then** `big` 按需启动命令作用域 `bigd` 子进程
**And** `bigd` 在本次命令期间通过 `MetadataRepository` 执行单写事务，命令完成后退出。

**Given** 多个工程师可能在不同 work root 或不同机器上执行 BIG 命令
**When** 这些命令需要写入同一个逻辑仓库元数据
**Then** 系统不得让多个客户端直接共享打开 NAS 上的 SQLite 数据库文件
**And** MVP 必须通过命令作用域 `bigd` 的单写边界与项目级写入协调机制保证元数据一致性。

**Given** 未来需要常驻公共 API、SDK、GUI、事件流或外部系统接入
**When** 进入 Growth 阶段
**Then** 该能力由新的 `big service` 承载
**And** MVP 的 `bigd` 不被误解为默认常驻服务。

**Given** 仓库已经初始化过
**When** IT 管理员再次执行初始化或重复登记相同 work root
**Then** 系统返回幂等结果或明确提示该逻辑仓库/work root 已存在
**And** 不破坏已有配置、元数据、CAS 对象或用户工作目录。

**Given** 初始化路径、work root 权限或配置不合法
**When** IT 管理员执行初始化
**Then** 系统失败并输出明确原因
**And** 不留下半初始化状态。

### Story 1.2：捕获 EDA 文件制品并发布统一文件级 CAS 快照

作为工程师，
我想要 BIG 将一次 EDA step 涉及的输入文件和输出文件都按原始字节捕获，并发布为只读不可变的文件级 CAS 对象，
以便脚本、配置、库文件、网表、LEF/DEF、GDS、SPEF、Log、Report 等不同类型文件都能被精确追踪、校验和复用，同时保留它们的 EDA 语义差异。

**Acceptance Criteria:**

**Given** 一个 EDA step 包含输入文件和输出文件
**When** 工程师执行 commit
**Then** 系统可以接收并区分输入与输出文件集合
**And** 输入/输出都通过统一 FileRef 模型记录。

**Given** 输入文件包含 Tcl、SDC、YAML、JSON、runset 等脚本或配置文件
**When** 系统捕获这些文件
**Then** 系统按原始字节计算 SHA-256 并发布到文件级 CAS
**And** 即使这些文件可编辑、经常变化，也以 commit 当时的字节内容作为不可变快照保存。

**Given** 输入文件包含 RTL、Netlist、LEF、DEF、Liberty、TechLib、PDK library view 或类似 EDA 大文件
**When** 系统捕获这些文件
**Then** 系统同样按原始字节计算 SHA-256 并发布到文件级 CAS
**And** 不因文件是文本格式或可读格式而改变底层快照保存方式。

**Given** 输出文件包含 Log、Report、DEF、Netlist、GDS/OASIS、SPEF/DSPF、SDF 或工具数据库
**When** 系统捕获这些输出
**Then** 系统同样按原始字节计算 SHA-256 并发布到文件级 CAS
**And** 输出文件与输入文件使用同一套 CAS 完整性和复用机制。

**Given** 某些文件虽然是人可读文本格式，但主要供 EDA 工具解析，例如 LEF、DEF、Liberty、Verilog netlist
**When** 系统记录文件元数据
**Then** 系统不得简单把“文本文件”解释为“用户可编辑脚本”
**And** 必须记录 `semantic_role` 和 `format_hint`，区分脚本/配置、设计源文件、设计交换格式、库视图、工具输出、报告和日志。

**Given** 脚本或配置文件来自外部 Git 仓库
**When** 系统捕获这些文件
**Then** BIG 仍必须将 commit 当时的文件字节内容保存到 BIG CAS
**And** 可选记录 Git repo、commit hash、branch/tag、dirty state 等 provenance 信息，但 Git 信息不得替代 BIG CAS 快照。

**Given** 某个 CAS 对象尚不存在
**When** 系统发布该对象
**Then** 系统先写入临时文件并完成回读校验
**And** 校验通过后以 create-if-absent 语义发布到 `.big/cas/`
**And** 发布后的 CAS 对象权限被设置为只读不可变。

**Given** 相同 SHA-256 摘要的 CAS 对象已经存在
**When** 系统再次捕获相同内容
**Then** 系统复用已有 CAS 对象
**And** 不重复写入新的对象文件。

**Given** CAS 对象发布或回读校验发现摘要不一致
**When** 系统处理该文件
**Then** 发布失败并返回明确的数据完整性错误
**And** 不创建可被 manifest 引用的 FileRef。

**Given** EDA 工作区需要读取或物化文件
**When** 系统使用 CAS 对象作为来源
**Then** 系统不得通过 writable hardlink 或 symlink 将 CAS 对象直接暴露给工作区
**And** 后续工作区物化只能通过受控 copy/restore 流程处理。

**Given** 文件格式未知或工具私有
**When** 系统无法识别格式
**Then** 系统仍可将其作为 `raw_file` 捕获并发布到 CAS
**And** 不阻断 commit，除非文件读取、权限或完整性校验失败。

### Story 1.3：验证 stable capture 条件、创建 staging snapshot 并原子提交 manifest

作为工程师，
我想要 `big commit` 在发布版本前先把目标文件集捕获到稳定的 staging snapshot，并检测复制期间发生变化的源文件，
以便即使 EDA 工具可能在工作目录中读写大量文件，BIG 也只能发布已经稳定捕获并成功写入 CAS 的内容，同时清楚表达本次 commit 对源目录一致性的证明边界。

**设计补充：Perforce/Helix Core 参考**

- Perforce 的 `p4 submit` 保证的是 changelist 级 depot 原子提交：文件要么全部保存到 depot，要么都不保存；提交前会短暂锁定提交文件，但这个锁属于 Perforce 工作流边界，并不等价于锁住任意本地 EDA 进程正在写的源目录。参考：[p4 submit](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/CmdRef/p4_submit.html)。
- 如果芯片设计公司把 EDA 写入与 submit 冲突问题交给 Perforce，成熟做法会先尝试把 EDA 写入纳入受控 workspace：使用 `noallwrite` 让未打开文件默认只读，通过 `p4 edit` 打开需要修改的文件；流程结束后用 `p4 reconcile` 把外部生成、修改、删除的文件整理成 changelist。参考：[workspace options](https://help.perforce.com/helix-core/server-apps/p4guide/current/Content/P4Guide/configuration.workspace.options.html)、[p4 edit](https://help.perforce.com/helix-core/server-apps/cmdref/2022.2/Content/CmdRef/p4_edit.html)、[p4 reconcile](https://help.perforce.com/helix-core/server-apps/cmdref/2023.1/Content/CmdRef/p4_reconcile.html)。
- 对 GDS/OASIS、工具 DB、关键 DEF/Netlist 等不适合并发编辑或合并的文件，Perforce 可用 typemap `+l` exclusive open 或 `p4 lock` 降低多人提交冲突；pre-submit trigger 可做流程门禁、配套文件校验或 marker 校验，但这些机制仍不能证明非受控 EDA 进程已经停止写入。参考：[exclusive locking](https://help.perforce.com/helix-core/server-apps/p4sag/2023.2/Content/P4SAG/superuser.basic.typemap_locking.html)、[p4 lock](https://help.perforce.com/helix-core/server-apps/cmdref/current/content/CmdRef/p4_lock.html)、[p4 triggers](https://help.perforce.com/helix-core/server-apps/cmdref/2023.1/Content/CmdRef/p4_triggers.html)。
- 因此 BIG 的 MVP 设计不得宣称“源目录天然被锁住”。BIG 可以保证的是：manifest 发布是原子的；manifest 只引用已经从 staging 成功发布到 CAS 的不可变对象；源目录一致性只能通过 stable capture 检测、外部 success marker、用户显式 quiet-state 约定或 NAS/filesystem snapshot 增强证明。

**Acceptance Criteria:**

**Given** 工程师执行 `big commit` 并指定或通过配置解析出本次 EDA step 的目标文件集
**When** commit 开始
**Then** 系统创建本次 commit 私有的 staging capture 上下文
**And** 在全部文件通过稳定性检查、CAS 发布和 manifest 提交前，不创建对用户可见的制品集版本。

**Given** 目标文件集来自命令参数、配置、清单或 glob/pattern
**When** 系统进入扫描阶段
**Then** 系统在扫描时解析出确定的候选文件列表
**And** 在 manifest 中记录本次 commit 实际捕获的文件列表与来源规则。

**Given** 系统准备捕获某个源文件
**When** 复制开始前
**Then** 系统记录可获得的源文件稳定性元数据，包括 size、mtime、ctime、inode 或平台可提供的等价字段
**And** 如果 NAS 或平台无法提供全部字段，系统必须保守降级，并在 capture evidence 中记录缺失字段。

**Given** 源文件正在被复制到 staging
**When** 复制完成
**Then** 系统只从 staging 副本计算 SHA-256
**And** 再次读取源文件稳定性元数据，与复制前记录进行比较。

**Given** 源文件在复制前后 size、mtime、ctime、inode 或可用等价字段发生变化
**When** 系统完成复制后校验
**Then** 系统判定该文件不稳定
**And** 根据配置进行有限重试或使 commit 失败
**And** 失败输出必须列出不稳定文件及检测到的变化证据。

**Given** 项目配置了 settle window
**When** 系统完成候选文件扫描或单文件捕获
**Then** 目标文件集和相关文件元数据必须在配置窗口内保持稳定
**And** 如果窗口内发生变化，系统必须重试或拒绝 commit。

**Given** 项目在 `big.toml` 中配置了外部 success marker 规则，例如 marker root 与 `{step}` pattern
**When** 工程师执行 `big commit --step <step> --require-marker`
**Then** 系统按项目配置解析 marker 路径并检查 success marker 是否存在
**And** marker 路径由外部流程系统拥有，不要求使用 `.big`、`big` 前缀或 BIG 专用目录
**And** 系统只要求 success marker，不要求外部系统提供 running、failed 或 meta 状态机。

**Given** `--require-marker` 被启用但配置的 success marker 不存在
**When** 工程师执行 commit
**Then** 系统拒绝 commit
**And** 仅提示“configured step success marker not found”及解析后的 marker 路径
**And** 不推断外部流程正在运行、已经失败或属于某个特定系统。

**Given** 本次 commit 未使用 success marker 且未从 NAS/filesystem snapshot 读取
**When** commit 成功
**Then** manifest 将 `capture_mode` 记录为 `best_effort`
**And** CLI summary 必须提示 BIG 已验证捕获文件在复制窗口内稳定，但未证明整个源目录具备事务级一致性。

**Given** 项目配置并启用了 NAS/filesystem snapshot 作为读取来源
**When** 工程师执行 commit
**Then** 系统从 snapshot 路径读取目标文件并记录 `capture_mode = "snapshot_sourced"`
**And** manifest 记录 snapshot 标识、snapshot 路径或外部 snapshot evidence。

**Given** 所有目标文件已经复制到 staging 并完成稳定性检查
**When** 系统发布 CAS 对象
**Then** manifest 只能引用 staging 副本计算出的 CAS hash 和 FileRef
**And** manifest 发布阶段不得再从源工作目录直接读取文件内容。

**Given** 某个文件的 CAS 发布、回读校验或稳定性检查失败
**When** commit 处理失败
**Then** 系统不得创建可见制品集版本
**And** 已创建的临时 staging 状态必须可清理或可诊断恢复
**And** 已成功发布的不可变 CAS 对象不得被当作完整 commit 暴露。

**Given** 所有目标文件均完成 staging 捕获、稳定性检查和 CAS 发布
**When** 命令作用域 `bigd` 提交元数据
**Then** `bigd` 在单个元数据事务中创建 manifest、制品集版本、文件引用和 provenance evidence
**And** 事务成功后该版本才对 `big log`、`big checkout` 和后续 lineage 查询可见。

**Given** commit 成功
**When** 系统输出 summary
**Then** summary 包含 commit ID、制品集状态、文件数量、总字节数、`capture_mode`、是否使用 success marker、是否使用 snapshot、失败重试次数和关键 warning
**And** 该输出在 SSH/CLI 场景下可读，不依赖 GUI。

### Story 1.4：提交包含 inputs 与 outputs 的制品集版本

作为工程师，
我想要通过 `big commit` 指定一次 EDA step 的输入文件和输出文件，并生成一个可追溯的制品集版本，
以便后续可以明确知道该版本消费了哪些输入、产出了哪些输出，并能用稳定 manifest 表达本次 EDA step 的结果。

**Acceptance Criteria:**

**Given** 工程师位于已登记 work root 下的 flow workspace
**When** 执行 `big commit --step <step> --inputs <path-or-glob> --outputs <path-or-glob>`
**Then** 系统创建一个新的制品集版本
**And** 该版本记录 step 名称、work root、flow workspace、用户、提交时间和 commit message
**And** 若用户未显式指定 `--branch` 或未处于已 checkout 的命名 branch 上，系统将该版本追加到当前 workspace-private ref
**And** 不同用户或不同 flow workspace 的默认 commit 历史彼此隔离，不得自动混入共享 `main`。

**Given** 工程师指定了 inputs 和 outputs
**When** 系统解析 commit 参数
**Then** 系统必须区分 `inputs` 与 `outputs` 两类文件角色
**And** 每个文件引用必须关联 FileRef、CAS hash、原始路径、文件大小和 capture evidence。

**Given** input path/glob 没有匹配任何文件
**When** 工程师执行 commit
**Then** 系统拒绝 commit
**And** 输出明确的遗漏输入提示。

**Given** inputs 中包含不存在、权限不可读、目录误作为文件、或被配置规则排除的路径
**When** 系统执行输入完整性校验
**Then** 系统拒绝 commit
**And** 输出错误输入列表及原因。

**Given** output path/glob 没有匹配任何文件
**When** 工程师执行 commit
**Then** 系统默认拒绝 commit
**And** 提示输出文件缺失，避免误提交不完整 step。

**Given** 所有 inputs 和 outputs 均通过 stable capture
**When** 系统提交 manifest
**Then** manifest 必须记录完整文件清单、文件角色、CAS hash、路径、大小和 capture evidence
**And** manifest 不再从源工作目录读取文件内容。

**Given** 系统生成制品集版本
**When** 计算本版本的初始 `recipe_hash`
**Then** `recipe_hash` 基于 step 标识、inputs 文件身份和 recipe schema version
**And** 不把 outputs 文件 hash 纳入 `recipe_hash`
**And** 本 Story 不引入独立 `params` 角色，脚本、配置、参数文件是否单独分类留待后续需求细化。

**Given** 两次 commit 的 step 与 inputs 身份完全一致但 outputs 不同
**When** 系统计算 `recipe_hash`
**Then** 两个版本可以拥有相同 `recipe_hash`
**And** 仍保留各自不同的 manifest、outputs FileRef 和 commit ID。

**Given** commit 成功
**When** CLI 输出 summary
**Then** summary 显示 commit ID、step、inputs 数量、outputs 数量、`recipe_hash`、capture mode 和制品集状态
**And** 默认输出保持简洁，`--verbose` 可展示更完整的 manifest 摘要。

**Given** commit 失败
**When** 系统输出错误信息
**Then** 错误必须区分遗漏输入、错误输入、缺失输出、stable capture 失败、CAS 发布失败和 manifest 事务失败
**And** 不创建可见制品集版本。

### Story 1.5：提供核心 CLI 帮助与错误引导

作为工程师，
我想要通过 CLI 内置帮助查看 `big`、`big repo init` 和 `big commit` 的命令说明、参数含义和典型示例，
以便在没有 GUI、没有额外文档入口的 SSH/NAS 工作环境中，也能正确初始化仓库和提交制品集版本。

**Acceptance Criteria:**

**Given** 工程师在任意目录执行 `big --help`
**When** CLI 渲染帮助信息
**Then** 输出显示 BIG 的用途摘要、全局选项、可用命令组和核心命令
**And** 帮助命令不要求当前目录属于已初始化 BIG 仓库。

**Given** 工程师执行 `big repo init --help`
**When** CLI 渲染初始化命令帮助
**Then** 输出说明普通 2D 项目的默认初始化形式：`big repo init /data/<ProjectName> --repo-id <ProjectName>`
**And** 输出说明 3DIC 项目的 `--integration 3d` 与多个 `--work-root` 用法。

**Given** 工程师执行 `big commit --help`
**When** CLI 渲染 commit 命令帮助
**Then** 输出说明当前实现支持的 commit 参数与能力，包括 step、inputs、outputs、commit message、success marker、settle window 和 verbose 输出
**And** 明确说明本阶段只区分 inputs 与 outputs，不引入独立 params 角色
**And** 具体参数名可在实现阶段按 CLI 设计调整，但帮助内容必须覆盖实际支持的参数和行为。

**Given** 工程师执行任一 Epic 1 范围内命令的 `--help`
**When** 命令帮助输出完成
**Then** 进程退出码为 0
**And** 不启动 `bigd`，不写元数据，不创建仓库目录或 staging 状态。

**Given** 工程师输入了缺失参数、未知参数或非法参数组合
**When** CLI 返回错误
**Then** 错误信息显示失败原因、相关参数名和可执行的下一步提示
**And** 提示用户使用对应命令的 `--help` 查看完整说明。

**Given** 工程师在窄终端或 SSH 环境中查看帮助
**When** CLI 输出帮助文本
**Then** 内容保持可读，不依赖 GUI、颜色或交互式 TUI
**And** 长示例可以换行，但不得破坏命令可复制性。

**Given** 后续 Epic 添加新的命令，例如 branch、checkout、log、restore
**When** 新命令进入实现范围
**Then** 必须复用本 Story 建立的帮助格式、错误引导和退出码约定
**And** 不得出现只在 GUI 或外部文档中可见的命令说明。

## Epic 2：安全分支工作区与受控恢复

工程师可以在已登记 NAS work root 下的稳定真实目录中切换分支、从历史版本创建新分支、选择性 checkout，并通过显式 restore 受控改写当前目录。

### Story 2.1：创建命名分支并基于 Linux groups 管理分支访问

作为 PD Lead，
我想要在逻辑 BIG 仓库中创建命名分支，并让分支访问权限绑定到公司现有 Linux groups 或预定义 ACL 模板，
以便团队可以围绕稳定分支开展并行设计工作，同时 BIG 不需要维护大量用户名单，也不会绕过公司统一权限体系。

**Acceptance Criteria:**

**Given** PD Lead 位于已初始化 BIG 仓库内且拥有创建分支权限
**When** 执行 `big branch create <branch-name> --from <source-ref>`
**Then** 系统创建一个命名分支记录
**And** 如果 `<source-ref>` 是 branch 名，系统将其解析为该 branch 在创建事务时的当前 head version
**And** 如果 `<source-ref>` 是 version ID，系统直接使用该 version 作为起点
**And** 新分支记录保存解析后的确定 version ID，不随后续 source branch 移动而变化。

**Given** PD Lead 创建分支时未指定 `--from`
**When** 系统可以从当前 work root/flow workspace 解析出当前 branch
**Then** 系统使用当前 branch 的 head version 作为新分支起点
**And** CLI summary 明确显示实际解析到的 source branch 和 source version。

**Given** PD Lead 创建分支时未指定 `--from`
**When** 当前上下文无法解析出 branch 或 head version
**Then** 系统拒绝创建分支
**And** 提示用户显式指定 `--from <source-ref>`。

**Given** 分支名称不合法、已存在、与保留名称冲突，或 `<source-ref>` 无法解析
**When** PD Lead 创建分支
**Then** 系统拒绝创建
**And** 输出明确原因，不创建半成品分支记录或半成品工作区。

**Given** source branch 已有分支 ACL
**When** PD Lead 创建新分支且未显式指定 ACL 模板
**Then** 新分支默认继承 source branch 的 ACL
**And** 系统在 audit 中记录继承来源、解析后的起点 version 和创建者。

**Given** 项目配置了 ACL 模板
**When** PD Lead 执行 `big branch create <branch-name> --from <source-ref> --acl-template <template-name>`
**Then** 系统按模板为新分支设置 owner group、read groups 和 write groups
**And** 模板中的主体必须是 Linux group principal，例如 `group:apr_team`
**And** BIG 不在分支 ACL 中展开或缓存 group 的完整成员名单。

**Given** ACL 模板引用了不存在或无法解析的 Linux group
**When** 系统创建分支或应用模板
**Then** 系统拒绝操作
**And** 输出无法解析的 group 名称和所属模板。

**Given** 用户执行需要分支权限的 BIG 操作
**When** 系统进行授权判断
**Then** BIG 通过 IdentityResolver 读取当前 Linux 身份，包括 username、uid、primary gid 和 supplementary groups
**And** MVP 的 IdentityResolver 使用 Linux/NSS 视角解析当前进程的 effective groups
**And** 授权判断基于当前用户是否命中分支 ACL 中的 Linux group principal。

**Given** 用户刚被公司权限系统加入某个 Linux group
**When** 用户当前 shell/session 尚未刷新 effective groups
**Then** BIG 可以仍按当前进程可见的 groups 做授权判断
**And** 权限不足错误应提示用户刷新 session、重新登录或联系 IT 确认 Linux group 生效。

**Given** 用户没有目标分支 read 权限
**When** 用户执行 `big checkout <branch>`、查看分支详情或读取该分支 manifest
**Then** 系统拒绝操作
**And** 不泄露受保护分支的文件清单、manifest 详情或物化路径信息。

**Given** 用户没有目标分支 write 权限
**When** 用户尝试向该分支 commit、移动分支指针、修改分支 ACL 或执行受控 restore
**Then** 系统拒绝操作
**And** 返回权限不足的确定性错误。

**Given** PD Lead 需要查看分支权限
**When** 执行 `big branch acl show <branch> --effective`
**Then** CLI 显示分支 ACL 中配置的 Linux group principals
**And** 显示当前用户的 effective read/write 结果和命中的授权 group
**And** 不要求枚举该 group 的所有成员。

**Given** PD Lead 需要进行少量例外授权
**When** 执行简单 ACL 变更，例如 `big branch acl grant <branch> --group <linux-group> --read` 或 `--write`
**Then** 系统记录 group 级 ACL 变更
**And** `write` 权限隐含 `read` 权限
**And** CLI 不鼓励逐个用户维护大规模成员名单。

**Given** 分支创建、ACL 模板应用或 ACL 变更成功
**When** `bigd` 提交元数据事务
**Then** 系统记录 append-only audit 事件
**And** audit 事件包含操作者 username/uid、创建时可见的 groups、命中的 ACL entry、分支名、source ref、resolved source version、权限变更摘要和事务 ID。

**Given** 多个 PD Lead 或自动化任务并发创建同名分支
**When** 元数据事务提交
**Then** 只有一个创建请求成功
**And** 失败请求返回分支已存在，不破坏已有分支记录。

### Story 2.2：checkout 到稳定真实分支工作目录且不改写源目录

作为工程师，
我想要通过 `big checkout <branch>` 进入目标分支对应的稳定真实 NAS 工作目录，
以便我可以在新目录中启动后续 EDA 工作，同时原目录中已经运行的 EDA 进程、cwd、打开文件和绝对路径都不被 BIG 改写或打断。

**Acceptance Criteria:**

**Given** 工程师位于已登记 work root 下的目录，例如 `/data/<ProjectName>/user/<Username>/APR`
**When** 执行 `big checkout <branch>`
**Then** 系统通过当前路径向上查找 `big.toml`，解析逻辑仓库、work root、用户和 flow workspace
**And** 将 `<branch>` 解析为目标分支当前 head version。

**Given** 用户对目标分支没有 read 权限
**When** 用户执行 `big checkout <branch>`
**Then** 系统拒绝 checkout
**And** 不泄露目标分支 manifest、文件列表或物化路径。

**Given** 用户对目标分支有 read 权限
**When** 系统解析 checkout 目标
**Then** 系统根据项目配置的 branch workspace path template 计算目标稳定目录路径
**And** 目标路径必须位于当前已登记 work root 的用户私有命名空间下
**And** 目标路径必须包含或关联 branch、version、generation 等可追踪信息
**And** 目标目录不得与当前源目录相同。

**Given** 目标分支工作目录已经物化且对应同一 branch head version
**When** 用户再次执行 `big checkout <branch>`
**Then** 系统复用已有稳定目录
**And** 不重复复制文件、不改变目录 generation。

**Given** 目标分支 head version 已变化
**When** 用户执行 `big checkout <branch>`
**Then** 系统创建或解析新的 generation 目录
**And** 不在旧 generation 目录中原地覆盖文件
**And** 仍在旧目录中运行的 EDA 进程不受影响。

**Given** 目标分支工作目录尚未物化
**When** 系统从 manifest/CAS 写入工作区文件
**Then** 系统先创建本次 checkout 私有临时物化目录
**And** 使用 copy-only 物化，不依赖 reflink/COW
**And** 不使用可变 `current` symlink 作为分支隔离边界
**And** 不通过 writable hardlink 或 symlink 暴露 CAS 对象。

**Given** 临时物化目录中的文件全部复制并校验完成
**When** 系统发布目标稳定目录
**Then** 系统以原子可见的方式登记该目录为 branch/version/generation 的稳定工作目录
**And** 在发布完成前不把半物化目录作为可 checkout 目标暴露给用户。

**Given** 目标目录物化或复用成功
**When** 系统记录工作目录元数据
**Then** 系统维护 owner、host、work root、flow workspace、branch、version、generation、target path 和物化时间
**And** 这些元数据可用于后续 commit、restore、audit 和诊断。

**Given** 安装了 shell 集成
**When** 用户执行 `big checkout <branch>`
**Then** checkout 完成后 shell 集成将父 shell 当前目录切换到目标稳定目录
**And** CLI summary 显示目标 branch、version ID、generation 和目标路径。

**Given** 未安装 shell 集成
**When** 用户执行 `big checkout <branch>`
**Then** BIG 仍完成目标目录解析或物化
**And** CLI 输出可复制执行的 `cd -- <target-path>`
**And** 输出清楚说明普通 CLI 子进程无法直接改变父 shell 的 cwd。

**Given** checkout 完成
**When** 用户在原目录中已有 EDA 进程仍在运行
**Then** BIG 不修改原目录中的任何文件
**And** 不改变该进程的 cwd、已打开文件描述符或绝对路径引用。

**Given** checkout 失败
**When** 失败原因是权限、manifest 缺失、CAS 对象缺失、目标目录写入失败或路径模板冲突
**Then** 系统输出明确错误原因
**And** 不留下半物化的可用分支目录；临时目录必须可清理或可诊断恢复。

**Given** 用户在 SSH 或窄终端环境中执行 checkout
**When** CLI 输出结果
**Then** 默认输出保持简洁，包含 branch、version、target path 和下一步操作
**And** `--verbose` 可以展示物化文件数、总大小、耗时和 generation 详情。

### Story 2.3：从历史版本创建新分支并 checkout 到稳定目录

作为工程师，
我想要执行 `big checkout <version> --new-branch <branch-name>`，从历史制品集版本创建一个新分支并进入对应的稳定真实目录，
以便我可以基于旧版本开展探索、修复或回退验证，而不会改写原分支目录或影响正在运行的 EDA 进程。

**Acceptance Criteria:**

**Given** 工程师位于已登记 work root 下的目录
**When** 执行 `big checkout <version> --new-branch <branch-name>`
**Then** 系统解析当前逻辑仓库、work root、用户和 flow workspace
**And** 将 `<version>` 解析为一个确定的历史制品集版本。

**Given** 用户没有该 version 的 read 权限，或没有创建新分支的权限
**When** 用户执行该命令
**Then** 系统拒绝操作
**And** 不泄露受保护 version 的 manifest、文件列表或物化路径。

**Given** `<branch-name>` 不合法、已存在或与保留名称冲突
**When** 用户创建新分支
**Then** 系统拒绝操作
**And** 不创建分支记录或目标工作目录。

**Given** 目标 version 可以被用户读取
**When** 系统创建新分支
**Then** 新分支指针指向该确定 version
**And** 新分支起点不随后续任何 source branch 的移动而变化。

**Given** 目标 version 可以从当前上下文或唯一可见 source branch 推导 ACL
**When** 系统创建新分支
**Then** 新分支默认继承 source branch ACL
**And** 如果 source branch 不明确，系统要求用户显式指定 ACL 模板或继承来源。

**Given** 新分支记录尚未对用户可见
**When** 系统准备 checkout 目标目录
**Then** 系统为新分支计算稳定真实 NAS 目录路径
**And** 目标目录必须是当前源目录的兄弟/独立目录，不得与源目录相同。

**Given** 目标 version 的 manifest 和 CAS 对象均可用
**When** 系统物化新分支目录
**Then** 系统从 manifest/CAS copy-only 到临时目录
**And** 校验完成后才发布为新分支的稳定工作目录
**And** 不使用可变 `current` symlink、reflink/COW 或 writable hardlink 暴露 CAS。

**Given** 新分支目录物化成功
**When** `bigd` 提交元数据事务
**Then** 系统在同一事务中创建 branch 记录、branch head、workspace generation 记录和 audit 事件
**And** 新分支在事务成功后才对 `big branch`、`big checkout` 和后续 commit 可见。

**Given** 物化目录失败、CAS 缺失或元数据事务失败
**When** 命令失败
**Then** 系统不得留下可见的新分支
**And** 临时目录必须可清理或可诊断恢复。

**Given** 安装了 shell 集成
**When** 命令成功
**Then** 父 shell 当前目录切换到新分支稳定目录。

**Given** 未安装 shell 集成
**When** 命令成功
**Then** CLI 输出可复制执行的 `cd -- <target-path>`。

**Given** 原目录中已有 EDA 进程仍在运行
**When** 新分支 checkout 完成
**Then** BIG 不修改原目录中的任何文件
**And** 不改变原进程的 cwd、已打开文件描述符或绝对路径引用。

### Story 2.4：显式部分物化制品集文件子集

作为工程师，
我想要在明确需要时只物化某个 branch 或 version 中的指定文件子集，
以便在百万文件级项目中查看、取用或验证少量历史输入、脚本、报告或局部输出，而不必为了这类局部用途全量复制整个制品集。

**Acceptance Criteria:**

**Given** 工程师执行普通 `big checkout <branch>` 或 `big checkout <version> --new-branch <name>`
**When** 命令中没有显式 include/exclude 选择规则
**Then** 系统按完整分支工作目录语义处理 checkout
**And** 不默认创建 partial workspace。

**Given** 工程师对目标 branch 或 version 有 read 权限
**When** 执行显式部分物化命令，例如 `big checkout <branch> --include <path-or-glob>`
**Then** 系统只从目标 manifest 中解析匹配的文件集合
**And** 目标 branch/version 仍解析为确定的 version ID
**And** 本次工作目录元数据标记为 `materialization = "partial"`。

**Given** 用户指定多个 include pattern
**When** 系统解析部分物化请求
**Then** 系统合并所有匹配文件并去重
**And** CLI summary 显示匹配文件数、总字节数和目标路径。

**Given** 用户指定 exclude pattern
**When** include 与 exclude 同时存在
**Then** 系统先应用 include，再应用 exclude
**And** CLI summary 显示被 exclude 排除的文件数。

**Given** include pattern 没有匹配任何文件
**When** 用户执行部分物化 checkout
**Then** 系统拒绝操作
**And** 输出未匹配 pattern，避免创建空的误导性工作目录。

**Given** 用户没有目标 branch/version 的 read 权限
**When** 用户执行部分物化 checkout
**Then** 系统拒绝操作
**And** 不泄露目标 manifest 中的文件清单、路径结构或匹配结果。

**Given** 部分物化目标目录尚未创建
**When** 系统从 manifest/CAS 写入文件
**Then** 系统只 copy 选中文件对应的 CAS 对象
**And** 保留文件在 manifest 中的相对路径结构
**And** 不通过 writable hardlink 或 symlink 暴露 CAS 对象。

**Given** 目标目录已经存在但选择集合不同
**When** 用户再次执行部分物化 checkout
**Then** 系统创建新的 workspace generation 或独立 materialization profile
**And** 不在已有目录中静默删除、覆盖或补齐文件。

**Given** 用户尝试在同一目标目录中混用 full checkout 和 partial checkout
**When** 系统检测到 materialization profile 不一致
**Then** 系统拒绝原地复用
**And** 提示用户使用新的 generation、显式 restore，或指定独立目标目录。

**Given** 部分物化 checkout 成功
**When** 系统记录工作目录元数据
**Then** 元数据记录 branch、version、generation、selection profile、include/exclude rules、文件数和总字节数
**And** 后续 BIG 操作可以识别该目录是部分物化目录。

**Given** 工程师在部分物化目录中执行后续 BIG 操作
**When** 该操作需要目标 version 中未物化的文件
**Then** 系统明确提示文件未物化
**And** 不把未物化解释为目标 version 中不存在。

**Given** 工程师在部分物化目录中执行 commit
**When** commit 未显式指定 inputs/outputs 或未显式确认 partial workspace 语义
**Then** 系统拒绝把该目录当作完整分支工作目录提交
**And** 提示用户显式指定要提交的 inputs/outputs 或切换到完整物化目录。

**Given** 部分物化过程中 CAS 对象缺失、文件复制失败或权限不足
**When** 命令失败
**Then** 系统不发布可用的目标目录
**And** 临时目录必须可清理或可诊断恢复。

**Given** 用户在 SSH 或窄终端环境中执行部分物化 checkout
**When** CLI 输出结果
**Then** 默认输出显示 version ID、目标路径、选中文件数、总字节数、`materialization = partial` 和下一步 `cd` 行为
**And** `--full` 可展开完整文件列表。

### Story 2.5：使用 reset 移动当前分支指针

作为拥有当前分支 write 权限的工程师或 PD Lead，
我想要执行 `big reset <version>` 将当前分支 head 指针移动到历史制品集版本，
以便团队可以把分支状态回退到已知稳定版本，而不创建语义混乱的逆向 commit，也不改写任何已经存在的工作目录。

**Acceptance Criteria:**

**Given** 用户位于 BIG 管理的稳定工作目录中
**When** 执行 `big reset <version>`
**Then** 系统解析当前逻辑仓库、work root、flow workspace 和当前 branch
**And** 将 `<version>` 解析为一个确定的历史制品集版本。

**Given** 用户对当前 branch 有 write 权限
**When** 执行 `big reset <version>`
**Then** 系统将当前 branch head 指针移动到指定 version
**And** 不创建新的制品集版本、manifest 或 CAS 对象
**And** 不改写当前工作目录、不执行 restore、不自动 checkout。

**Given** 用户没有当前 branch write 权限
**When** 用户尝试执行 `big reset <version>`
**Then** 系统拒绝操作
**And** 返回权限不足的确定性错误。

**Given** `<version>` 不存在、不可读或不属于用户可见历史
**When** 用户执行 reset
**Then** 系统拒绝操作
**And** 不泄露用户无权访问的 version 详情。

**Given** `<version>` 是当前 branch 历史链上的祖先版本
**When** 用户执行 reset
**Then** 系统允许移动 branch head
**And** 在事务中记录 old head、new head、操作者、时间和 reason/message。

**Given** `<version>` 不在当前 branch 历史链上
**When** 用户执行普通 reset
**Then** 系统默认拒绝操作
**And** 提示该操作属于跨血缘重指向，需要后续单独设计，不在 MVP 普通 rollback 范围内。

**Given** 当前 branch head 已经等于 `<version>`
**When** 用户执行 reset
**Then** 系统返回幂等成功或 no-op 提示
**And** 不重复写 audit 事件，除非用户显式要求记录。

**Given** reset 成功
**When** `bigd` 提交元数据事务
**Then** 该事务只更新当前 branch head 指针和 audit/hash-chain 事件
**And** 不改写任何 workspace generation、checkout 目录或源目录文件。

**Given** reset 成功后已有工程师仍在旧 generation 目录中运行 EDA
**When** 这些进程继续运行
**Then** BIG 不改变它们的 cwd、已打开文件描述符或绝对路径引用
**And** 新执行 `big checkout <branch>` 的用户会解析到 reset 后的新 head version。

**Given** 用户需要进入 reset 后的分支目录
**When** 用户随后执行 `big checkout <branch>`
**Then** 系统按 Story 2.2 解析或物化对应 new head version 的稳定目录
**And** `big reset <version>` 本身不隐式执行目录切换。

**Given** reset 失败
**When** 失败原因是权限、目标 version 无效、并发更新或元数据事务失败
**Then** 系统保持 old head 不变
**And** 输出明确错误原因和可操作建议。

**Given** 用户熟悉 Git reset
**When** 查看 `big reset --help`
**Then** 帮助必须明确说明 BIG MVP 的 reset 是 branch pointer reset only
**And** 不等同于 Git hard reset，不会改写工作目录文件。

### Story 2.6：显式原地 restore 当前工作目录

作为工程师，
我想要在明确确认后执行 `big restore --in-place <version>`，将当前稳定工作目录恢复到指定制品集版本的文件状态，
以便我可以在确实需要复用当前目录路径时受控改写文件，同时 BIG 能检测 dirty state、活动 lease，并通过 restore journal 支持失败诊断和恢复。

**Acceptance Criteria:**

**Given** 工程师位于 BIG 管理的稳定工作目录中
**When** 执行 `big restore --in-place <version>`
**Then** 系统解析当前逻辑仓库、work root、flow workspace、branch、workspace generation 和目标 version
**And** 该命令必须显式包含 `--in-place`，不得由 `checkout` 或 `reset` 隐式触发。

**Given** 用户没有当前 branch write 权限或目标 version read 权限
**When** 用户执行 restore
**Then** 系统拒绝操作
**And** 不泄露用户无权访问的 version manifest 或文件列表。

**Given** 当前工作目录存在 dirty state
**When** 用户执行 restore
**Then** 系统拒绝操作
**And** 输出 dirty 文件摘要、变化数量和建议处理方式。

**Given** 当前工作目录存在活动受管 lease
**When** 用户执行 restore
**Then** 系统拒绝操作
**And** 输出 lease owner、命令摘要和建议等待或终止受管流程。

**Given** 当前目录可能存在手工启动的 EDA 写入进程
**When** 用户执行 restore
**Then** CLI 必须提示 BIG 无法可靠自动发现所有外部写入进程
**And** 要求用户显式确认已停止相关写入或使用项目约定的 quiet-state 流程。

**Given** 用户确认继续 restore
**When** 系统准备改写当前目录
**Then** 系统先生成 restore plan
**And** plan 包含待新增、待覆盖、待删除或待保留文件数量、总字节数和目标 version ID。

**Given** restore plan 已生成
**When** 用户未使用强制确认选项
**Then** CLI 展示 plan 摘要并要求二次确认
**And** 默认选择为取消。

**Given** restore 开始执行
**When** 系统写入文件
**Then** 系统使用 copy-only 物化到同目录临时文件
**And** 校验临时文件内容后再逐文件替换目标路径
**And** 不使用 writable hardlink、symlink、reflink/COW 暴露 CAS。

**Given** restore 需要删除当前目录中目标 version 不存在的文件
**When** 系统执行删除阶段
**Then** 删除行为必须在 plan 中明确列出
**And** MVP 可以默认拒绝删除，除非用户显式启用删除选项。

**Given** restore 执行中断或失败
**When** 用户或系统查看恢复状态
**Then** `restore journal` 记录已完成、未完成和失败的文件操作
**And** 后续命令可以根据 journal 提示继续、回滚或人工处理。

**Given** restore 成功完成
**When** 系统更新工作目录元数据
**Then** 系统更新 workspace generation、restored_from version、restore timestamp 和操作者
**And** 记录 append-only audit 事件。

**Given** restore 成功完成
**When** CLI 输出 summary
**Then** 输出变化文件数、总字节数、目标 version、restore journal ID 和新的 generation
**And** 提醒用户重新打开文件或重启可能缓存旧内容的 EDA 工具。

**Given** restore 完成后用户继续在当前目录工作
**When** 后续执行 `big commit`
**Then** 系统可以识别该目录经历过 in-place restore
**And** commit provenance 中可记录 restore journal ID 和 restored_from version。

## Epic 3：版本历史、配方洞察与血缘追溯

工程师可以查看历史、配方详情、配方差异、回退语义、上游血缘、下游影响和基础跨分支依赖关系。

### Story 3.1：查看分支上的制品集版本历史

作为工程师，
我想要查看某个分支上的制品集版本历史，
以便我可以找到最近提交、定位历史版本 ID，并把 CLI 输出中的版本 ID 用于 checkout、reset、recipe 查看、diff 或 GUI 搜索。

**Acceptance Criteria:**

**Given** 工程师位于 BIG 管理的稳定工作目录中
**When** 执行 `big log`
**Then** 系统解析当前逻辑仓库、work root、用户、flow workspace 和当前 ref
**And** 如果用户未显式 checkout 命名 branch，则当前 ref 为该 workspace-private ref
**And** 按时间或拓扑顺序显示当前 ref head 可达的制品集版本历史，不混入其他用户或其他 flow workspace 的默认历史。

**Given** 工程师想查看指定分支历史
**When** 执行 `big log <branch>`
**Then** 系统显示该 branch 当前 head 可达的版本历史
**And** 不要求用户先 checkout 到该 branch。

**Given** 用户没有目标 branch read 权限
**When** 执行 `big log <branch>`
**Then** 系统拒绝查询
**And** 不泄露该分支的 version ID、manifest 摘要或提交信息。

**Given** 分支曾经执行过 `big reset <version>`
**When** 用户查看该分支历史
**Then** `big log` 默认显示 reset 后当前 head 可达的历史链
**And** reset 审计事件不伪装成制品集版本 commit。

**Given** 历史中存在大量版本
**When** 用户执行 `big log`
**Then** 默认输出分页或限制条数
**And** 支持 `--limit`、`--after` 或等价游标参数继续查看历史。

**Given** 仓库中至少存在 10 万个制品集版本历史记录
**When** 用户查看单个分支的最近历史
**Then** 查询必须使用索引或等价机制避免全仓扫描
**And** 默认查询在可接受时间内返回。

**Given** 单条版本历史记录被输出
**When** CLI 渲染该记录
**Then** 输出包含稳定 version ID、branch、提交时间、作者、step、制品集状态、resident/recipe_only 状态和简短 message
**And** version ID 与 GUI 实体 ID 保持一致。

**Given** 用户使用 `--verbose`
**When** CLI 输出历史
**Then** 每条记录可展开显示 parent version、recipe_hash、capture_mode、inputs/outputs 数量和 workspace generation 摘要。

**Given** 用户使用 `--full`
**When** CLI 输出历史
**Then** 可以进一步展示完整 manifest 摘要或文件列表入口
**And** 对大文件列表必须分页或提示使用更具体的 recipe/detail 命令。

**Given** 分支没有任何可见版本
**When** 用户执行 `big log <branch>`
**Then** 系统输出空历史提示
**And** 不返回错误，除非分支不存在或用户无权访问。

**Given** 用户在 SSH 或窄终端环境中查看历史
**When** CLI 输出结果
**Then** 默认输出保持紧凑可读
**And** 不依赖 GUI、X11 或交互式 TUI。

### Story 3.2：查看制品集版本的 manifest 与 recipe 详情

作为工程师，
我想要查看任意可访问制品集版本的 manifest、inputs、outputs 和 recipe 摘要，
以便我可以理解该版本由哪些文件产生、产出了哪些文件，并用文件 hash、recipe_hash 和 capture evidence 做追溯或问题定位。

**Acceptance Criteria:**

**Given** 用户拥有目标 version 的 read 权限
**When** 执行 `big show <version>`
**Then** 系统显示该 version 的基本信息
**And** 包含 version ID、branch、parent version、作者、提交时间、step、message、状态和驻留状态。

**Given** 目标 version 包含 manifest
**When** 用户查看详情
**Then** 系统显示 manifest 摘要
**And** 包含 inputs 数量、outputs 数量、总字节数、capture_mode、manifest hash 和 recipe_hash。

**Given** 用户使用默认输出
**When** CLI 渲染详情
**Then** 只展示摘要和关键 hash
**And** 不默认展开完整百万级文件列表。

**Given** 用户使用 `--verbose`
**When** CLI 渲染详情
**Then** 展示 inputs/outputs 的分类摘要、semantic_role、format_hint、文件大小分布和 capture evidence 摘要。

**Given** 用户使用 `--full`
**When** CLI 渲染详情
**Then** 展示完整 FileRef 列表或分页入口
**And** 每个 FileRef 包含 path、role、SHA-256、size、semantic_role 和 format_hint。

**Given** 脚本、配置或参数文件在当前 MVP 中仍作为 inputs 记录
**When** 系统展示 recipe 详情
**Then** 系统显示这些文件的 semantic_role/format_hint
**And** 不强行引入独立 params 角色；独立 params 分类留待后续需求细化。

**Given** 用户没有目标 version read 权限
**When** 执行 `big show <version>`
**Then** 系统拒绝查询
**And** 不泄露 manifest、文件路径、hash 或提交信息。

**Given** 目标 version 不存在或已不可访问
**When** 用户查看详情
**Then** 系统返回明确错误
**And** 区分 version 不存在、无权访问、manifest 缺失和 CAS/metadata 损坏。

**Given** 目标 version 的驻留状态为 `recipe_only`
**When** 用户查看详情
**Then** 系统仍可展示 recipe、manifest 和 FileRef hash
**And** 明确提示输出文件内容可能需要重新物化或重跑。

**Given** 实现阶段调整详情命令名称
**When** 命令从 `big show <version>` 调整为等价命令
**Then** CLI 帮助和 Story 验收仍必须覆盖 version 基本信息、manifest 摘要、FileRef 详情和权限边界。

### Story 3.3：对比两个制品集版本的 recipe 与 manifest 差异

作为工程师，
我想要对比两个制品集版本的 inputs、outputs、recipe_hash 和 manifest 摘要差异，
以便我可以快速判断一次 EDA 结果变化是由输入变化、输出变化、step/recipe 变化，还是仅由驻留状态或元数据变化引起。

**Acceptance Criteria:**

**Given** 用户拥有两个目标 version 的 read 权限
**When** 执行 `big diff <old-version> <new-version>`
**Then** 系统对比两个 version 的 manifest 和 recipe 摘要
**And** 默认输出 CLI unified diff 风格的摘要结果。

**Given** 任一目标 version 不存在或用户无权访问
**When** 用户执行 diff
**Then** 系统拒绝查询
**And** 不泄露无权访问 version 的 manifest、文件路径、hash 或提交信息。

**Given** 两个 version 的 recipe_hash 相同
**When** 系统渲染 diff
**Then** 输出明确显示 recipe_hash unchanged
**And** 继续展示 outputs 是否发生变化。

**Given** 两个 version 的 recipe_hash 不同
**When** 系统渲染 diff
**Then** 输出显示 recipe_hash changed
**And** 展示导致 recipe 差异的 inputs 文件身份变化摘要。

**Given** inputs 文件集合发生变化
**When** 系统对比 FileRef
**Then** diff 显示新增、删除和内容 hash 改变的 input 路径数量
**And** `--verbose` 展示这些路径的摘要列表。

**Given** outputs 文件集合发生变化
**When** 系统对比 FileRef
**Then** diff 显示新增、删除和内容 hash 改变的 output 路径数量
**And** 默认不展开百万级完整列表。

**Given** 某个路径在两个 version 中都存在但 SHA-256 不同
**When** 系统输出 diff
**Then** 显示该路径为 modified
**And** 展示 old hash、new hash、old size、new size 的短摘要。

**Given** 某个路径只在 new version 中存在
**When** 系统输出 diff
**Then** 显示该路径为 added。

**Given** 某个路径只在 old version 中存在
**When** 系统输出 diff
**Then** 显示该路径为 removed。

**Given** 用户使用 `--full`
**When** CLI 输出 diff
**Then** 可以展开完整 changed FileRef 列表
**And** 对超大列表必须分页或提示导出到文件。

**Given** 两个 version 的文件内容相同但生命周期状态或驻留状态不同
**When** 系统输出 diff
**Then** 将状态差异与 recipe/manifest 文件差异分开显示
**And** 不把驻留状态变化误判为 recipe 变化。

**Given** 两个 version 属于不同 branch
**When** 用户执行 diff
**Then** 系统允许跨分支 diff
**And** 输出显示 old branch/new branch，帮助用户理解差异来源。

**Given** 用户在 SSH 或窄终端环境中查看 diff
**When** CLI 输出结果
**Then** 输出保持可读，不依赖 GUI
**And** 使用 `--verbose` / `--full` 渐进披露更大差异。

### Story 3.4：记录 derived_from 与逆向上游血缘链

作为工程师，
我想要从任意制品集版本逆向追溯其 parent、derived_from 和 consumes 上游关系，
以便我可以理解一个版本来自哪个历史版本、是否由回退后重新生成，以及它消费了哪些跨分支上游制品。

**Acceptance Criteria:**

**Given** 系统创建新的制品集版本
**When** 新版本由普通 commit 产生
**Then** 系统记录 `version_parent` 关系，指向当前 branch 的上一 head version
**And** 该关系表达版本祖先关系，不等同于数据依赖关系。

**Given** 用户从历史 version 创建新分支并重新 commit
**When** 新版本语义上来自该历史 version
**Then** 系统可以记录 `derived_from` 关系
**And** `derived_from` 不替代当前 branch 上的 parent 关系。

**Given** 某个版本消费了另一个 branch 或 version 的输出作为 input
**When** 用户在 commit 时声明或系统从 manifest/provenance 解析该关系
**Then** 系统记录 `provenance_edge`，类型为 `consumes`
**And** 可以表达跨分支上游制品依赖。

**Given** 用户执行 `big lineage <version>`
**When** 系统查询逆向血缘
**Then** 输出该 version 的 parent 链、derived_from 边和 consumes 上游边
**And** 默认以递归 tree 形式展示。

**Given** lineage 中包含用户无权读取的上游 version
**When** 系统输出血缘结果
**Then** 系统隐藏无权访问 version 的详细信息
**And** 可以显示受限占位符，避免破坏 tree 结构。

**Given** lineage 链很长
**When** 用户执行默认查询
**Then** 系统限制默认深度
**And** 支持 `--depth` 或等价参数扩大查询范围。

**Given** 仓库中至少有 1 万个制品集版本
**When** 用户查询单个 version 的逆向血缘链
**Then** 查询必须在 30 秒内完成
**And** 使用索引或等价结构避免全仓扫描。

**Given** 用户使用 `--verbose`
**When** 系统输出 lineage
**Then** 每个节点显示 version ID、branch、step、作者、时间、recipe_hash、状态和边类型。

**Given** 用户使用 `--full`
**When** 系统输出 lineage
**Then** 可以展开每条边的 evidence，例如 consumes 的 FileRef、路径、hash 和 manifest 引用。

**Given** lineage 中同时存在 parent 与 consumes 边
**When** 系统渲染结果
**Then** 必须清楚区分版本祖先关系与数据依赖关系
**And** 不把跨分支数据依赖误显示为 commit parent。

**Given** 用户在 SSH 或窄终端环境中查看 lineage
**When** CLI 输出结果
**Then** tree 输出保持可读
**And** 不依赖 GUI；Growth GUI 可在后续以 DAG 形式增强。

### Story 3.5：查看血缘链上每个节点引入的 recipe 变化

作为工程师，
我想要在查看血缘链时看到每个版本节点相对于父节点引入的 recipe/input 变化摘要，
以便我可以快速定位是哪一次提交改变了脚本、配置、输入文件或其他影响 recipe_hash 的内容。

**Acceptance Criteria:**

**Given** 用户拥有目标 version 及其可见上游节点的 read 权限
**When** 执行 `big lineage <version> --changes`
**Then** 系统在血缘 tree 中为每个可见节点显示相对于 parent 的变化摘要
**And** 默认只显示变化数量和关键摘要，不展开完整文件列表。

**Given** 某个节点的 recipe_hash 相比 parent 未变化
**When** 系统渲染该节点
**Then** 输出显示 recipe unchanged
**And** 不把 outputs 或驻留状态变化误报为 recipe 变化。

**Given** 某个节点的 recipe_hash 相比 parent 发生变化
**When** 系统渲染该节点
**Then** 输出显示 recipe changed
**And** 展示 inputs 中 added、removed、modified 的数量。

**Given** 改变的 input 文件包含脚本、配置、runset、SDC 或类似文本类可编辑文件
**When** 系统已有 semantic_role/format_hint
**Then** 输出优先突出这些高影响文件
**And** 不要求 MVP 对文件内容做文本级 diff。

**Given** 用户使用 `--verbose`
**When** 系统输出变化摘要
**Then** 展示每个节点 changed inputs 的路径摘要、旧 hash、新 hash、文件大小变化和 semantic_role。

**Given** 用户使用 `--full`
**When** 系统输出变化详情
**Then** 可以展开所有 changed FileRef
**And** 对超大列表必须分页或提示导出。

**Given** 某个上游节点因权限不可见
**When** 系统计算变化摘要
**Then** 不展示该节点的变化细节
**And** 显示受限占位符，避免泄露路径或 hash。

**Given** lineage 中存在 `derived_from` 或 `consumes` 边
**When** 系统显示变化摘要
**Then** 对 parent 边和 consumes 边分别计算或标注变化含义
**And** 不把跨分支 consumes 输入变化误解释为同一 branch 的 commit 修改。

**Given** 后续引入独立 params 角色
**When** 系统展示 `--changes`
**Then** params 变化应作为 recipe 变化的独立分组展示
**And** 不破坏 MVP 已有 inputs 变化展示。

### Story 3.6：正向追溯下游影响范围

作为工程师，
我想要从任意制品集版本正向查看哪些下游版本依赖它，
以便当上游版本发生变更、回退或淘汰时，我可以识别可能受影响的下游 flow、branch 或制品集版本。

**Acceptance Criteria:**

**Given** 用户拥有目标 version 的 read 权限
**When** 执行 `big impact <version>`
**Then** 系统查询以该 version 为上游的 `provenance_edge(consumes)` 反向关系
**And** 输出直接依赖该 version 的下游版本列表。

**Given** 用户使用默认查询
**When** 系统输出 impact 结果
**Then** 默认只显示一层直接下游影响
**And** 包含下游 version ID、branch、step、作者、时间、状态和依赖边类型。

**Given** 用户使用 `--depth <n>`
**When** 系统查询下游影响
**Then** 系统递归展开 n 层下游依赖
**And** 防止环或重复节点导致无限遍历。

**Given** 某个下游 version 用户无权读取
**When** 系统输出影响范围
**Then** 隐藏该 version 的详细信息
**And** 可以显示受限占位符和受影响计数。

**Given** 下游依赖来自跨分支 consumes 边
**When** 系统输出结果
**Then** 输出必须显示上游 branch 与下游 branch
**And** 不把跨分支数据依赖误解释为 commit parent。

**Given** 用户使用 `--verbose`
**When** 系统输出 impact 结果
**Then** 每条依赖边展示 evidence 摘要，例如依赖的 FileRef、路径、hash 和 manifest 引用。

**Given** 用户使用 `--full`
**When** 系统输出 impact 结果
**Then** 可以展开完整下游树或 DAG 摘要
**And** 对大型影响范围必须分页或支持导出。

**Given** 上游 version 没有任何可见下游依赖
**When** 用户执行 `big impact <version>`
**Then** 系统输出 no visible downstream impact
**And** 不把无权限节点误报为无影响。

**Given** 仓库中存在大量版本和跨分支依赖
**When** 用户查询单个 version 的影响范围
**Then** 查询必须使用索引或等价结构避免全仓扫描
**And** 默认直接下游查询在可接受时间内返回。

**Given** Growth GUI 后续实现影响分析视图
**When** 使用同一公共 API 查询 impact
**Then** GUI 与 CLI 必须共享同一权限过滤、节点 ID 和依赖边语义
**And** 不引入 GUI 专用影响分析逻辑。
