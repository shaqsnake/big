---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/research-technical-architecture.md'
  - '_bmad-output/brainstorming/brainstorming-session-2026-05-17-121344.md'
  - '_bmad-output/planning-artifacts/prd-validation-report.md'
workflowType: 'ux-design'
classification:
  projectType: '开发者工具（CLI + GUI/Electron+Web）'
  domain: '半导体/EDA'
  complexity: '高'
---

# UX设计规格 - BIG

**作者:** shaqsnake
**日期:** 2026-05-28

---

## Executive Summary

### Project Vision

BIG 是面向芯片设计的大文件版本管理与团队协作系统。核心洞察是：芯片设计的版本管理对象不是文件，而是设计决策历史。BIG 通过"制品集+文件"双中心模型，解决工程师手动命名混乱、问题追溯慢半天以上、交付依赖人工规范而非系统保障的痛点。系统采用 CLI 为核心交互界面，Electron+Web GUI 用于版本树/血缘图可视化和版本挑选操作，部署在现有 NAS 基础设施上，追求工程师工作方式的零侵入和最少认知负荷。

### Target Users

| 角色 | 典型场景 | 核心痛点 | 界面偏好 |
|------|---------|---------|---------|
| 数字后端工程师 | 日常探索（多方案对比）、问题追溯与回退 | 版本混乱、追溯慢、选错输入 | CLI 为主，GUI 辅助查看全局 |
| PD Lead | 交付把控、流水线触发、阶段晋升 | 人为失误导致返工、缺乏系统保障 | CLI + GUI（版本挑选、状态总览） |
| IT管理员 | 仓库部署、存储监控、GC回收、权限管理 | 存储爆掉、兼容性担忧 | CLI 为主，GUI 辅助监控仪表盘 |
| 3DIC PD Lead | 跨流程版本同步、依赖预警 | 4个并行流程的版本对齐靠人肉 | CLI + GUI（跨分支血缘图） |
| DSO工程师 | 寻优结果管理、存储水位控制 | 磁盘满导致寻优崩溃、手动删DB怕删错 | Python API + CLI，GUI 辅助分组概览 |

### Key Design Challenges

1. **概念门槛** — "制品集"是新概念，工程师习惯了文件/目录视角。如何在 CLI/GUI 中让制品集自然可理解而不增加认知负荷？文件视图降级入口是关键安全网。
2. **双界面协同** — CLI 和 GUI 分工不同但心智模型必须统一。CLI 用户何时切换到 GUI？两个界面之间的信息如何衔接而不造成定位迷失？
3. **海量数据交互** — 百万文件、10万+版本的项目中，log/lineage/diff 如何保持响应和可读？渐进式信息披露是必须的设计策略。
4. **生命周期表达** — Exploring→Candidate→Pinned→Golden 的晋升流转在 CLI（命令+标记）和 GUI（颜色/图标/布局）中如何统一且直觉地表达？
5. **跨分支关系可视** — 3DIC 跨 die 流程的依赖关系、DSO 寻优分组的层级关系，如何在 GUI 中清晰呈现而不造成信息过载？

### Design Opportunities

1. **"零学习成本"CLI** — 命令设计复用工程师已有的心智模型（类似 SVN 的"提交-更新"而非 Git 的三区模型），一个操作能完成的事不拆成三个命令。
2. **GUI 作为"望远镜"** — 版本树和血缘图是 CLI 天然难以表达的信息形态，GUI 的核心价值在于让全局关系一目了然——这是 CLI 的"放大镜"而非"替代品"。
3. **渐进式信息披露** — 默认只显示摘要（commit msg + lifecycle + 关键指标），用户需要时才展开配方细节、血缘全链或文件差异，避免海量版本的界面崩溃。
4. **工作流连续性** — CLI 和 GUI 共享同一套概念和状态，工程师可以在 CLI 中 `big commit`，在 GUI 中查看版本树，再回到 CLI 中 `big checkout`——界面切换不中断工作流。

## Core User Experience

### Defining Experience

BIG 的核心体验循环是 **commit → explore → checkout**：

- **commit**（提交）：工程师跑完 EDA 工具后，一条命令锁定输入、参数、输出的完整快照。这是每天重复最频繁的操作，必须快（哈希计算不阻塞感知）、必须简单（不需要 staging、不需要三区操作）、必须可靠（输入完整性自动校验）。
- **explore**（探索）：在版本历史和血缘图中导航——对比不同尝试的配方差异、沿着血缘链追溯决策源头、查看跨分支的依赖关系。CLI 提供快速查询，GUI 提供全局可视化。
- **checkout**（切换）：回到任意历史版本重新出发，或切换到不同分支继续工作。路径完全不变，EDA 工具无感知，就像"时间旅行"一样自然。

如果只做好一个交互，一切都会成功：**`big commit`**。只有提交足够简单且可靠，工程师才愿意持续使用，数据积累才足以支撑血缘追溯和配方缓存的全部价值。

### Platform Strategy

| 平台 | 定位 | 使用占比 | 核心价值 |
|------|------|---------|---------|
| CLI | 主战场 | ~70% | 日常所有操作的入口，SSH 远程可用 |
| GUI (Electron+Web) | 望远镜 | ~25% | 版本树可视化、血缘图浏览、版本挑选、DSO分组概览 |
| Python API | 系统集成层 | ~5% | pds_xxx 命令、DSO 系统的程序化调用 |

平台约束：
- 纯键鼠操作，无触屏需求
- CentOS NAS 环境，本质是本地磁盘性能
- CLI 必须支持 SSH 远程使用（无 X11 依赖）
- GUI 独立运行，暂不嵌入 EDA 工具环境
- CLI 和 GUI 共享同一套概念模型和状态数据

### Effortless Interactions

1. **commit 零等待感** — 哈希计算在后台流式进行，进度条即时反馈，工程师不需要等待"提交完成"才能继续下一个动作
2. **checkout 后工具继续跑** — EDA 工具打开的文件句柄不失效，目录结构不变，切换版本就是"文件内容变了但路径没变"
3. **血缘追溯一键到达** — `big log --lineage <id>` 直接输出决策链，无需翻目录、无需问同事
4. **生命周期晋升一步到位** — `big promote <id>` 一条命令完成阶段跳跃，系统自动处理存储策略迁移
5. **文件视图降级入口** — 工程师可以完全不关注"制品集"概念，通过文件路径直接操作，制品集在背后自动管理

### Critical Success Moments

1. **第一次 commit 后发现路径没变** — "这就提交了？我的工具还能继续跑？" → 零侵入的顿悟时刻，这是用户从"试一试"到"愿意用"的转折点
2. **血缘追溯 30 秒找到问题根源** — 从半天到 30 秒的落差冲击，这是用户从"愿意用"到"离不开"的转折点
3. **GUI 中一眼看清版本树全貌** — 从混乱命名到结构化全局视图的认知解放，这是用户信任系统组织能力的关键
4. **checkout 回退后原路重新出发** — 时间旅行的自然感，回退不是"删掉重来"而是"回到那个节点继续"，derived_from 语义边让决策链完整

### Experience Principles

1. **零侵入** — 工程师的工作方式不因 BIG 而改变。文件在同一个 NAS 路径下，EDA 工具不需要任何适配。BIG 是安静的幕后管理者，不是需要被照顾的系统。
2. **最少认知负荷** — 一个操作能完成的事不拆成三个命令，一个概念能解释清楚的事不引入三个术语。CLI 命令设计遵循"提交-切换-查看"的三词心智模型。
3. **渐进披露** — 默认只显示核心信息（提交消息 + 生命周期 + 关键指标），用户主动请求时才展开配方细节、血缘全链或文件差异。百万版本的仓库也不会让界面崩溃。
4. **界面即工具** — CLI 是手的延伸（快速操作），GUI 是眼的延伸（全局洞察）。两者共享概念模型，切换不中断工作流。GUI 不是 CLI 的翻译，而是 CLI 做不到的事的补充。
5. **数据驱动信任** — 每一次 commit 都有完整配方记录，每一次追溯都有精确决策链，存储统计实时可见。用数据完整性而非流程规范来建立信任。

## Desired Emotional Response

### Primary Emotional Goals

**从焦虑到安心（From Anxiety to Calm Confidence）**

芯片工程师当前最大的情绪负担是焦虑：不确定输入版本对不对、恐惧删错数据、挫败于追溯无力、担心磁盘随时爆满。BIG 的核心情感目标是消除这些焦虑，替换为"数据可靠、可追溯、不会丢失"的安心感。每一次交互——从 commit 到 checkout，从 lineage 到 promote——都应该传递同一个信号：你在掌控之中。

### Emotional Journey Mapping

| 阶段 | 当前情绪 | 期望情绪 | 关键交互 |
|------|---------|---------|---------|
| 首次接触 | 怀疑"又来一个工具" | 惊喜"这就提交了？路径还没变！" | 第一次 commit |
| 日常使用 | 习惯性焦虑"版本对不对" | 顺手自然"肌肉记忆级操作" | commit/checkout 日常循环 |
| 问题追溯 | 绝望"又要翻半天目录" | 释然"30秒找到根源" | lineage 追溯 |
| 阶段晋升 | 紧张"别搞砸了" | 自信"系统替我把关" | promote 操作 |
| 存储管理 | 恐惧"磁盘会不会爆" | 放心"水位自动控制" | DSO淘汰/存储统计 |
| 回退重来 | 沮丧"又要重做" | 从容"回到那个点继续" | checkout 回退后重新 commit |

### Micro-Emotions

| 期望情感 | 对立面 | 在 BIG 中的体现 |
|---------|--------|----------------|
| 信心 | 怀疑 | 每条命令执行后有确定性反馈（成功/失败+原因），杜绝"不知道有没有成功"的灰色地带 |
| 安心 | 焦虑 | 数据完整性自动守护，路径不变，Golden 数据冗余保护 |
| 掌控感 | 无力感 | GUI 血缘图让跨分支依赖一目了然，CLI 筛选让海量版本可控浏览 |
| 成就感 | 挫败感 | 晋升成功时明确阶段跃迁反馈，追溯命中时高亮关键决策节点 |
| 信任感 | 不信任 | 存储统计透明可见，CAS 去重比实时展示，每次操作都有审计记录 |

### Design Implications

| 情感目标 | UX 设计策略 |
|---------|-----------|
| 信心 | CLI 命令执行后必须有清晰的完成反馈：成功显示绿色勾+摘要，失败显示红色叉+原因+建议操作。不允许"沉默成功"。 |
| 安心 | commit 时自动校验输入完整性并即时报告；存储水位预警在 70% 时提前显示；Golden 数据操作需二次确认。 |
| 掌控感 | GUI 血缘图支持缩小/放大/过滤/搜索，跨分支依赖用不同颜色区分 lineage 边类型；CLI `--limit` `--filter` 参数让海量版本可控。 |
| 成就感 | promote 操作后有生命周期阶段变化的视觉反馈（CLI 颜色标记 + GUI 动画过渡）；lineage 关键节点用视觉权重区分。 |
| 信任感 | `big repo stats` 实时展示去重比、存储分布、CAS 健康；所有写操作自动记录审计日志，用户可通过 `big audit` 查看。 |

### Emotional Design Principles

1. **确定性反馈** — 每一次操作都有明确的成功/失败信号，不允许"不知道发生了什么"的灰色地带。CLI 用颜色和图标，GUI 用动画和过渡，让结果不可忽视。
2. **预防优于补救** — 在错误发生之前预警（磁盘水位、输入校验），而不是在错误发生后报错。让工程师安心地相信"系统会在我犯错前拦住我"。
3. **透明可见** — 系统在做什么、数据在哪里、存储用了多少——这些信息永远对用户开放可见。"幕后管理"不等于"黑箱操作"。
4. **渐进成就** — 从第一次 commit 的"惊喜"，到日常使用的"顺手"，到关键时刻的"救命"——情感价值随使用深度递增，而不是一次性消耗。

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

**SVN — 双命令心智模型**

SVN 之所以被芯片团队广泛接受，核心在于极简的交互模型：日常工作只需 `svn commit` 和 `svn update` 两个命令。工程师不需要理解 staging area、本地仓库、远程仓库的区别——提交就是提交，更新就是更新。这种"所见即所得"的集中式模型完美匹配芯片设计的协作模式。

- 核心优势：概念极简，学习成本几乎为零
- 关键教训：**CLI 命令设计应复用工程师已有的心智模型，而非创造新的操作范式**

**DVC — 配方即缓存 + 声明式 Pipeline**

DVC 是最接近 BIG 定位的工具。其 Run Cache 机制（`hash(输入+命令+参数)` 匹配已有输出跳过执行）与 BIG 的"配方即缓存 Key"理念完全呼应。`dvc.yaml` 的声明式 pipeline 定义让复杂工具链的编排变得可读可维护。

- 核心优势：配方驱动的缓存命中、声明式 pipeline
- 关键教训：**配方既是存储策略的核心，也是缓存策略的核心——一石二鸟**
- 反模式：DVC 强依赖 Git 追踪 `.dvc` 代理文件，造成"两个版本管理系统"的认知负担，BIG 应避免

**Perforce — 零存储分支 + 按需同步**

Perforce 是芯片行业版本管理的事实标准。其 Lazy Copy 机制通过元数据引用实现零存储开销的分支，Workspace 视图支持按需同步文件子集，这两点是 BIG 的直接参考。

- 核心优势：Lazy Copy 分支零开销、文件级锁定、按需 Workspace 同步
- 关键教训：**分支是元数据引用而非数据复制，checkout 是按需加载而非全量下载**
- 反模式：二进制文件全量存储导致存储膨胀——BIG 用块级去重根治

**W&B/MLflow — 参数·指标·产物三维绑定**

实验追踪工具的核心创新在于将参数（做了什么）、指标（效果如何）、产物（产出什么）三者绑定在一个实验运行上。这与 BIG 的"配方+PPA指标+制品集版本"三位一体完全对应。W&B 的运行分组功能也是 DSO 寻优分组的直接参考。

- 核心优势：三维绑定让决策有据可查、分组概览让批量实验可对比
- 关键教训：**版本不只是文件快照，更是决策的完整证据链**
- 反模式：MLflow 只管元数据不管存储——BIG 必须同时管理数据和元数据

**VS Code — 分栏布局 + 渐进披露**

VS Code 的布局已成为开发者工具的事实标准：左侧资源树 + 中央主内容 + 底部面板。命令面板（Ctrl+Shift+P）提供快速操作入口，折叠面板支持渐进披露。BIG GUI 应借鉴这种已论证的信息架构。

- 核心优势：开发者熟悉的三栏布局、命令面板快速操作、面板可折叠
- 关键教训：**GUI 的布局应复用开发者已习惯的信息层级，而非发明新的视觉范式**

### Transferable UX Patterns

**导航模式：**
- **三栏布局**（版本树 + 详情 + 终端/日志）— 对标 VS Code，开发者无需学习新布局
- **命令面板式搜索** — GUI 中按 `/` 或 Ctrl+K 打开快速搜索，输入版本ID/消息/分支名直达目标

**交互模式：**
- **双命令核心循环**（commit / checkout）— 对标 SVN 的极简模型，工程师日常操作无需记忆更多命令
- **配方匹配自动跳过**（pipeline 中 hash 命中时跳过执行）— 对标 DVC Run Cache，零交互即可节省计算
- **分组概览 + 下钻**（DSO 寻优分组→单个 case 详情）— 对标 W&B 运行分组，批量实验的对比分析

**视觉模式：**
- **生命周期色彩编码** — CLI 和 GUI 统一使用四色系统（Exploring=灰、Candidate=蓝、Pinned=橙、Golden=金），一眼识别版本阶段
- **血缘图节点权重** — 关键决策节点放大/加粗，普通节点缩小/淡化，避免大面积图谱的视觉噪音
- **确定性状态指示** — CLI 用 ✓/✗ 彩色标记，GUI 用图标动画过渡，杜绝"不知道有没有成功"的灰色地带

### Anti-Patterns to Avoid

1. **Git 三区模型**（staging → local repo → remote）— 工程师不需要理解暂存区和本地仓库，一个 `big commit` 搞定
2. **双系统认知负担**（DVC 的 `.dvc` 文件 + Git 追踪）— BIG 一个系统管理所有版本相关数据，不依赖外部 VCS
3. **全量 checkout 默认行为**（Perforce 默认同步全部文件）— 百万文件项目必须默认轻量，`--subset` 按需加载
4. **沉默操作**（命令执行后无反馈或模糊反馈）— 每条命令必须有明确的成功/失败信号
5. **信息过载默认展示**（log 默认显示所有字段）— 默认只显示摘要，详细信息按需展开
6. **GUI 功能对称 CLI**（GUI 复制 CLI 的所有操作按钮）— GUI 聚焦"看"（可视化洞察），CLI 聚焦"做"（快速操作），不重复造轮子

### Design Inspiration Strategy

**直接采纳：**
- SVN 双命令心智模型 → `big commit` / `big checkout` 为日常核心循环
- VS Code 三栏布局 → GUI 左侧版本树 + 中央详情 + 底部日志面板
- 四色生命周期编码 → CLI 颜色标记 + GUI 图标/徽章统一表达

**适配改造：**
- W&B 运行分组 → DSO 寻优分组概览（适配 EDA 场景的 PPA 指标维度）
- DVC Run Cache → 配方即缓存 Key（适配制品集粒度而非 pipeline step 粒度）
- Perforce Workspace 视图 → `big checkout --subset`（适配 NAS 环境的一分支一目录模型）

**坚决避免：**
- Git 三区模型和分布式复杂性
- 双系统依赖（DVC+Git 模式）
- 全量默认加载和沉默操作

## Design System Foundation

### Design System Choice

**Ant Design Vue** 作为 BIG GUI 的设计系统基础。

选择 Ant Design Vue 而非其他方案的核心原因：
- **中文优先** — 组件内置中文排版优化，日期/数字/表格格式开箱即用
- **Data Display 组件丰富** — Table、Tree、Descriptions 等组件直接支撑版本树、血缘图、配方详情等核心视图
- **开发者工具验证** — Ant Design Pro 系列模板已在中后台工具场景大量验证
- **Electron 适配** — 大量 Electron 桌面应用使用 Ant Design Vue，性能和兼容性问题已被社区解决
- **设计语言一致** — 与 Ant Design React 版共享同一设计体系，文档和社区资源可交叉引用

CLI 侧不涉及设计系统，但输出格式（颜色标记、表格排版）需与 GUI 的色彩体系和信息架构保持一致。

### Rationale for Selection

1. **速度优先** — 小团队6-9个月交付 MVP，Ant Design Vue 的 60+ 组件覆盖 BIG GUI 90% 以上的界面需求，无需从零构建
2. **核心视图就绪** — Tree（版本树）、Graph/Tree（血缘图）、Descriptions（配方详情）、Table（DSO分组概览）都有高质量组件
3. **CLI-GUI 一致性** — Ant Design 的色彩体系（蓝色主色、绿色成功、红色错误、橙色警告）可直接映射到 CLI 的输出颜色标记
4. **文档与社区** — 中文文档完善，Vue 生态社区活跃，减少团队的学习成本和排障时间
5. **定制能力充足** — ConfigProvider + Design Token 机制允许在不 fork 的情况下调整主题

### Implementation Approach

**技术栈：**
- Vue 3 + TypeScript + Vite
- Ant Design Vue 4.x（CSS-in-JS 主题引擎）
- Electron（桌面壳，管理窗口生命周期）
- AntV G6 或 D3.js（血缘图渲染，Ant Design Vue 不含图组件，需补充）

**分阶段实施：**
- **MVP**：Ant Design Vue 默认主题 + 最小定制，聚焦版本树和配方详情两个核心视图
- **Growth**：引入 Design Token 定制主题（颜色微调、字体替换），补充血缘图视图（集成 G6），DSO 分组概览
- **Vision**：深度定制主题（暗色模式、3DIC 跨分支图谱可视化、流水线监控仪表盘）

### Customization Strategy

**Minimal Viable Customization (MVP)：**
- 不做主题定制，使用 Ant Design Vue 默认蓝色主题
- 只调整生命周期色彩映射，与 CLI 四色系统对齐：
  - Exploring → 灰色 (`#8C8C8C`)
  - Candidate → 蓝色 (`#1677FF`，Ant Design 主色)
  - Pinned → 橙色 (`#FA8C16`)
  - Golden → 金色 (`#FADB14`)
- ConfigProvider 包裹全局，统一中文 locale

**Growth 阶段定制：**
- Design Token 层级定制：`colorPrimary`、`fontFamily`、`borderRadius` 等
- 暗色模式支持（`theme.algorithm: theme.darkAlgorithm`）
- 自定义血缘图组件（基于 G6，复用 Ant Design 的色彩和字体体系）

**不定制：**
- 不重新设计基础组件（Button、Input、Select 等），保持 Ant Design Vue 默认行为
- 不创建独立的设计系统文档站点——直接引用 Ant Design Vue 官方文档
- 不 fork Ant Design Vue——所有定制通过 ConfigProvider 和 Design Token 实现

## 核心体验定义

### 定义性体验

BIG 的定义性体验是 **`big commit`**——工程师跑完 EDA 工具后，一条命令锁定输入、参数、输出的完整快照。这是每天重复最频繁的操作，也是整个价值链的起点：只有提交足够简单且可靠，数据积累才足以支撑血缘追溯和配方缓存的全部价值。

如果只用一句话让工程师理解 BIG："跑完一行提交，路径不变工具继续跑，版本已经锁定了。"

### 用户心智模型

芯片工程师的版本心智模型是 **"状态快照"** 而非 **"文件变更历史"**：
- 版本 = 某个时间点的输入 + 参数 + 输出的完整绑定
- 提交 = 锁定当前状态，而非记录一组文件差异
- 切换 = 工作目录内容变、路径不变，EDA 工具无感知

他们从 SVN 带来的期望是简单集中式操作——`commit` 就是提交，`update` 就是更新。Git 的 staging area、本地仓库、远程仓库三分区模型是认知负担而非价值。

痛点集中在线性叠加：手动命名混乱、追溯耗时、选错输入返工、磁盘爆满崩溃。

### 核心体验成功标准

1. **提交即锁定** — commit 后数据不可变，确定性保证
2. **路径零变化** — checkout 后目录路径完全一致，EDA 工具无感知
3. **配方自动记录** — 输入完整性自动校验，配方自动生成
4. **反馈即时明确** — 成功 = 绿色 ✓ + 摘要；失败 = 红色 ✗ + 原因 + 建议；无灰色地带
5. **渐进式披露** — 默认一行摘要，`--verbose` 展开配方，`--full` 展开文件列表

### 新颖性模式分析

| 模式 | 归类 | 策略 |
|------|------|------|
| commit/checkout 双命令循环 | 已有模式 | 直接采纳 SVN 模型，零学习成本 |
| 配方即缓存 Key | 组合创新 | 制品集粒度实施，`big log` 展示配方详情 |
| 生命周期四色编码 | 组合创新 | CLI 颜色标记 + GUI 徽章双重表达 |
| 血缘图跨分支链接 | 新颖模式 | 用"决策族谱"隐喻降低门槛 |
| PPA 排名驱动淘汰 | 新颖模式 | 用"自动保洁员"隐喻可视化机制 |

### 体验力学

**核心交互流程：**

1. **发起** — 工程师执行 `big commit -m "message"`，无需 staging、无需选文件，工作目录即提交范围（`.bigignore` 排除规则过滤）；无参数时自动打开编辑器输入提交消息（对标 `svn commit`）
2. **交互** — 后台异步哈希流式计算，进度条即时反馈（`Computing hashes... ████████░░ 80% | 12.4s elapsed`）；输入完整性并行校验，失败立即中断并报告缺失文件
3. **反馈** — 成功：`✓ Committed as a1b2c3d [Candidate]` + 配方摘要 + 去重比；失败：`✗ Commit failed` + 具体原因 + 可操作建议
4. **完成** — 工作目录状态不变，EDA 工具继续运行；自然延伸到 `big log` / `big promote` / GUI 版本树

## 视觉设计基础

### 色彩系统

**主色调：深青蓝（#0E7C86）**

区别于 Ant Design 默认蓝，传递专业性与安稳感，与生命周期四色系统天然兼容。

**语义色彩：**

| 语义 | 色值 | 用途 |
|------|------|------|
| Primary | #0E7C86 | 主操作、导航高亮、选中态 |
| Success | #52C41A | commit 成功、校验通过、Golden 标记 |
| Warning | #FA8C16 | 存储水位预警、Pinned 标记 |
| Error | #F5222D | 操作失败、校验失败、破坏性操作 |
| Info | #1677FF | 提示信息、Candidate 标记 |

**生命周期四色系统（CLI + GUI 统一）：**

| 阶段 | 色值 | CLI | GUI |
|------|------|-----|-----|
| Exploring | #8C8C8C | 灰色标签 | 灰色徽章 |
| Candidate | #1677FF | 蓝色标签 | 蓝色徽章 |
| Pinned | #FA8C16 | 橙色标签 | 橙色徽章 |
| Golden | #FADB14 + #D4B106 描边 | 黄色标签 | 金色徽章 + 星标 |

**中性色阶：**
- Text Primary: #262626 / Secondary: #595959 / Tertiary: #8C8C8C
- Border: #D9D9D9 / Background: #F5F5F5 / Surface: #FFFFFF

**对比度合规：** 所有文本 ≥ 4.5:1（WCAG AA）；Golden 色加描边确保可读性。

### 字体系统

| 用途 | 字体 | 降级链 |
|------|------|--------|
| 中文 UI | Noto Sans SC | PingFang SC, Microsoft YaHei, sans-serif |
| 英文/数字 | Inter | Segoe UI, Roboto, sans-serif |
| 代码/CLI | JetBrains Mono | Fira Code, Source Code Pro, monospace |

**字号层级：** H1 24px / H2 20px / H3 16px / Body 14px / Caption 12px / Code 13px
**字重：** Regular 400（正文）/ Medium 500（数据）/ Semibold 600（标题/按钮）

### 间距与布局基础

**8px 基准网格：** xs 4px / sm 8px / md 16px / lg 24px / xl 32px / xxl 48px

**布局原则：**
1. 信息密度优先 — 默认紧凑布局，减少滚动和视觉跳转
2. 三栏弹性布局 — 左版本树(240-320px) + 中央详情(自适应) + 底部面板(可折叠180-300px)
3. 呼吸感靠结构而非留白 — 分割线和背景色差区分区块
4. CLI 输出对齐 — 等宽字体 + 8px 网格对齐

**网格：** 面板内 24 栏栅格（Ant Design Vue 默认）；卡片内 8px 基线网格

### 无障碍考量

- 所有文本满足 WCAG AA 对比度标准（4.5:1）
- 生命周期用颜色 + 文字标签 + 图标三重传达，不依赖色彩单一通道
- GUI 全键盘可操作，焦点状态清晰
- 支持浏览器字体缩放至 200%
- 尊重 prefers-reduced-motion，减少动效模式下关闭过渡动画

## 设计方向决策

### 探索的设计方向

| 方向 | 核心理念 | 视觉权重 | MVP 难度 |
|------|---------|---------|---------|
| A 极简工具流 | GUI=可视化终端，表格即一切 | 低 | 低 |
| B 结构化工作台 | 工程师工作台，分区明确+渐进披露 | 中 | 低 |
| C 监控仪表盘 | 项目健康仪表盘，全局态势感知 | 中高 | 中高 |
| D 探索地图 | 决策地图，血缘图为核心视觉 | 高 | 高 |

### 选定方向

**方向 B：结构化工作台** — 以 VS Code 三栏范式为基础的工程师工作台，分区明确，渐进披露自然发生。

**融合增强：**
- 来自方向 C：左侧版本树面板顶部嵌入 2-3 个关键指标卡（存储水位环形图、生命周期分布），不独立占据布局
- 来自方向 D：中央面板支持切换为血缘图视图（Growth 阶段由 Tree 升级为 G6 图谱；MVP 先用 Tree 组件实现简化版血缘树）

### 设计理由

1. **范式一致性** — VS Code 三栏布局是开发者工具的事实标准，工程师零学习成本即可理解信息层级
2. **组件映射直接** — Ant Design Vue 的 Tree → 版本树、Descriptions → 配方详情、Table → 文件列表，组件直出无需深度定制
3. **渐进披露天然** — 中央面板按需展现配方摘要→文件变更→血缘关系，不缺不溢
4. **全角色适配** — 工程师快速浏览版本、PD Lead 审查晋升、IT 查看存储指标，同一布局服务不同角色
5. **MVP 效率最高** — Ant Design Vue 组件覆盖率最高，开发周期最短
6. **可演进** — Tree → G6 血缘图、纯表格 → 统计卡、单视图 → 多视图切换，结构化工作台为后续增强提供稳固骨架

### 实施路径

**MVP 阶段：**
- 左侧：版本树（Ant Design Vue Tree 组件，240-320px 可调宽度），顶部嵌入存储水位 + 生命周期分布 2 个微型指标卡
- 中央：详情面板，上方配方摘要（Descriptions），下方可折叠的文件变更列表（Table）
- 底部：可折叠面板（日志 / 终端 / 审计），默认折叠为标签栏
- 血缘视图：中央面板切换为简化版血缘树（Tree 组件递归渲染 DAG 节点）

**Growth 阶段：**
- 血缘视图升级为 G6 全屏交互图谱（可缩放/平移/搜索），支持跨分支链接
- 新增 DSO 寻优分组概览视图（Table + 统计卡片混合布局）
- 暗色模式支持
- Design Token 主题微调（colorPrimary → #0E7C86、fontFamily、borderRadius）

**Vision 阶段：**
- 3DIC 全流程版本图谱可视化（跨 die 血缘图 + 流程间联动关系）
- 流水线监控仪表盘（实时状态、阶段门禁可视化）
- 自定义工作台布局（面板拖拽、视图保存）

## 用户旅程流程

### commit 提交流程

定义性交互。工程师执行 `big commit -m "msg"` 后：
1. 变更检测 → 2. 异步哈希流式计算（进度条非阻塞） → 3. 输入完整性校验（失败即中断+报告缺失文件） → 4. 配方自动记录 → 5. 存储层写入（CAS去重） → 6. 完成反馈（✓ + 版本ID + 配方摘要 + 去重比）

配方匹配时提示已有版本，可选择复用或强制新建。

### lineage 追溯流程

工程师执行 `big log --lineage <id>` 后沿 derived_from 边回溯：
1. 血缘图查询 → 2. 深度检测（>5层默认截断+提示） → 3. 渲染决策链摘要（ID / 消息 / 生命周期 / 关键参数变更） → 4. 按需展开（`big show` 配方详情 / `big diff` 参数对比 / GUI点击节点）

### checkout 回退流程

工程师执行 `big checkout <id>` 后：
1. 未提交变更检测（有变更→选择提交/暂存/丢弃/取消） → 2. CAS层构建目标文件 → 3. 大规模检测（>10万文件→提示 --subset） → 4. 文件硬链接替换（路径不变内容替换） → 5. 完成反馈（✓ + 文件数 + 大小）

路径零变化，EDA工具打开的文件句柄不受影响。

### promote 晋升流程

PD Lead 执行 `big promote <id>` 后：
1. 显示当前→目标阶段 → 2. 系统校验（配方完整性/验证结果） → 3. Golden操作二次确认 → 4. 生命周期标签更新 + 存储策略切换 → 5. 完成反馈（✓ + 阶段跃迁 + 存储变化描述） → 6. GUI Badge动画过渡

### 跨分支依赖预警流程

工程师在依赖分支 commit 后：
1. 系统检测跨分支依赖 → 2. 标记受影响下游版本 → 3. 触发预警通知（CLI ⚠️ 影响版本数 / GUI 脉冲红高亮） → 4. 下游负责人响应（确认/checkout重跑/忽略留待）

预警为通知而非阻塞，持久化不清除直到确认。

### 旅程共性模式

| 模式 | 描述 |
|------|------|
| 安全网检查 | 破坏性操作前检测当前状态，给出选择而非直接执行 |
| 渐进式披露 | 默认摘要，--verbose/--full/GUI点击按需展开 |
| 确定性反馈 | 每个操作必以 ✓/✗ + 摘要结束 |
| 异步非阻塞 | 长操作不阻塞终端，进度条即时反馈 |
| 预防性验证 | 问题发生前校验（输入完整性/未提交变更/Golden确认） |

### 流程优化原则

1. **最少步骤到达价值** — commit 一条命令完成，无需 staging/add/push
2. **决策点最小化** — 只在不可逆操作（Golden晋升）才要求确认，可逆操作直接执行并可 undo
3. **进度永远可见** — 所有超过 1 秒的操作都有进度指示
4. **错误可操作** — 失败反馈包含具体原因和建议下一步，不是笼统的 error code

## 组件策略

### 设计系统组件

Ant Design Vue 4.x 直接覆盖 BIG GUI 80% 以上的组件需求：

| 核心视图 | 组件 |
|---------|------|
| 版本树 | Tree / DirectoryTree |
| 配方详情 | Descriptions |
| 文件变更列表 | Table |
| 生命周期标记 | Tag / Badge |
| 分支选择 | Select |
| 操作确认 | Modal / Popconfirm |
| 面板切换 | Tabs |
| 进度反馈 | Progress / Spin |
| 预警通知 | Alert / Notification |
| 统计卡片 | Statistic + Card |
| 配置表单 | Form |

### 自定义组件

| 组件 | 用途 | MVP 实现 | Growth 实现 |
|------|------|---------|------------|
| LineageGraph | 血缘链可视化 | Tree 递归渲染 | G6 DAG 图谱 |
| LifecycleTimeline | 阶段流转历史 | — | Timeline + 动画 |
| StorageGauge | 存储水位环形图 | Progress circle | 自定义 SVG |
| DiffPanel | 配方双栏对比 | CLI diff 输出 | GUI 双栏高亮 |
| DsoGroupOverview | 寻优分组全景 | — | Table + 批量操作 |
| TerminalPanel | 内嵌终端 | xterm.js + node-pty | 同左 |

#### LineageGraph

沿 derived_from 边渲染版本决策链。MVP 用 Tree 组件递归渲染，支持节点展开/折叠和生命周期色块；Growth 阶段升级为 G6 力导向/层次布局 DAG，支持缩放/平移/搜索/跨分支链接。节点可 Tab 聚焦、Enter 展开详情。

#### LifecycleTimeline

展示版本从 Exploring→Candidate→Pinned→Golden 的阶段流转。当前阶段脉冲高亮，阶段间标注存储策略变更。Growth 阶段实现阶段跃迁过渡动画。

#### StorageGauge

环形图展示磁盘使用率（中心百分比）+ 生命周期分段占比 + 70% 阈值线。正常青蓝（<70%）、警告橙（70-85%）、危险红（>85%）。点击分段可筛选版本列表。

#### DiffPanel

双栏展示两版本配方差异，差异字段高亮（新增绿、删除红、修改黄）。CLI 模式用统一 diff 格式，GUI 模式用双栏高亮。

#### DsoGroupOverview

寻优分组全景：顶部统计卡（总 case / Top-K / 回收空间）+ 排名表格（Case ID / PPA 得分 / 生命周期 / 大小）。支持批量淘汰/保留操作。

#### TerminalPanel

基于 xterm.js + node-pty 的内嵌终端，支持 ANSI 颜色解析、命令历史、Ctrl+C 中断。

### 组件实施策略

三层架构：
- **基础层**（Ant Design Vue 直出，零定制）：Tree、Table、Descriptions、Tag、Badge、Modal、Tabs、Progress、Notification、Statistic、Form
- **组合层**（组件组合 + 少量逻辑）：StorageGauge、LifecycleTimeline
- **自定义层**（额外架构工作）：LineageGraph（G6）、DiffPanel、DsoGroupOverview、TerminalPanel（xterm.js）

所有自定义组件复用 Ant Design Vue 的 Design Token（色彩、字体、间距），确保视觉一致性。

### 实施路线图

**MVP：** 基础层全部 + LineageGraph（Tree 版）+ StorageGauge（Progress circle）+ TerminalPanel + DiffPanel（CLI diff）
**Growth：** LineageGraph（G6）+ DiffPanel（GUI双栏）+ DsoGroupOverview + LifecycleTimeline
**Vision：** 3DIC 跨分支图谱 + 流水线监控组件 + 自定义面板组件

## UX 一致性模式

### 反馈模式

| 场景 | CLI | GUI |
|------|-----|-----|
| 成功 | ✓ 绿色 + 摘要（≤3行） | 绿色 Toast + 面板刷新 |
| 失败 | ✗ 红色 + 原因 + 建议操作 | 红色 Alert 内联 + 操作按钮 |
| 警告 | ⚠ 黄色 + 风险 + 继续/取消 | 黄色 Modal 确认 |
| 进行中 | 进度条 ██░░ 60% | Progress + Spin |
| 信息 | ℹ 蓝色 + 补充说明 | Notification 5秒消失 |

规则：成功≤3行详情用`--verbose`；失败必须含建议；写操作必有反馈；Toast/Notification不阻断。

### 生命周期标记模式

CLI 格式：`abc1234 [Candidate]`，颜色紧跟；GUI 使用 Badge 右上角/行首。Golden 有★图标。跃迁时 GUI 0.3s Badge 过渡动画。三重传达：颜色+文字+图标。

### 导航与定位模式

CLI 版本ID = GUI 搜索锚点，标识符完全一致。GUI 中 Ctrl+K 命令面板搜索直达。GUI 选中实体对应 URL 状态，支持浏览器前进/后退。GUI 节点悬停显示等效CLI命令。

### 破坏性操作确认模式

可逆操作不确认，不可逆操作必须确认。Golden晋升需输入"GOLDEN"文本确认。确认默认为取消（y/N）。checkout丢弃变更需选择确认。

### 搜索与筛选模式

CLI 默认20条摘要，`--limit`扩展；GUI 模糊匹配实时高亮。过滤器叠加结果实时更新。百万级仓库走索引搜索。

### 加载与空状态模式

空状态必有引导文案+下一步建议。加载>2秒显示进度。骨架屏轮廓匹配实际布局，避免闪烁跳动。

### 设计系统集成规则

自定义组件使用 Ant Design Vue Design Token；间距遵循8px网格；CLI/GUI 语义色值统一；GUI 使用 Ant Design Icons；组件优先级：原生 > 组合 > 自定义。

## 响应式设计与无障碍

### 响应式策略

BIG 仅面向桌面端（CentOS NAS + Electron），无移动端/平板端需求。

| 场景 | 策略 |
|------|------|
| 全高清 1920x1080+ | 三栏全展开，左280px + 中央自适应 + 底部240px |
| 笔记本 1366x768 | 紧凑布局，左240px + 中央自适应 + 底部默认折叠 |
| SSH 终端 | CLI 文本输出自适应终端宽度 |
| 多显示器 | Electron 多窗口——面板可拖出为独立窗口 |

### 断点策略

桌面优先，两个断点覆盖全场景：

| 断点 | 范围 | 行为 |
|------|------|------|
| compact | ≤1280px | 左侧可折叠为图标栏(48px)，底部默认折叠 |
| standard | 1281-1919px | 三栏可见，左240px，底部200px |
| wide | ≥1920px | 左320px，中央可并排，底部280px |

### 无障碍策略

**合规目标：WCAG 2.1 Level AA**

| 维度 | CLI | GUI |
|------|-----|-----|
| 对比度 | ANSI 色 ≥ 4.5:1（深色终端背景） | 所有文本 ≥ 4.5:1；大文本 ≥ 3:1 |
| 键盘导航 | 原生终端操作 | Tab/Enter/Esc/方向键全覆盖 |
| 屏幕阅读器 | 建议系统终端+SR | ARIA labels + role + aria-live |
| 色盲 | 文字标签不依赖颜色 | 颜色+文字+图标三重传达 |
| 焦点指示 | — | 2px 青蓝焦点环 |
| 动效控制 | — | prefers-reduced-motion 关闭过渡 |
| 字体缩放 | 终端原生缩放 | 支持200%缩放不崩坏 |

Golden 色(#FADB14)搭深色文字(#874D00)确保白色背景可读。G6 血缘图叠加隐藏语义 DOM 供 Screen Reader 读取。

### 测试策略

**响应式：** Electron 窗口缩放 + DevTools 多分辨率模拟 + CLI 终端宽度测试 + 200%缩放验证。

**无障碍：** axe-cli 自动化扫描 + 键盘全流程遍历 + NVDA/VoiceOver 测试 + Chrome DevTools 色盲模拟 + WebAIM 对比度逐色验证 + prefers-reduced-motion 验证。

### 实施指南

**响应式：** 左侧面板 CSS resize + min/max-width；底部可折叠 Drawer/Panel；多窗口 Electron BrowserWindow；中央 CSS Grid 布局。

**无障碍：** 语义 HTML（nav/main/aside）；交互元素必有 aria-label；状态变化 aria-live="polite"；G6 图谱叠加 visually-hidden 语义 DOM；CLI 输出 ANSI 标准转义码。
