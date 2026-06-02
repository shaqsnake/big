---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-05-domain, step-06-innovation, step-07-project-type, step-08-scoping, step-09-functional, step-10-nonfunctional, step-11-polish, step-e-01-discovery, step-e-02-review, step-e-03-edit]
releaseMode: phased
lastEdited: '2026-06-02'
editHistory:
  - date: '2026-06-02'
    changes: 'EDA进程隔离、元数据与GUI解耦修订：每分支稳定真实目录、checkout进入兄弟目录、显式原地restore、MetadataRepository可替换adapter、Candidate事务outbox交付、公共API/OpenAPI/事件契约支持定制GUI'
  - date: '2026-06-02'
    changes: '外部架构评审与生产NAS澄清修订：用户私有分支目录、CAS只读不可变、copy-only增量checkout、commit一致快照、bigd单写元数据服务、review_state与retention_state分离、recipe_hash与action_hash分离、Golden耐久性目标可验证化'
  - date: '2026-05-28'
    changes: '新增3DIC多流程版本管理和DSO存储优化场景：Executive Summary补充两个场景描述、Success Criteria新增2条、Product Scope调整Growth/Vision、新增Journey 5(3DIC)和Journey 6(DSO)、Domain Requirements新增两个子章节、Innovation新增第5点PPA排名淘汰、FR34-FR39(6个新需求)、DSO集成入口、NFR21、Scoping阶段调整'
  - date: '2026-05-26'
    changes: '基于PRD验证报告全面修正：NFR扩展四列模板补充测量方法(20条)、FR格式修正(5条)、FR18重分类到NFR3、FR阶段标签MVP/Growth(32条)、FR33旅程追溯补全、成功标准旅程支撑补全、代码示例章节新增、迁移指南实操扩充'
inputDocuments:
  - '_bmad-output/brainstorming/brainstorming-session-2026-05-17-121344.md'
  - '_bmad-output/planning-artifacts/research-technical-architecture.md'
workflowType: 'prd'
classification:
  projectType: '开发者工具（CLI + GUI/Electron+Web）'
  domain: '半导体/EDA'
  complexity: '高'
  projectContext: '混合（系统绿地开发，部署在棕地环境——需适配现有NAS基础设施、EDA工具链和团队工作习惯）'
---

# 产品需求文档 - BIG

**作者:** shaqsnake
**日期:** 2026-05-20

## Executive Summary

芯片数字后端设计（特别是3DIC等复杂流程）面临日益严峻的版本管理和协作挑战：一个项目每天产生TB级新数据，工程师靠手动命名规则管理版本，追溯问题版本至少需要半天时间，团队交付依赖人工规范而非系统保障。现有工具无法解决——Git LFS的整文件存储无法应对EDA文件的量级和增量修改，Perforce虽可行但无法采购商业许可。特别是3DIC等先进封装方向，一个设计被拆分为多个并行的die流程，流程间存在复杂的交叉依赖——top die的物理设计输出成为bottom die的输入，2D网表需要跨流程联合迭代调时序——这些跨流程的版本关系正是BIG血缘管理的核心价值场景。

BIG是一个面向芯片设计的大文件版本管理与团队协作系统，旨在让工程师从手动版本管理的混乱中解放出来，通过制品集血缘图实现秒级问题追溯，通过流水线实现规范化交付，支撑越来越复杂的芯片设计项目的迭代和交付。在自动寻优（DSO）场景下，一个模块需并行探索100+组APR参数组合以寻找最优PPA，产生的海量Innovus DB可达100T级别，频繁因磁盘空间耗尽导致寻优失败。BIG通过分层存储和智能淘汰机制，可自动保留较优设计DB、回收劣序DB空间，与DSO系统无缝对接解决存储膨胀痛点。系统采用CLI为核心交互方式，以公共API作为集成边界；可选Electron+Web参考GUI用于版本树/图可视化和版本挑选操作，其他系统也可提供定制GUI。BIG需部署在现有NAS基础设施上，兼容EDA工具链，最小化工程师的学习成本和工作方式变更。

### What Makes This Special

BIG的核心洞察是：**芯片设计的版本管理对象不是文件，而是设计决策历史。** 基于此洞察，BIG重点整合四类能力：制品集+文件双中心模型、CAS块级去重存储、完整action hash缓存Key、流水线驱动交付。详见 Innovation & Novel Patterns 章节。

## Project Classification

- **项目类型：** 开发者工具（CLI + GUI/Electron+Web）
- **领域：** 半导体/EDA（数字后端设计）
- **复杂度：** 高 — 领域专业性强、TB级数据管理、版本图有环等非标准需求、I/O性能硬约束、类似aerospace的tapeout不可逆验证要求
- **项目上下文：** 混合 — 系统绿地开发，部署在棕地环境（需适配现有NAS基础设施、EDA工具链和团队工作习惯，设计约束来自环境而非旧代码）

## Success Criteria

### User Success

1. **血缘追溯效率**：工程师定位一个产出物的完整决策链耗时 < 30秒（当前半天以上）
2. **输入校验保障**：commit时自动检测输入文件完整性，漏文件/错文件检出率 > 99%
3. **流水线零遗漏**：流水线触发后所有步骤自动串行执行完成，无需人工干预中间环节
4. **跨流程版本追踪**：3DIC设计场景下，工程师可以追踪跨die流程的版本依赖关系（如top die LEF变更影响哪些bottom die设计版本），完整追踪链耗时 < 1分钟

### Business Success

1. **存储空间节省**：相比当前手动命名管理方式，存储空间节省 > 80%（基于CAS块级去重 + 分层存储策略）
2. **交付周期缩短**：项目交付周期缩短 > 30%（来源于流水线标准化、追溯效率提升、减少人为错误返工）
3. **团队采纳率**：上线6个月内，团队 > 90% 的工程师日常使用BIG进行版本管理
4. **人为错误减少**：因选错文件或版本混乱导致的返工减少 > 70%
5. **DSO存储优化**：对接DSO系统后，自动寻优存储空间节省 > 90%（自动淘汰劣序DB），寻优过程因磁盘不足导致的失败率降为0

### Technical Success

1. **I/O性能**：通过BIG读写文件的吞吐量不低于NAS直读的70%
2. **存储可靠性**：Golden阶段达到可验证的耐久性目标，整体数据丢失率 < 0.01%；上线前明确 RPO/RTO、故障域隔离、副本校验和恢复演练
3. **可扩展性**：单项目支持百万级文件、PB级数据量
4. **兼容性**：兼容主流NAS文件系统，无缝对接EDA工具链（工具无需感知BIG的存在）

### Measurable Outcomes

| 指标 | 当前基线 | 目标 | 备注 |
|------|---------|------|------|
| 问题版本追溯耗时 | ≥ 半天 | < 30秒 | |
| 存储空间占用 | 100%（基线） | MVP: < 50%; Growth: < 20% | Growth目标依赖CAS+FastCDC |
| 交付周期 | 100%（基线） | < 70% | Growth阶段，依赖流水线 |
| 版本混乱导致返工 | 100%（基线） | < 30% | |
| I/O吞吐量 vs NAS直读 | 100% | ≥ 70% | |
| DSO寻优存储空间 | 100%（基线，100+/模块） | < 10% | Growth阶段，依赖淘汰策略引擎 |
| DSO寻优磁盘不足失败率 | 频繁发生 | 0 | Growth阶段 |

## Product Scope

### MVP - Minimum Viable Product

核心版本管理能力，证明概念可行：

- CLI核心：init、commit、checkout、log、branch基础命令
- 文件级CAS存储引擎（Growth阶段引入FastCDC块级去重）
- 制品集+文件双中心数据模型
- 分层存储（Exploring→Candidate→Pinned→Golden）
- NAS原生部署 + 用户私有稳定分支目录（`/data/<project>/user/<username>/<branch>/`）
- 低版本NAS兼容：新分支目录与显式原地restore仅使用普通copy物化，不依赖reflink/COW
- 单机`bigd`元数据服务 + 公共`/api/v1`（SQLite仅为服务端本地可替换adapter，NAS不共享数据库文件）
- 不可变只读CAS + commit一致快照发布
- 基础血缘追溯（命令行查询）
- 文件完整性校验（commit时自动检测）

### Growth Features (Post-MVP)

流水线与协作能力，提升竞争力：

- 流水线定义与执行引擎
- 验证门禁Agent（自动跑LVS/DRC）
- PPA指标与制品集版本绑定
- 影响分析（正向追溯）
- 基线快照
- GUI基础版（Electron+Web，版本树可视化、版本挑选）
- Candidate事件驱动交付（不可变manifest/CAS → staging → 版本化统一发布目录）
- OpenAPI与事件契约，支持外部系统和定制GUI对接

### Vision (Future)

完善生态与体验：

- GUI高级版（血缘图可视化、流水线监控仪表盘）
- 3DIC全流程版本图谱可视化（跨die血缘图、流程间联动关系呈现）
- 多站点分布式部署（类Commit-Edge架构）
- 完整action hash缓存Key（安全匹配已有输出，避免重复计算）
- Delta传输优化（远程同步场景）
- 与交付制品系统集成
- 插件生态（支持自定义工具链、验证步骤）

## User Journeys

### Journey 1: 工程师的日常探索 — 从混沌到有序

**角色：** 李明，数字后端工程师，5年经验

李明每天的工作是在宏大的设计空间中寻找最优解。今天是3DIC项目floorplan阶段的关键一天——他需要尝试三种不同的布局策略，对比它们的PPA结果。

过去，李明会在NAS上创建三个目录：`fp_v1_baseline`、`fp_v2_channel_routing`、`fp_v3_shared_power`，然后在每个目录里分别跑工具。但目录里文件杂乱，两天后他自己都记不清哪个目录用了什么参数，哪个结果对应哪个输入。更糟的是，一旦某个结果看起来有问题，他根本无法确认当时是否选错了输入文件。每次追溯问题版本，他都要花至少半天翻目录、问同事——这种痛苦正是团队愿意迁移到BIG的根本原因。

今天，一切不同了。

```bash
# 在BIG管理的项目分支上工作
big checkout feature/fp-exploration

# 第一次尝试：baseline布局
# ... 跑EDA工具，产出def/gds文件 ...
big commit -m "baseline floorplan" --inputs "rtl/*.v, sdc/*.sdc" \
  --params "place_density=0.6, util=0.7" --outputs "out/*.def, out/*.gds"
# → 系统自动校验输入文件完整性，记录配方，生成制品集 v1

# 第二次尝试：channel routing策略
# ... 修改参数，重新跑工具 ...
big commit -m "channel routing floorplan" --inputs "rtl/*.v, sdc/*.sdc" \
  --params "place_density=0.55, util=0.65, channel_width=2um" --outputs "out/*.def, out/*.gds"
# → 系统检测到相同的输入文件哈希，配方不同，生成制品集 v2

# 第三次尝试：shared power策略
# ... 再次修改 ...
big commit -m "shared power floorplan" --inputs "rtl/*.v, sdc/*.sdc" \
  --params "place_density=0.6, util=0.7, power_shared=true" --outputs "out/*.def, out/*.gds"
# → 制品集 v3，当前处于Exploring状态

# 查看三次探索的对比
big log --oneline --branch feature/fp-exploration
# v3 | shared power floorplan | Exploring
# v2 | channel routing floorplan | Exploring
# v1 | baseline floorplan | Exploring
```

**情感转折：** 李明不再焦虑地检查目录名和备注文件——每一个版本都有完整的输入、参数、输出记录。他可以随时回到任何一个探索节点，精确复现当时的状态。三个布局策略的对比不再是猜测游戏，而是有据可查的设计决策历史。更让他惊喜的是，当项目后期文件数增长到百万级别时，他可以用 `big checkout --subset` 只加载当前需要的输出文件，而不必等待全量checkout——BIG在大规模场景下同样高效。

**揭示的能力需求：**
- 制品集commit与配方记录
- 输入文件完整性自动校验
- Exploring状态的轻量存储
- 分支上的版本历史浏览
- 大规模项目的选择性checkout

---

### Journey 2: 问题追溯与回退 — 从半天到30秒

**角色：** 王磊，数字后端工程师，3年经验

3DIC项目的综合阶段出了问题：signoff时序分析报告显示，有一条关键路径的setup slack为负值。王磊需要找出是哪一次变更引入了这个时序违例。

在过去，这是噩梦般的半天工作：他需要翻阅多个目录，对照命名规则猜测文件的先后关系，打开工具逐个检查参数，运气不好的话还要去问同事"这个版本你用了什么输入？"——而同事可能也记不清了。

现在，王磊只需要：

```bash
# 从问题制品集出发，查看完整血缘链
big log --lineage signoff_v5
# signoff_v5 [Golden candidate]
#   ← route_v8 [Pinned] (路由结果)
#     ← place_v12 [Pinned] (布局结果)
#       ← fp_v3 [Candidate] (floorplan，shared power策略)
#         ← synth_v2 [Candidate] (综合结果)
#           ← rtl_v7 [Pinned] (RTL提交)
# 参数变更链：
#   fp_v3: power_shared=true ← 这是唯一引入power_shared参数的版本

# 30秒内，王磊锁定了问题源头：fp_v3的shared power策略导致了时序收敛困难
# 他决定回退到floorplan阶段重新做布局

# 回退到fp_v2（channel routing策略），从那里重新出发
big checkout fp_v2 --new-branch timing-from-fp-v2
# 在fp_v2的基础上重新做floorplan探索
# ... 调整布局参数，重新跑工具 ...
big commit -m "revised floorplan based on channel routing" \
  --inputs "rtl/*.v, sdc/*.sdc" \
  --params "place_density=0.55, util=0.65, channel_width=2.5um" \
  --outputs "out/*.def, out/*.gds"
# → 生成新的制品集，分支指针回退到fp_v2后新生成，derived_from语义边记录此决策
```

**情感转折：** 王磊从绝望的搜索变成冷静的导航。血缘图让问题的根源无所遁形，回退操作像时间旅行一样自然。下游发现问题、回到上游重新决策——这正是芯片设计的真实流程，BIG通过derived_from语义边完整记录这一决策链。在追溯过程中，即使涉及多个子模块的PT DB文件同时读取（单个文件数十GB），BIG的文件级CAS直读机制保证了I/O性能接近NAS直读，不会因为版本管理而拖慢分析速度。

**揭示的能力需求：**
- 血缘链双向追溯（正向/逆向）
- 版本图的环形结构支持（derived_from分支指针回退+语义边）
- 基于历史版本的checkout与分支
- 制品集参数对比与差异展示

---

### Journey 3: PD Lead的交付把控 — 流水线驱动的规范化

**角色：** 张薇，PD Lead（Committer），10年经验

张薇负责3DIC项目的交付节奏。她的痛点不是技术难点，而是人为失误：上次tapeout前夕，团队交付的GDS文件竟然混用了两个不同版本的DEF，导致LVS验证失败，整个后端团队加班三天才修复。根因是工程师手动拷贝文件时选错了输入版本。

今天，前端团队提交了新的RTL版本，需要走完整的流水线交付到后端。

```bash
# 前端工程师提交RTL
big commit -m "RTL v8: fix timing violation on path A" \
  --inputs "*.v" --outputs "*.v"
# → rtl_v8 生成，自动标记为 Pinned

# 张薇触发交付流水线
big pipeline run rtl-to-backend --from rtl_v8
# 流水线自动执行：
# [1/6] ✅ RTL完整性校验（清单核对，无遗漏文件）
# [2/6] ⏳ 综合执行中...（约4小时）
#        → synth_v8 生成，配方 hash(rtl_v8 + 综合参数) 自动记录
#        → 检测到配方匹配历史输出 synth_v5，跳过综合！节省4小时
# [3/6] ⏳ LVS验证执行中...
#        → 调用验证工具，自动使用 synth_v8 的输出
#        → LVS clean ✅
# [4/6] ✅ 前端出口检查（时序、面积、功耗指标采集）
# [5/6] ✅ 后端入口检查（DEF一致性、约束文件完整性）
# [6/6] ✅ 发布到交付制品系统

# 流水线完成通知
big pipeline status rtl-to-backend
# Pipeline rtl-to-backend: COMPLETED (6/6)
# Released: deliverable_v3 [Golden]
```

**情感转折：** 张薇不再需要逐一检查每个工程师的工作——流水线替代了她的"人肉检查"。每一步都是系统强制执行，不会遗漏不会跳过。配方匹配更是意外之喜：相同的RTL+参数组合直接复用已有输出，4小时的综合时间瞬间节省。交付不再是一场紧张的考试，而是一条清晰的流水线。

**揭示的能力需求：**
- 流水线定义与编排（步骤、前后依赖）
- 流水线触发与自动串行执行
- 验证门禁（LVS/DRC自动调用）
- 完整action hash缓存Key（检测已有输出复用）
- 指标采集与版本绑定
- 阶段晋升（Pinned → Golden）
- 与外部交付制品系统集成

---

### Journey 4: IT管理员的系统运维 — 部署与监控

**角色：** 陈浩，IT基础设施工程师

陈浩负责为公司搭建BIG的运行环境。他的主要关注点是：BIG必须跑在现有NAS上，不能要求特殊的存储系统；工程师的学习成本要低，最好感觉不到BIG的存在。

```bash
# 在NAS共享目录上初始化BIG版本仓库
big repo init /nas/projects/3dic-project-2026
# → 创建 .big/ 元数据目录
# → 初始化CAS存储池（指向NAS路径）
# → 生成默认配置文件 .big/config.toml

# 配置分层存储策略
big repo config set storage.golden.replicas 2
big repo config set storage.golden.paths ["/nas/golden-backup-1", "/nas/golden-backup-2"]

# 创建团队分支
big branch create feature/fp-exploration --owner liming
big branch create feature/pd-delivery --owner zhangwei

# 监控存储使用
big repo stats
# Storage: 2.3TB used / 12TB available (19%)
# CAS chunks: 1,247,832 | Dedup ratio: 8.7x
# Exploring: 894 artifact sets (0.3TB recipes only)
# Candidate: 127 artifact sets (1.8TB)
# Pinned: 43 artifact sets (0.2TB)
# Golden: 12 artifact sets (0.0TB, replicated to 2 locations)

# GC回收被淘汰分支的存储
big repo gc --dry-run
# Would reclaim: 340GB from 2,156 orphaned chunks
big repo gc
# Reclaimed: 340GB
```

**情感转折：** 陈浩最担心的是BIG会不会搞坏NAS、会不会让存储爆掉。但看到CAS去重比率达到8.7倍，以及Exploring版本只存配方占用极小空间，他的担忧消散了。Golden数据的双副本冗余也让他对数据安全有信心。BIG不是一个需要特殊照料的系统，而是一个在现有基础设施上安静运行的好公民。

**揭示的能力需求：**
- NAS原生部署（无特殊存储要求）
- 分层存储策略配置
- 存储统计与监控
- CAS块级去重与GC回收
- Golden数据冗余备份
- 分支管理与权限

### Journey 5: 3DIC PD Lead的跨流程把控

**角色：** 张磊，3DIC PD Lead，8年经验

张磊负责的3DIC项目进入了最复杂的阶段——芯片被切成top die、bottom die和3D环节，拆出2D网表后，四个设计流程并行展开：2D综合、top die APR、bottom die APR和3D集成。流程之间盘根错节的交叉依赖让他焦头烂额——top die跑完floorplan要输出LEF给bottom die读取，2D网表一旦迭代就要通知top/bottom重新跑，3D集成更是依赖top+bottom全部完成才能启动。任何一步版本对不上，上下游就要全部重来，而他用文件夹命名和邮件通知来协调这一切——每次版本变更都是一场全流程的"人肉同步"。

今天，他打开了BIG。

```bash
# 为3DIC项目创建四个并行分支
big branch create 3dic/2d-synthesis --owner zhangsan
big branch create 3dic/top-die-apr --owner lisi
big branch create 3dic/bottom-die-apr --owner wangwu
big branch create 3dic/3d-integration --owner zhanglei

# top die APR完成，输出LEF
big commit -m "top die floorplan v3, LEF ready" \
  --outputs "top_die/lef/*.lef" --branch 3dic/top-die-apr

# 在血缘图中查看跨分支依赖
big lineage trace --cross-branch \
  --from 3dic/top-die-apr:v3 --artifact "top_die/lef/top.lef"
# → 下游依赖: 3dic/bottom-die-apr:v5 (读取top LEF做联合物理设计)
# → 下游依赖: 3dic/3d-integration:v1 (依赖top+bottom完成)

# 2D网表迭代，自动预警受影响的下游
big commit -m "2D netlist timing fix v7" \
  --outputs "2d/netlist/*.v" --branch 3dic/2d-synthesis
# → 系统预警: 此变更影响 3dic/top-die-apr (需重新APR)
# → 系统预警: 此变更影响 3dic/bottom-die-apr (需重新APR)

# 声明跨流程依赖关系
big depend declare --from 3dic/top-die-apr:v3:top_die/lef/top.lef \
  --to 3dic/bottom-die-apr:v5  --type "cross-flow-input"
big depend declare --from 3dic/2d-synthesis:v7:2d/netlist/design.v \
  --to 3dic/top-die-apr --type "cross-flow-input"
```

**情感转折：** 张磊再也不用逐一邮件确认上下游版本是否对齐了。血缘图跨分支链接让他一眼看清四个流程的依赖全貌——哪个LEF版本被哪些下游流程依赖，哪个网表变更会影响哪些APR流程，全都自动呈现。当2D网表迭代时，系统自动标记受影响的top die和bottom die分支版本，他只需点开预警列表就知道接下来要做什么。BIG让他从一个疲于奔命的"版本调度员"变回了真正的设计负责人。

**揭示的能力需求：**
- 跨分支血缘追踪（一个分支的输出是另一个分支的输入）
- 跨流程依赖声明
- 变更影响自动预警（跨分支版本标记）

### Journey 6: DSO工程师的存储管控

**角色：** 刘洋，设计空间寻优工程师，3年经验

刘洋的日常工作是用DSO系统为每个模块并行探索100+组APR参数组合，寻找最优PPA。但这份工作有一个让人窒息的副产品——存储膨胀。每组APR case产生一个Innovus DB，动辄数GB到数十GB，一个模块100+组就是TB级开销，多模块同时寻优磁盘轻松突破100T。更糟糕的是，寻优跑到一半磁盘满了，整个任务直接崩溃，之前跑完的成果也白白浪费。他试过手动删除排名靠后的DB，但删的时候总怕删错，而且下一个模块又要开始跑了——存储永远不够用。

今天，DSO系统对接了BIG。

```bash
# DSO系统通过BIG Python API自动提交每个APR case
import big

for case_id, result in dso_runner.run(module="cpu_core", num_cases=120):
    # 每个case自动成为BIG制品集版本
    big.commit(
        message=f"DSO case {case_id}",
        inputs=result.inputs,
        params=result.params,
        outputs=result.outputs,
        metadata={"ppa_score": result.ppa_weighted_score},  # DSO计算的PPA加权得分
        group=f"dso/cpu_core/run_20260528"  # 寻优分组
    )

# 查看本轮寻优的分组概览
big group list dso/cpu_core/run_20260528
# Group: dso/cpu_core/run_20260528
# Cases: 120 | Total size: 4.2TB
# PPA Top-5: case_087(92.1), case_043(91.8), case_112(91.5), ...
# Eviction candidate: 98 cases (ranked below Top-10)

# 配置PPA排名淘汰策略（保留Top-10完整DB，其余降级）
big policy set dso-eviction \
  --type ppa-rank \
  --keep-top 10 \
  --metric ppa_weighted_score \
  --group "dso/*"

# 配置存储水位线
big policy set storage-watermark \
  --high-threshold 85% \
  --action trigger-eviction

# 存储水位触达阈值后自动执行淘汰
# → 98个劣序case降级为Exploring（只保留配方+PPA指标），回收3.8TB空间
# → Top-10的完整Design DB保留，随时可checkout复用

big group stats dso/cpu_core/run_20260528
# Total: 120 cases | Size: 0.4TB (after eviction, saved 90.5%)
# Top-10 intact: ✓ | Others: Exploring (recipe + PPA score only)
```

**情感转折：** 刘洋再也不用半夜被"磁盘空间不足"的报警叫醒了。DSO跑出的每个case自动进入BIG的版本管理体系，PPA排名靠后的DB被自动降级回收空间，排名靠前的完整保留随时可用。120个case从4.2TB压缩到0.4TB，节省超过90%的存储——而且整个寻优过程再也不会因为磁盘满了而崩溃。他终于可以把精力放回PPA优化本身，而不是和存储空间打架。

**揭示的能力需求：**
- DSO系统集成接口（Python API批量提交）
- PPA排名驱动的智能淘汰策略（Top-K保留，劣序降级）
- 存储水位自动管理（阈值触发淘汰回收空间）
- 寻优任务级版本分组

### Journey Requirements Summary

| 能力领域 | 揭示的旅程 | 关键需求 |
|---------|-----------|---------|
| 制品集版本管理 | J1, J2, J3 | commit/checkout/log、配方记录、输入校验、环形版本图 |
| 血缘追溯 | J2, J5 | 双向追溯、参数对比、决策链可视化、跨分支血缘链接 |
| 分层存储 | J1, J4, J6 | Exploring轻量存储、Candidate完整存储、Golden冗余备份、PPA排名淘汰 |
| 流水线引擎 | J3 | 步骤编排、自动执行、验证门禁、指标采集、阶段晋升 |
| 执行缓存 | J3 | 完整action hash匹配、输出复用、跳过重复计算 |
| NAS兼容 | J4 | 原生文件系统部署、用户私有分支目录、copy-only增量物化、不可变CAS、服务端元数据 |
| 系统运维 | J4, J6 | 存储统计、GC回收、分层策略配置、监控、存储水位自动管理 |
| 跨流程版本管理 | J5 | 跨分支依赖链接、依赖声明、变更影响预警 |
| DSO存储优化 | J6 | 寻优结果自动版本化、PPA排名淘汰策略、寻优任务级分组 |

## Domain-Specific Requirements

### 不可逆性与Tapeout保障

- BIG的流水线需要能与现有的自动化流程系统对接，而不是替代它——现有系统负责出口检查，BIG负责版本管理和交付编校
- Golden晋升需要严格的权限控制和审计记录——谁在什么时间基于什么依据晋升了Golden版本，必须有不可篡改的记录
- 现有的团队Review + 人工确认流程不会改变，BIG需要让Review过程有据可查（哪些检查项通过、哪些人工确认），但不替代人的决策

### EDA工具链兼容

- 当前团队通过自动化流程系统统一创建规范的目录结构。BIG 应适配用户私有根目录：每个用户在 `/data/<project>/user/<username>/...` 下为每个分支维护稳定工作目录；`big checkout <branch>` 进入目标分支目录，不改写源分支目录
- EDA工具对输入文件路径的依赖是BIG设计的关键约束。分支目录必须使用稳定且不同的真实路径；旧目录中的进程继续使用旧分支，新目录中新启动的进程使用新分支
- 历史版本默认物化为新的兄弟分支目录。仅显式`big restore --in-place <version>`允许在静默目录中执行可恢复增量替换

### 访问控制模型

- BIG需要实现一套独立的权限模型，底层理念应与Linux权限一致（简单、好懂：用户/组/读写）
- 权限粒度至少需要到分支级（不同分支不同权限），制品集级权限可后续迭代
- 需要考虑与现有Linux group体系的映射关系，避免两套权限体系造成混乱

### I/O性能特征

- 顶层模块修时序场景是I/O压力最大的场景之一：需要把多个子模块的PT DB文件同时读入，单次工程读取量极大
- BIG的CAS增量拼接机制在此场景下必须保持高性能——不能因为文件由多个chunk组成而增加读放大

### 跨站点协作

- 设计团队分布在不同地域，NAS分别挂载在各地域机房
- 跨域协作当前通过scp/rsync手动完成，效率低且易出错
- BIG未来需要支持跨站点的版本/制品集同步（Vision阶段），但MVP阶段可以暂不考虑——至少要保证数据模型和架构上不阻碍未来的分布式扩展

### 数据归档与留存

- 当前归档策略选取tapeout Golden版本的完整链路数据，冷备到归档NAS
- 应用层无额外容灾保护，依赖IT基础设施的基本容灾
- BIG的Golden冗余存储机制应能增强现有的归档可靠性——相当于从"单NAS冷备"升级到"多副本可控冗余"
- 归档操作应在BIG中有对应的命令支持（如 `big archive export`），确保归档数据的完整性可校验

### 3DIC多流程版本管理

- 3DIC设计本质上是4个并行流程的版本矩阵管理：2D综合、top die APR、bottom die APR、3D集成
- 核心交叉依赖：top die LEF输出 → bottom die LEF输入；2D网表变更 → top/bottom重新跑；3D集成依赖top+bottom完成
- BIG血缘图必须支持跨分支链接——一个分支的制品集输出可以是另一个分支的制品集输入
- 变更传播预警：当某个流程的关键输出（如top die LEF）发生版本变更时，BIG应能标记受影响的下游流程版本
- 数据模型约束：跨分支依赖关系不应破坏DAG性质（依赖边指向不同分支的节点仍是DAG）

### DSO自动寻优存储管理

- DSO寻优产生海量中间DB（100+ Innovus DB/模块），当前痛点是磁盘膨胀和空间不足导致寻优失败
- BIG需提供与DSO系统的集成接口，使DSO的每个APR case自动成为BIG的制品集版本
- 渐进式淘汰策略：基于PPA指标排名，自动将排名靠后的Design DB降级为Exploring（只保留配方+PPA指标），保留Top-K的完整DB
- 存储水位管理：BIG应能配置存储水位线，当磁盘使用率达到阈值时自动触发淘汰策略
- 寻优分组：支持将同一轮寻优的100+ case归组管理，便于整体查看和操作

### 避坑：不要模仿Git

- Git的分布式、三区模型（working directory → staging area → local repo → remote repo）、rebase/merge策略等概念对芯片工程师来说是过度复杂的负担
- 即使SVN的集中式简单模型也比Git更适合芯片设计的协作模式——工程师只需要"提交"和"更新"，不需要理解本地仓库和远程仓库的差异
- BIG的交互设计原则应为：**最少概念、最少步骤、最少认知负荷**——一个操作能完成的事情不要拆成三个命令，一个概念能解释清楚的事情不要引入三个术语
- 这是整个系统设计的顶层约束，影响CLI命令设计、GUI交互流程、报错信息、帮助文档等方方面面

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. 制品集+文件双中心模型（核心创新）**

这是BIG针对芯片场景的重要产品选择。Git、Perforce、DVC、MLMD 和构建系统中已有 commit、workspace、stage、execution、artifact 和 action cache 等相近概念；BIG 的差异不在于宣称首创，而在于把"一组配套的输入文件+工具参数+输出文件"固化为适配 EDA 工作流的原子制品集，并与 NAS、生命周期和血缘追溯整合。

- Google MLMD最接近此抽象（Execution + input/output Artifacts），但只管元数据不管存储和去重
- DVC通过pipeline stage隐式绑定输入输出，但不是一等公民对象
- W&B的Artifact是版本化文件集合，但输入输出关联依赖Run，不是Artifact本身的属性

BIG的创新在于：制品集既是版本管理的原子单位（有独立身份和哈希），又是血缘图的节点（链接上下游制品集），同时还可以降级为纯文件视图（兼容工程师的文件直觉）。

**2. CAS块级去重应用于版本管理（技术突破）**

内容定义分块（CDC/FastCDC）在备份领域已成熟（Restic、Borg），但从未应用于ML/EDA版本管理系统。所有现有系统停留在文件级CAS：

| 系统 | 去重粒度 | 对50GB文件改100MB的存储开销 |
|------|---------|---------------------------|
| Git LFS | 整文件SHA-256 | 50GB（全量新副本） |
| DVC | 整文件MD5 | 50GB（全量新副本） |
| Perforce | 整文件gzip | ~50GB（二进制无增量） |
| BIG (FastCDC，待EDA基准验证) | 可调CDC块 | 理论上接近变更块大小，实际取决于文件格式 |

FastCDC 适合作为 Growth 候选，但块大小、去重比例和读放大不能直接从通用数据集外推到 EDA 文件。MVP 必须使用真实 Innovus DB、GDS/OASIS、LEF/DEF 和参数文件建立基准，再决定 min/avg/max 参数与是否引入 Pack。

**3. 完整action hash作为缓存Key（系统级优化）**

DVC的Run Cache、Bazel Action Cache 和 Pachyderm 的 Datum Caching 实现了类似概念。BIG 可以将其适配到 EDA：缓存 Key 不能只包含输入和参数，还必须纳入命令、工具/PDK/库版本、选定环境变量、平台和 schema 版本。

- CI/CD重跑场景：命中率可达80-100%（Bazel remote cache基准）
- 迭代开发场景：命中率约10-30%（参数频繁变化）
- EDA固定流程重跑：预期较高命中率（工具版本和参数相对稳定）

缓存是纯增量收益——命中则节省计算，不命中不影响功能正确性。

**4. 版本图语义边（设计修正）**

基于调研发现，BIG应修正"版本图有环"的数据结构设计：

- **语义层面**：芯片设计确实存在下游驱动上游变更的回退流程，这是真实的业务语义
- **数据结构层面**：应使用DAG + 带类型语义边（`derived_from`）实现，而非允许真正的环
- **具体方案**：回退操作通过"移动分支指针到历史节点" + "创建derived_from语义边"来表达，保持DAG的数学性质（拓扑排序、LCA计算等）不变
- **收益**：避免环形图的理论和实践难题，同时完整保留回退决策链的语义信息

**5. PPA排名驱动的智能淘汰（场景创新）**

现有备份去重系统（Restic/Borg）基于时间或手动策略淘汰旧版本。BIG创新：将外部业务指标（DSO提供的PPA加权得分：正分越高越优）融入存储生命周期决策——劣序Design DB自动降级回收空间，优序Design DB自动晋升保留。BIG不负责PPA计算，仅消费DSO提供的得分作为淘汰决策输入——简洁、解耦。

### Market Context & Competitive Landscape

**现有系统的定位空白：**

```
         去重粒度
         粗 ←————————————→ 细
    ┌─────────────────────────────┐
  高│ Perforce  Git LFS  DVC/W&B  │
  血│ (整文件)  (整文件)  (整文件)  │
  缘│                             │
  水│            ┌──────┐         │
  平│            │ BIG  │         │
    │            │(CDC块)│         │
  低│  手动命名   MLflow            │
    │  (无血缘)  (无去重)          │
    └─────────────────────────────┘
```

BIG占据的是"高血缘 + 块级去重"的空白象限。没有任何现有系统同时提供完整的制品集血缘追踪和块级内容去重。

**工业界的变通方案：** Hugging Face通过手动分片（5GB一片）近似实现块级去重，说明行业对此有真实需求，但缺乏系统级解决方案。

### Validation Approach

**需要验证的关键假设：**

| 假设 | 验证方法 | 成功标准 | 失败退路 |
|------|---------|---------|---------|
| EDA文件CDC去重有效 | 收集真实EDA项目的多版本文件，跑FastCDC去重测试 | 去重比 ≥ 3:1 | 降级为文件级CAS |
| 制品集概念可被工程师理解 | 原型可用性测试（CLI + GUI） | 工程师5分钟内理解核心操作 | 加强文件视图降级入口 |
| 配方缓存命中率有价值 | 对历史项目跑配方匹配分析 | 固定流程重跑命中率 ≥ 50% | 缓存作为可选优化，不影响核心流程 |
| NAS直读性能可达标 | CAS读取 + copy-only增量物化基准测试 | 读吞吐 ≥ NAS直读的70% | 仅复制摘要变化文件；禁止reflink/COW假设和可写hardlink/symlink指向CAS |

**EDA文件去重基准——待填补的空白：** 目前没有EDA文件格式的CDC去重公开基准数据。BIG应在MVP阶段首先建立此基准，这对行业也有参考价值。

### Risk Mitigation

| 创新点 | 主要风险 | 退路 |
|--------|---------|------|
| 制品集双中心模型 | 工程师可能不理解"制品集"概念 | 提供纯文件版本视图作为降级入口 |
| CAS块级去重 | EDA文件去重比可能低于预期（OASIS压缩数据差） | 回退到文件级CAS（类似DVC），仍比手动管理好很多 |
| 完整action hash缓存Key | 变参探索场景命中率低 | 缓存是增量收益，不命中不影响功能正确性 |
| 版本图语义边 | 语义边查询增加实现复杂度 | 最简方案：分支指针移动 + commit message记录回退原因 |
| PPA排名驱动淘汰 | PPA指标获取依赖DSO系统接口稳定性 | 支持手动指定淘汰策略（基于时间/大小），不依赖外部指标 |

底线：只要BIG解决了分支和版本管理的基本痛点，存储和I/O不比现状劣化太多就可成立。所有创新点都有合理降级路径。

## Developer Tool Specific Requirements

### Project-Type Overview

BIG是一个面向芯片设计工程师的CLI优先开发者工具，采用Python为主要开发语言（MVP阶段），以`bigd /api/v1`作为公共集成边界。Electron+Web为可选官方参考GUI，外部系统可以基于同一OpenAPI和事件契约定制界面。部署目标为CentOS生产环境，编译安装方式。BIG需与现有Python+TCL自动化流程系统双向集成，流水线引擎定位为子进程编排器。

### Language & Runtime

- **主要语言：** Python（MVP阶段优先跑通，性能瓶颈后续用C或Rust扩展优化）
- **参考GUI技术栈：** Electron + Web（独立可选客户端，原型阶段先不整合到现有EDA环境）
- **性能优化路径：** 识别I/O和CPU热路径（FastCDC分块、CAS读写、chunk拼接），MVP用纯Python实现并建立基准测试，性能不达标时引入C/Rust扩展
- **兼容性约束：** 需兼容CentOS生产环境的Python版本

### Installation & Deployment

- **目标平台：** CentOS（统一生产环境，无需多发行版支持）
- **安装方式：** 编译安装（容器化暂不适用，EDA环境对容器适配不好）
- **构建产物：** CLI/SDK安装包 + `bigd`服务端安装包 + 可选官方GUI安装包
- **依赖管理：** 最小化外部依赖，避免与EDA工具链的库版本冲突

### Integration Architecture

- **与现有自动化流程系统双向集成：**
  - BIG → 现有系统：BIG流水线step调用 `pds_xxx` 命令启动工具或执行动作
  - 现有系统 → BIG：`pds_xxx` 命令调用BIG命令完成版本管理步骤
- **EDA工具调用方式：** 子进程编排模型——每个step = 启动子进程执行工具命令，step间通过文件路径传递数据
- **流水线引擎定位：** 子进程编排器（类CI runner），BIG管理对输入/输出文件的认知（配方），不改变EDA工具本身的数据传递方式
- **现有系统技术栈：** Python + TCL，BIG需提供Python友好的集成接口
- **DSO系统集成：** DSO系统通过BIG Python API提交寻优结果，BIG自动创建制品集版本并记录PPA指标；BIG根据淘汰策略自动管理存储空间

### API Surface

- **CLI命令体系：** 推动"最少概念、最少步骤、最少认知负荷"原则（详见 Domain-Specific Requirements）
  - 版本管理核心：`init`, `commit`, `checkout`, `restore`, `log`, `branch`, `shell-init`
  - 流水线：`pipeline run`, `pipeline status`
  - 仓库管理：`repo init`, `repo config`, `repo stats`, `repo gc`
  - 归档：`archive export`
- **公共HTTP API：** 从MVP开始提供版本化`/api/v1`与OpenAPI schema；CLI、SDK、官方GUI和外部定制GUI共享资源模型
- **Python集成接口：** 供现有`pds_xxx`命令和未来扩展调用的公共API client封装
- **GUI功能范围（原型阶段）：** 官方GUI是可选参考客户端，用于版本树可视化和版本挑选；独立运行，暂不嵌入EDA环境，不使用GUI专用业务端点

### Documentation

- **CLI内置帮助：** 每个命令的 `--help` 输出完整且易懂
- **用户手册：** 详细的使用文档，涵盖所有命令、工作流和最佳实践
- **设计文档：** 技术架构、数据模型、存储引擎设计，供团队内部开发参考
- **快速上手指南：** 新用户5分钟内跑通核心流程
- **流水线模板示例：** 预配置的流水线定义模板（如RTL→后端交付的经典流程）

### Code Examples

**Python API调用示例：**
```python
import big

# 初始化仓库
big.repo.init("/nas/projects/3dic-project-2026")

# 创建制品集版本
artifact = big.commit(
    message="baseline floorplan",
    inputs=["rtl/*.v", "sdc/*.sdc"],
    params={"place_density": 0.6, "util": 0.7},
    outputs=["out/*.def", "out/*.gds"]
)
print(f"Committed: {artifact.id} [{artifact.review_state}/{artifact.retention_state}]")

# 血缘追溯
lineage = big.log.lineage(artifact_id="signoff_v5", direction="upstream")
for node in lineage:
    print(f"  {node.id} [{node.review_state}/{node.retention_state}] <- {node.param_changes}")
```

**Pipeline定义文件示例（.big/pipeline/rtl-to-backend.toml）：**
```toml
[pipeline]
name = "rtl-to-backend"
description = "RTL → 后端交付流水线"

[[step]]
name = "rtl-check"
command = "pds_rtl_check --input {{inputs.rtl}}"
inputs = { rtl = "*.v" }
outputs = { report = "check/*.rpt" }

[[step]]
name = "synthesis"
command = "pds_synth -top {{params.top}} -input {{inputs.rtl}}"
depends_on = ["rtl-check"]
inputs = { rtl = "*.v" }
params = { top = "chip_top" }
outputs = { netlist = "synth/*.v", sdc = "synth/*.sdc" }

[[step]]
name = "lvs"
command = "pds_lvs --layout {{inputs.layout}} --source {{inputs.source}}"
depends_on = ["synthesis"]
```

**常见CLI工作流脚本示例：**
```bash
# 日常探索：三次尝试 + 对比
big checkout feature/fp-exploration
# ... 跑EDA工具 ...
big commit -m "try A" --inputs "rtl/*.v" --params "density=0.6" --outputs "out/*"
# ... 改参数重跑 ...
big commit -m "try B" --inputs "rtl/*.v" --params "density=0.55" --outputs "out/*"
big diff v1 v2  # 对比两次配方差异

# 问题追溯：从问题目标回溯
big log --lineage signoff_v5 --upstream
big checkout fp_v2 --new-branch fp-from-v2  # 从早期版本创建兄弟分支重新出发
```

### Migration & Onboarding

- **目录结构迁移：** 需要支持现有自动化流程系统的用户私有目录约定。每个分支使用 `/data/<project>/user/<username>/<branch>/` 下的稳定真实目录；`big checkout <branch>`进入目标目录，不复用或改写源目录
- **学习曲线控制：** 工程师从手动命名管理迁移到BIG，过渡期可能需要双轨运行
- **示例项目：** 提供一个完整的示例项目，让工程师快速体验BIG的核心价值

**目录结构映射表：**

| 现有自动化流程目录 | BIG目录 | 说明 |
|------------------|--------|------|
| `/proj/3dic/user/liming/fp_v1` | `/data/proj_A/user/liming/fp-v1/` | 用户私有稳定分支目录，版本通过commit管理 |
| `/proj/3dic/user/liming/fp_v2` | `/data/proj_A/user/liming/fp-v2/` | `big checkout fp-v2`进入该目录；旧EDA进程仍留在`fp-v1/` |
| `/proj/3dic/release/golden_v5` | `/data/proj_A/release/<release-id>/` | Candidate流水线从不可变CAS发布版本目录；Golden由评审状态与驻留策略表达 |

**命令对照表：**

| 手动命名操作 | BIG命令 | 说明 |
|------------|--------|------|
| `cp -r fp_v1 fp_v2` | `big commit -m "v2"` | 版本提交而非目录复制 |
| 文件名猜测追溯 | `big log --lineage <id>` | 血缘追溯替代人工推断 |
| `cd ../fp_v2` | `big checkout <branch>` | shell集成进入稳定兄弟目录，不改写旧分支 |
| `rm -rf fp_v1 && cp -r fp_v2 fp_v1` | `big restore --in-place <version>` | 仅在静默目录中显式执行可恢复增量copy |
| 邮件/文档记录参数 | 自动写入配方 | 参数记录嵌入commit |

**双轨运行期操作规范：**
- 现有自动化流程系统命令和BIG命令可并存，但同一分支不应同时用两种方式管理
- 迁移优先选择新项目或新分支试点，成熟团队逐步迁移现有分支
- 过渡期结束标志：团队90%以上工程师日常使用BIG，手动命名目录不再更新

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — 解决最核心的痛点（工程师管理每一步输入输出件的版本和关系），证明BIG的业务价值，而非展示技术极限。

**Pilot Scale:** 1-2个团队试用，10-30人规模，20-40个模块。MVP需要在真实项目中可用，但不支撑全公司规模。

**Resource Assumption:** 小团队（Maker + 1-2人），6-9个月交付MVP。

**Core Hypothesis to Validate:** 工程师愿意用CLI工具管理版本和血缘，且这确实能解决追溯慢、手动混乱的痛点。技术优化（FastCDC、配方缓存等）可在验证业务价值后逐步叠加。

### Benchmark-Driven Development Principle

BIG将基准测试贯穿整个设计与实现过程，确保各项核心能力可量化、有数据支撑，驱动迭代优化决策：

- **存储效率基准**：在不同EDA文件格式（GDSII/OASIS、DEF/LEF、PT DB、Verilog等）上持续测量去重比，为分层存储策略和FastCDC参数调优提供数据依据
- **I/O性能基准**：持续监控读吞吐量（vs NAS直读）、读放大倍数、版本切换延迟等指标，确保≥70% NAS直读的底线
- **配方缓存基准**：在真实项目中测量缓存命中率，按场景分类（CI重跑、迭代开发、固定流程），为缓存策略分层提供数据
- **功能可用性基准**：测量工程师完成核心操作（commit、追溯、回退）的时间和错误率，验证"最少认知负荷"原则的效果

每个基准从MVP阶段建立，在Growth和Vision阶段持续演进，所有优化决策必须基于基准数据而非直觉。

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1（日常探索）：版本提交、分支管理、探索历史
- Journey 2（问题追溯）：血缘追溯、回退到历史版本

**Must-Have Capabilities:**

| 能力 | 说明 |
|------|------|
| CLI核心命令 | `init`, `commit`, `checkout`, `log`, `branch` |
| 制品集数据模型 | 输入文件+工具参数+输出文件作为原子版本单位 |
| 文件级CAS存储 | MD5/SHA-256寻址，相同文件只存一份 |
| 分层存储 | Exploring只存配方→Candidate完整存储→Pinned→Golden |
| 用户私有分支目录 | NAS原生部署；用户在私有根目录下为每个分支维护稳定真实目录，`big checkout <branch>`进入目标目录且不改写源目录 |
| Shell集成与显式restore | 一次安装shell wrapper后日常仍是一条`big checkout`；历史内容原地覆盖仅通过`big restore --in-place`显式执行 |
| 血缘追溯 | CLI查询制品集上下游关系链 |
| 跨分支血缘追踪 | 血缘链可跨分支链接上下游依赖 |
| 输入完整性校验 | commit时自动检测漏文件/错文件 |
| DAG + derived_from语义边 | 回退通过移动分支指针+语义边表达，不创建真正的环 |
| 文件路径隔离 | 每个分支目录路径稳定；运行中的EDA进程不会因另一个shell切分支而读写到新分支 |
| 分支级权限 | 类Linux简单权限模型（用户/组/读写）|

**Explicitly Deferred from MVP:**

| 能力 | 原因 | 目标阶段 |
|------|------|---------|
| CAS+FastCDC块级去重 | 技术风险高，MVP验证业务价值不需要 | Growth |
| 完整action hash缓存Key | 依赖流水线引擎与工具链指纹 | Growth |
| 流水线引擎 | 需要独立的验证周期 | Growth |
| GUI | 核心流程可由CLI覆盖 | Growth |
| DSO存储策略集成 | 需要DSO系统API先就绪 | Growth |
| 跨流程依赖声明 | MVP先支持手动跨分支血缘查询 | Growth |
| 跨站点同步 | MVP不支持分布式 | Vision |
| 归档命令 | 可手动完成 | Growth |

### Post-MVP Features (Phase 2 — Growth)

**Additional User Journeys Supported:**
- Journey 3（流水线交付）：规范化交付流程
- Journey 4（IT运维）：存储监控、GC回收（基础版可在MVP实现）

**Growth Capabilities:**
- CAS+FastCDC块级去重（基于MVP建立的EDA去重基准数据决策参数）
- 完整action hash缓存Key（命令+输入+参数+工具链+环境+平台匹配后复用输出）
- 流水线定义与执行引擎（子进程编排器）
- 验证门禁Agent（调用LVS/DRC等外部工具）
- PPA指标与制品集版本绑定
- 影响分析（正向追溯，含3DIC跨die流程影响追溯）
- 基线快照
- GUI基础版（Electron+Web，版本树可视化、版本挑选）
- DSO自动寻优存储策略引擎（PPA排名驱动的智能保留/淘汰）
- 跨流程依赖声明与变更预警
- 归档命令（`archive export`）
- Python集成接口（供pds_xxx命令调用）

### Expansion Features (Phase 3 — Vision)

- GUI高级版（血缘图可视化、流水线监控仪表盘、3DIC全流程版本图谱可视化）
- 多站点分布式部署（类Commit-Edge架构）
- Delta传输优化
- 与交付制品系统集成
- 插件生态

### Risk Mitigation Strategy

**Technical Risks:**

| 风险 | 缓解措施 |
|------|---------|
| 文件级CAS在增量修改场景存储膨胀 | MVP先用分层存储（Exploring只存配方）缓解；Growth引入FastCDC根治 |
| EDA文件去重效果未知 | MVP阶段建立去重基准测试，为Growth阶段FastCDC参数调优提供数据 |
| I/O性能不达标 | 避免FUSE方案；文件级CAS读取即直接读NAS文件（读放大≈1.0x）；持续性能基准监控 |

**Market/User Risks:**

| 风险 | 缓解措施 |
|------|---------|
| 工程师不愿改变工作方式 | MVP专注解决最痛的点；最少概念设计降低门槛；双轨过渡期 |
| 制品集概念不被理解 | 同时提供文件视图降级入口；示例项目引导；详细用户手册 |

**Resource Risks:**

| 风险 | 缓解措施 |
|------|---------|
| 团队小、时间紧 | MVP范围已大幅缩减（砍掉FastCDC、流水线、GUI）；优先跑通核心流程 |
| Python性能瓶颈 | 识别热路径，建立基准，必要时引入C/Rust扩展，但不提前优化 |

## Functional Requirements

### 制品集版本管理

- FR1 [MVP]: 工程师可以创建制品集版本（指定输入文件、工具参数、输出文件）
- FR2 [MVP]: 工程师可以在commit时自动校验输入文件完整性（检测遗漏和错误）
- FR3 [MVP]: 工程师可以查看分支上的制品集版本历史
- FR4 [MVP]: 工程师可以查看任意制品集版本的配方详情（输入文件哈希、工具参数、输出文件哈希）
- FR5 [MVP]: 工程师可以对比两个制品集版本的配方差异
- FR6 [MVP]: 工程师可以执行`big checkout <branch>`进入目标分支的稳定真实目录，也可以执行`big checkout <version> --new-branch <name>`从历史版本物化新的兄弟分支目录；两者均不得改写源分支目录
- FR7 [MVP]: 系统可以为每个制品集版本计算并记录用于追溯的配方哈希（hash(输入+参数)）；该哈希不默认等同于可复用输出的缓存Key

### 分支管理

- FR8 [MVP]: PD Lead可以在项目中创建命名分支
- FR9 [MVP]: 工程师可以通过单条`big checkout <branch>`命令解析或物化目标分支目录，并通过shell集成进入该目录；未安装shell集成时CLI输出可执行的`cd -- <target-path>`
- FR10 [MVP]: 工程师或自动化任务可以在NAS上的`/data/<project>/user/<username>/<branch>/`维护每个分支的稳定真实目录；禁止使用可变`current` symlink作为隔离边界
- FR11 [MVP]: 工程师切换分支后，原目录中的EDA进程继续保持原cwd、已打开文件描述符和绝对路径，新目录中新启动的进程使用目标分支
- FR12 [MVP]: PD Lead可以设置分支的访问权限（用户/组/读写）
- FR13 [MVP]: 系统可以通过移动分支指针到历史节点来表达回退操作（分支指针回退，非创建逆向commit）
- FR14 [MVP]: 系统可以记录制品集间的`derived_from`语义关系（如"此版本从某个早期版本回退后重新生成"）
- FR33 [MVP]: 工程师可以选择性checkout制品集的文件子集，而非全量加载（适用于百万文件级别的项目）

### 血缘追溯

- FR15 [MVP]: 工程师可以从任意制品集逆向追溯其完整上游血缘链（输入从哪个制品集来）
- FR16 [Growth]: 工程师可以查看血缘链上每个节点引入的参数变更
- FR17 [Growth]: 工程师可以从任意制品集正向追溯其下游影响范围（哪些制品集依赖它）

### 分层存储

- FR19 [MVP]: 系统可以分别管理制品集的评审状态（Exploring→Candidate→Pinned→Golden）和驻留状态（resident→recipe_only→archived/missing）
- FR20 [MVP]: 系统可以在宽限期后将Exploring制品集降级为recipe_only而回收输出文件，并明确提示该版本checkout时需要降级物化或重跑
- FR21 [MVP]: PD Lead可以手动将制品集晋升到更高生命周期阶段
- FR22 [Growth]: 系统可以将Golden阶段的制品集设置为只读，禁止修改或删除
- FR23 [Growth]: 系统可以为Golden阶段的制品集存储多副本冗余备份

### 仓库管理

- FR24 [MVP]: IT管理员可以在NAS目录上初始化BIG版本仓库
- FR25 [Growth]: IT管理员可以配置仓库的分层存储策略（如Golden副本数量、备份路径）
- FR26 [MVP]: IT管理员可以查看仓库的存储使用统计（总用量、CAS去重比、各层数据量）
- FR27 [Growth]: IT管理员可以执行垃圾回收释放被淘汰分支的孤立存储块
- FR28 [Growth]: IT管理员可以导出Golden制品集用于归档，并支持完整性校验

### 系统集成

- FR29 [Growth]: BIG流水线step可以调用外部命令（`pds_xxx`等）作为子进程执行
- FR30 [Growth]: 外部系统可以通过BIG的Python SDK调用版本化公共HTTP API执行BIG版本管理操作；SDK不得直接导入服务端数据库或业务实现
- FR31 [Growth]: BIG可以与现有自动化流程系统双向交互（BIG调用`pds_xxx`，`pds_xxx`调用BIG）
- FR32 [MVP]: 工程师可以通过CLI内置帮助获取每个命令的使用说明
- FR45 [Growth]: 当制品集标记为Candidate时，系统必须在同一事务中记录状态迁移、审计和可靠outbox事件；流水线幂等消费事件，仅从不可变manifest/CAS物化到staging，验证后发布版本化统一交付目录
- FR46 [Growth]: 官方GUI和外部定制GUI必须通过同一版本化公共API、OpenAPI schema和事件契约接入；不得依赖GUI专用业务端点、直连数据库或导入服务端模块

### 跨流程版本管理

- FR34 [MVP]: 工程师可以在血缘追踪中跨分支链接上下游制品集依赖（一个分支的输出是另一个分支的输入）
- FR35 [Growth]: 工程师可以声明跨流程的依赖关系（如"top_die_apr v3 的输出LEF 被 bottom_die_apr v5 依赖"）
- FR36 [Growth]: 当跨流程依赖的上游版本发生变更时，系统可以标记受影响的下游版本并发出预警

### DSO存储优化集成

- FR37 [Growth]: BIG可以与DSO系统集成，DSO的每个APR case自动创建为BIG制品集版本（含PPA指标）
- FR38 [Growth]: 系统可以根据PPA加权得分排名驱动存储淘汰策略——保留Top-K设计的完整DB，劣序DB保留Exploring评审状态并将驻留状态降级为recipe_only。PPA得分由DSO系统计算并随制品集提交，BIG作为淘汰决策输入，不负责PPA计算
- FR39 [Growth]: 工程师可以配置存储水位线，当磁盘使用率达到阈值时自动触发淘汰策略回收空间

### 基础正确性

- FR40 [MVP]: 系统必须将CAS对象发布为只读不可变文件，禁止通过可写hardlink或symlink把CAS对象直接暴露给EDA工作区
- FR41 [MVP]: 系统必须在commit时先建立一致staging快照，检测复制期间发生变化的文件，并在全部CAS对象发布成功后再原子提交manifest
- FR42 [MVP]: 系统必须通过单写`bigd`元数据服务处理提交、分支和审计写操作；SQLite仅作为`bigd`本地磁盘上的可替换仓储adapter，不允许客户端共享打开NAS数据库文件。应用层只依赖`MetadataRepository`接口
- FR43 [MVP]: 系统必须在内部为用户私有稳定分支目录维护owner、host、root、branch/version、generation、受管lease与显式restore恢复journal。branch checkout不得改写源目录；手工启动的EDA写入进程无法可靠自动发现，`big restore --in-place`前停止写入属于使用契约，严格受控执行使用`big run -- <command>`获取lease
- FR44 [Growth]: 系统必须使用完整`action_hash`作为输出复用缓存Key，至少包含命令、依赖摘要、参数、工具/PDK/库版本、选定环境变量、平台与schema版本

## Non-Functional Requirements

### Performance

| NFR | 指标 | 测量方法 | 依据 |
|-----|------|---------|------|
| NFR1: 文件读取吞吐量 | 通过BIG读取文件不低于NAS直读的70% | dd/fio基准测试 + EDA工作负载回放（PT DB读取、DEF加载），文件级CAS直接读取场景，数据量≥10GB | 成功标准、EDA工作I/O密集 |
| NFR2: 存储读写带宽 | 存储层读写吞吐量 ≥ 1 GB/s | fio顺序读写基准（block size=1M，numjobs=4），在CentOS+NAS生产环境实测 | 满足大规模EDA数据传输需求（顶层修时序多子模块PT DB并发读取等） |
| NFR3: 血缘追溯响应时间 | 单次血缘链查询 < 30秒 | 在含≥1万制品集版本的仓库中执行全链追溯查询，取10次中位值 | 成功标准 |
| NFR4: commit操作耗时 | commit操作额外开销 < 文件哈希计算时间的10% | 对比纯哈希计算耗时与big commit端到端耗时（扣除哈希时间），测试数据集≥10000文件；DSO批量commit场景下（100+ case同时完成），commit并发性能不下降 | 不显著改变工程师工作节奏 |
| NFR5: 目录物化与恢复延迟 | 新分支目录物化或显式原地restore完成延迟 < 同等文件量cp操作的2倍 | 在低版本NAS上分别对比新目录普通copy物化、增量`big restore --in-place`与`cp`，覆盖10万级文件和不同变化比例，执行5次取中位值 | 不依赖reflink/COW仍需保持可接受速度 |
| NFR6: 并发支持 | 支持同一分支上10个工程师从各自私有目录同时commit不冲突 | 10个客户端通过bigd同时对同一分支执行commit，验证乐观并发、无数据损坏和丢失，连续测试100轮 | 10-30人团队的真实场景 |

### Security

| NFR | 指标 | 测量方法 | 依据 |
|-----|------|---------|------|
| NFR7: 访问控制 | 所有版本管理操作需经过权限检查，未授权操作拒绝率100% | 以无权限用户执行全部CLI命令，验证每个命令均被拒绝；覆盖用户/组/角色组合 | 芯片设计数据是核心IP |
| NFR8: 审计追踪 | 所有写操作（commit、晋升、权限变更）记录服务端append-only哈希链审计日志，并定期外部锚定 | 执行写操作后检查哈希链完整性；模拟篡改验证可检测；验证外部不可变副本存在 | Golden晋升的可追溯性要求 |
| NFR9: 数据完整性 | CAS存储的文件内容哈希校验通过率100% | 写入后立即回读校验全量文件；定期全仓库完整性扫描 | 版本管理的数据完整性是底线 |
| NFR10: 权限模型简洁性 | 权限模型概念数 ≤ 5个（用户、组、读、写、所有者）| 人工评审权限模型文档，计数核心概念 | "最少认知负荷"原则、与Linux权限对齐 |

### Reliability

| NFR | 指标 | 测量方法 | 依据 |
|-----|------|---------|------|
| NFR11: Golden数据耐久性 | Golden阶段必须满足已定义的RPO/RTO，且单一故障域失效时数据完整可读 | 模拟单盘/单节点/单NAS故障，验证完整读取、RPO/RTO和修复；每季度恢复演练 | Tapeout不可逆 |
| NFR12: 整体数据可靠性 | 非Golden数据丢失率 < 0.01% | 注入CAS对象损坏，验证摘要检测与可恢复比例；运行6个月统计实际丢失事件 | 成功标准 |
| NFR13: 冗余备份 | Golden数据至少存2份于不同故障域 | 检查Golden对象副本分布，验证不同物理存储；每日scrub并验证不一致修复 | 增强归档可靠性 |
| NFR14: 故障隔离 | 单个CAS chunk损坏时，系统可检测并报告，不影响其他数据 | 注入单个chunk损坏，验证检测告警触发、其他文件正常访问 | 局部故障不扩散 |

### Scalability

| NFR | 指标 | 测量方法 | 依据 |
|-----|------|---------|------|
| NFR15: 单项目文件数 | 支持 ≥ 100万个文件的版本管理 | 创建含100万文件的仓库，执行commit/checkout/log基准操作验证功能正确和性能可接受 | 成功标准 |
| NFR16: 单项目数据量 | 支持 ≥ 1PB数据的版本管理 | 在CAS存储池中填充至1PB量级，执行commit/checkout/stats验证功能正确 | 成功标准 |
| NFR17: 版本历史规模 | 支持 ≥ 10万个制品集版本的历史查询 | 创建含10万版本的仓库，执行log/lineage查询验证响应时间在可接受范围 | 长期项目积累 |
| NFR21: DSO寻优规模 | 支持单模块 ≥ 500 组APR Case的版本管理与存储淘汰 | 创建含500个制品集的寻优分组，验证淘汰策略执行和空间回收效果 | DSO场景的真实规模 |

### Integration

| NFR | 指标 | 测量方法 | 依据 |
|-----|------|---------|------|
| NFR18: Python API可用性 | 提供Python SDK公共API client，核心操作可通过Python调用 | 编写Python脚本通过SDK调用公共API（commit/checkout/log/branch），验证功能与CLI等价 | 与pds_xxx系统集成 |
| NFR19: 子进程调用可靠性 | 流水线step作为子进程执行时，退出码和标准输出/错误可准确捕获 | 编写测试step（正常退出0、异常退出非0、大量输出），验证BIG准确捕获退出码和全部输出 | 子进程编排器模型 |
| NFR20: 路径隔离与透明性 | BIG管理的文件在用户私有稳定分支目录中的NAS真实路径可被外部工具直接访问；branch checkout不得改变仍在运行进程所使用的目录内容 | 在分支A目录启动持续读写进程后，从另一个shell执行`big checkout B`；验证旧进程仍只写A，新进程在B中工作。另行验证显式restore在dirty state或受管lease存在时拒绝 | EDA工具无需适配BIG存储格式，且切分支不混淆运行中进程 |
| NFR22: 公共API可替换性 | CLI、SDK、官方GUI和外部定制GUI共享版本化公共API与事件契约；无GUI专用业务端点 | 根据OpenAPI生成独立测试客户端，完成浏览、晋升、交付状态查询；静态检查GUI不直连数据库、不导入服务端模块 | GUI不是BIG产品边界，便于现有系统定制集成 |
