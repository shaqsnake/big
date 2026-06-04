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
**And** 物理目录名 `APR/SYN/PV/STA/PI` 不被默认解释为 branch，branch/version 由 BIG 元数据单独记录。

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
**And** 该版本记录 step 名称、work root、flow workspace、用户、提交时间和 commit message。

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
