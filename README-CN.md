# tacit-skills

[English](./README.md) | 简体中文

一套完整的 AI 技能工具集及其配套应用包，覆盖软件开发从初步分析、设计、实现、验证到持久化项目记忆的全过程。

## 概览

本仓库包含 **17 个独立技能**，旨在简化软件开发工作流。

### Grok Bot 舰队

- **[bot_fleet](./bot_fleet/)** — Grok Bot 多智能体舰队的共享技能（密钥、X/XFlux 摘要、IBKR 账本、写作修订、财报/EDGAR 助手、可视化、Nothing 设计）。嵌套包；不属于 tacit Go SOP 闭环。作者：Dr Eggbot。


### 上手与维护

- **[warmup](./warmup/SKILL.md)** — 代码库上手。探索仓库结构、提取 Go 编码约定，并整理为兼容 Claude 的开发规则文件。
- **[scout](./scout/SKILL.md)** — 代码库漂移检测。对比 Git 历史、Go 源码与已保存的约定，识别结构变化、约定偏离和接口修改。
- **[charter](./charter/SKILL.md)** — 记忆同步。根据已批准的 scout 漂移报告更新约定、规则与项目记忆，并压缩历史记录。

### 设计与实现

- **[blueprint](./blueprint/SKILL.md)** — 实现前设计工作流。探索代码库、起草 PRD、制定实施计划，坚持先设计后编码。
- **[builder](./builder/SKILL.md)** — 按规格构建功能。接收 PRD 或实施计划并产出可运行代码。
- **[pivot](./pivot/SKILL.md)** — 处理中途需求变更。把变更记录到 `.claude/amendments/<slug>-r<N>.md`，就地修改 PRD 并提升版本号，同时将现有计划、构建报告和 bailiff 结论标记为过期。它补上了 SOP 所缺少的“第五个动词”。
- **[code-analyze](./code-analyze/SKILL.md)** — 架构代码分析工具，支持项目/API/模块/函数级交互式范围选择、快速/深度模式、框架无关的发现流程，以及由 `tokei` 驱动的指标统计。报告输出到 `.claude/analyses/`。**前置依赖：** `tokei`（[安装说明](https://github.com/XAMPPRocky/tokei#installation)）。

### 验证

- **[bailiff](./bailiff/SKILL.md)** — 规格驱动的验证与契约级测试。检查实现是否符合规格，执行 Go 代码质量检查，并扫描代码树（含 `.claude/`、`.agent/`）中泄露的本机路径、密钥以及未采纳方案的残留注释。
- **[plumb](./plumb/SKILL.md)** — 对比 PRD、计划、构建报告和 bailiff 产物的版本，指出哪些功能的计划、构建或结论已经过期。它是只读传感器，不会修改文件；builder 和 bailiff 会在预检阶段自动调用它。
- **[smoke-client](./smoke-client/SKILL.md)** — 为单个进程内函数或在线 HTTP 端点搭建独立的 Go 冒烟测试客户端。无需启动周边服务即可重放 JSONL 输入，并稳定输出 parsed、results、skipped 和 failures 等 JSONL 产物；dry-run 模式只解码，不发起网络请求。
- **[inquest](./inquest/SKILL.md)** — 在验证结论或部署之后展开调查，包含两种模式：**smoke**（对比 PRD ↔ 代码 ↔ 冒烟结果，判断故障属于代码缺陷、规格缺口、规格过期还是环境问题）和 **triage**（逐项核验 bailiff 报告，限定在问题指向的文件内修复真实问题、驳回误报，并更新报告状态）。不会调用其他技能。

### 事后复盘

- **[distill](./distill/SKILL.md)** — 周期性的跨仓库元审查。读取磁盘上的全部 bailiff 报告，把零散问题抽象为命名明确、反复出现的失效模式和可机械执行的防护规则，保存为带日期的 `bailiff-lessons-YYYY-MM-DD.md`。它只在 SOP 闭环之后运行，是其他技能产物的下游消费者而非依赖；只读取 bailiff 报告，不读取被审计的源码。其他技能不应调用 distill，但 distill 可以引用其他技能的目录（例如 bailiff 的 `references/perf-pitfalls.md`），以保持摘要中的标识符稳定。

### 报告

- **[herald](./herald/SKILL.md)** — 将 bailiff、builder 或 scout 的 Markdown 报告渲染为采用 nothing-design 设计语言的单文件 HTML。通过内联 CSS 复刻 `@vibes/nothing-ui` token，无需 React、构建步骤或远程资源；支持单报告和多报告合集模式。

### 实用工具

- **[json-to-schema](./json-to-schema/SKILL.md)** — 将示例 `.json` 文件转换为 draft-07 JSON Schema。能够推断类型、把共享子结构提取为 `$ref` 定义，并添加日期时间、HTML、签名 URL 等语义标注；附带验证脚本。

### 长期记忆：Honcho 套件

三个 Honcho 技能共同构成完整的记忆闭环，而不是一组互不相关的命令：管理服务、保存持久上下文，并在后续工作中取回正确的上下文。

- **[honcho-manage](./honcho-manage/SKILL.md)** — 端到端运维自托管 Honcho sidecar：引导并构建 Docker Compose 服务栈、等待服务就绪、检查健康状态与会话详情、切换作用域，以及跨全部 API 分页安全清理记忆。
- **[honcho-remember](./honcho-remember/SKILL.md)** — 将用户偏好、项目事实、决策和长期指令转换为经过验证的原子化观察，并保存到当前会话。
- **[honcho-recall](./honcho-recall/SKILL.md)** — 通过近期记忆列表或语义搜索取回已保存知识，并始终限定在当前会话内，防止不同项目的上下文相互串扰。

如需完全自托管的服务栈，建议将这些技能与 **[Laucr/honcho](https://github.com/Laucr/honcho)** 配合使用。该 Honcho 分支包含自托管的嵌入服务，让记忆存储和嵌入推理都处于你的掌控之下，同时保留相同的“管理 → 记忆 → 召回”工作流。

再配合 [`.pkg/memboard`](./.pkg/memboard/) 中的 **Memboard**，这套方案既能提供面向 Agent 的原生工作流，也能提供便于人工浏览、搜索和删除记忆的 Web 控制界面。

## 快速开始工作流

典型开发流程如下：

```
0. warmup       → 熟悉代码库并提取约定
1. blueprint    → 生成 PRD 和实施计划
2. builder      → 按规格实现（plumb 预检）
3. bailiff      → 验证实现是否符合规格（plumb 预检）
4. scout        → 变更落地后检测约定漂移
5. charter      → 将批准的漂移更新写入记忆（scout 的配套技能）
6. code-analyze → 记录架构（可选）
7. herald       → 将上述报告渲染为可分享的 HTML（可选）
```

完成闭环后，定期运行：

```
*. distill      → 汇总磁盘上的全部 bailiff 报告，生成带日期的经验文件。
                  仅用于复盘，位于 SOP 下游，不参与 SOP 内部流程。
```

当实现过程中规格发生变化时：

```
*. pivot        → 提升 PRD 版本、记录变更，并将计划/构建/bailiff 标记为过期
*. plumb        → 只读检测：哪些功能产物已经过期？
```

当真实环境与规格不符，或 bailiff 留下未解决的问题时：

```
*. smoke-client → 为一个函数或 HTTP 端点搭建 JSONL 驱动的测试工具；
                  dry-run 验证输入，在线运行则产出
                  parsed/results/skipped/failures 证据。
*. inquest      → smoke 模式：三方对比（PRD 怎么说 ↔ 代码怎么做 ↔ 冒烟看到了什么），
                  判断代码缺陷、规格过期、规格缺口或环境问题。
                  triage 模式：核验每个 bailiff 发现、修复真实问题、
                  驳回其余问题并更新报告状态。自身不会运行 pivot 或 bailiff。
```

Blueprint、builder 和 bailiff 通过**上下文账本**自动交换信息：blueprint 的决策会传递给 builder，builder 的偏离会传递给 bailiff，而 bailiff 的结论会反馈到下一轮 blueprint。每个产物的 frontmatter（PRD 的 `version`、计划的 `prd_version`、构建/bailiff 的 `prd_version` 和 `plan_version`）是 `plumb` 与 `pivot` 在需求演进过程中保持整条链路可信的依据。

长期记忆工作流：

```
1. honcho-manage   → 设置并管理记忆 sidecar
2. honcho-remember → 保存偏好、决策和上下文
3. honcho-recall   → 取回已保存知识
```

Honcho 套件会首先从 `HONCHO_HOME` 解析其主目录，其次使用当前项目（Compose 根目录或最近的 `.claude/honcho/`），最后回退到 Honcho 全局约定 `~/.honcho/`。因此，同一套安装既能保存跨项目共享的偏好，也能维护彼此隔离的项目会话。

## 配套应用包（`.pkg`）

技能是面向 Agent 的接口；`.pkg/` 则存放让特定技能形成完整产品体验的可选软件。这些应用包被刻意放在隐藏的顶层目录下，避免编码 Agent 的技能加载器把它们误认为独立技能。

### Memboard

**[Memboard](./.pkg/memboard/)** 是 Honcho 记忆套件的 Web 配套应用。它把技能所使用的同一套 Honcho v3 API 转换为紧凑的控制面板，用户可以：

- 查看服务健康状态和记忆数量；
- 浏览全部记忆或按会话过滤；
- 执行语义搜索；
- 删除单条记忆，或经确认后清空整个会话；
- 通过 Vite 在本地使用，也可以打包为轻量容器。

Memboard 是一个独立的 Vite + React 应用。默认情况下，其开发服务器会把 `/api` 代理到 `http://localhost:8787` 上的 Honcho；工作区、观察者、被观察者、基础路径和 API 地址均可通过应用源码中记录的 `VITE_*` 与 `HONCHO_BASE_URL` 环境变量进行配置。

## 跨技能记忆

各技能通过目标项目中的 `.claude/memory/` 文件共享上下文：

```
.claude/memory/
├── current.md              # 代码库状态快照（提交、结构、已知异味）
├── context-ledger.md       # 跨技能上下文交换（约 35 行，覆盖式写入）
└── history/
    ├── drift/              # Scout 漂移报告（由 charter 压缩）
    ├── ledger-archive.md   # 账本归档
    └── smells-archive.md   # 异味归档
```

- **`current.md`** — 由 scout/charter 维护，记录最近已知的提交哈希和代码库状态。
- **`context-ledger.md`** — 由 blueprint、builder、bailiff 和 inquest 维护。每个技能完成时会覆盖自己的区段，而非持续追加，因此文件始终保持精简。Scout 通过它区分计划内变更与意外漂移。
- **`history/`** — charter 会压缩旧的漂移报告和账本归档，防止历史记录无限增长。

完整协议：[charter/references/context-ledger-spec.md](./charter/references/context-ledger-spec.md)

## 安装

使用仓库自带的安装器，将技能接入一个或多个编码 CLI 的厂商目录：

```bash
bash .scripts/install.sh                                     # 交互式首次安装/同步
bash .scripts/install.sh --dry-run                           # 预览操作，不做修改
bash .scripts/install.sh --yes --wired claude --groups core  # 非交互模式
bash .scripts/install.sh --enable-group vec-memory           # 稍后添加长期记忆技能
bash .scripts/install.sh --check                             # 若重复运行无需操作则返回 0
bash .scripts/install.sh --uninstall                         # 卸载全部内容并删除配置
```

默认情况下，安装器会把每个技能目录以**符号链接**方式接入 `<vendor>/skills/`。因此，在本仓库执行 `git pull` 后，技能的*内容*变更会立即传播到所有已接入的厂商。重新运行 `install.sh` 主要用于同步技能*集合*的变化（上游新增或删除技能），以及重新生成策略文件和 Agent 包装器。在不支持符号链接的文件系统上可使用 `--mode copy`；复制模式下，重新运行也会更新技能内容，因此 `installer.yaml` 中记录的已安装版本会参与判断。

`--check` 会报告重复运行将带来的变化：符号链接模式下检查损坏或缺失的链接，复制模式下检查版本漂移，两种模式都会检查策略与 Agent 文件冲突。退出码 0 表示已同步，无需操作；非 0 表示再次运行可解决问题。

除技能外，安装器还会复制两类文件：

- **策略文件**（`CLAUDE.md`、`dev-routes.md`）会复制到各厂商的 `policy_dir`。启用的分组决定使用哪个版本：仅 core 时使用 `.policy/core/`，启用 `vec-memory` 时使用 `.policy/vec-memory/`。如果目标文件没有 `<!-- tacit-skills policy v1` 标头，则视为外部文件并拒绝覆盖；传入 `--force` 后，安装器会先将其移动到 `.tacit-backup`。
- **Agent 包装器**（`.agents/*.md`）会复制到各厂商的 `agents_dir`。调用方可借此通过**子 Agent 传输**调用技能，例如 `Agent(subagent_type: "bailiff", ...)`，并只接收单行结果，而推理过程保存在磁盘报告中。可用 `--no-agents` 跳过，用 `--agents-dir NAME=PATH` 覆盖路径，或将某个厂商指向 `~/.claude/agents/`。

已知厂商默认值：

| 厂商 | 技能目录 | 策略目录 | Agent 目录 |
|---|---|---|---|
| claude | `~/.claude/skills` | `~/.claude` | `~/.claude/agents` |
| codex | `~/.codex/skills` | `~/.codex` | `~/.codex/agents` |

可在交互提示中输入 `[a]` 添加自定义厂商，也可重复传入 `--add-vendor NAME=PATH`。使用 `--policy-dir NAME=PATH` 设置策略目录，使用 `--agents-dir NAME=PATH` 设置 Agent 目录（PATH 为空表示跳过该类文件）。执行 `bash .scripts/install.sh --help` 可查看全部参数。

每次安装、升级或卸载都会向 `~/.local/state/tacit-skills/install.log` 追加一条 JSON Lines 记录。

### 发布版本

维护者通过以下命令创建版本标签：

```bash
bash .scripts/release.sh patch          # v0.3.0 -> v0.3.1（带注释标签，不推送）
bash .scripts/release.sh minor --push   # 创建标签并推送到远端
bash .scripts/release.sh --dry-run patch
```

除非传入 `--force`，预检会拒绝在工作树不干净或 HEAD 已有标签时创建标签。本项目不维护 CHANGELOG.md；带注释标签中会记录两个版本之间的 `git log --oneline`。

### 编辑策略文件

`.policy/` 保存标准策略文件的两个版本：

- `.policy/core/` — 基础说明，不包含长期记忆内容。
- `.policy/vec-memory/` — 在同一套说明中加入长期记忆规则和路由。目前由 `honcho-*` 技能组提供能力；`vec-memory` 采用能力导向命名，因此未来替换底层工具时无需改名。

安装器根据启用的分组选择版本（`--groups core,vec-memory` 使用 `vec-memory`，否则使用 `core`）。两套文件的公共内容必须同步维护，而差异部分正是它们存在的意义。这里没有 lint 步骤，两套 `.md` 文件的 `diff` 就是审查界面。

兼容旧参数：`--groups honcho` 和 `--enable-group honcho` 仍然可用，并会静默映射到 `vec-memory`。

## 配置

技能自身的配置文件（即各技能 Setup 阶段写入的 YAML/JSON）统一存放在一个 XDG 风格的根目录下：

```
~/.config/tacit-skills/<skill-name>.yaml
```

当前已注册：

- `~/.config/tacit-skills/installer.yaml` — 安装器状态，包括已接入厂商、启用分组和最后安装版本。由 `.scripts/install.sh` 写入；只要遵循扁平结构（版本标记参见文件中的 `# tacit-skills installer.yaml v1` 标头），即可安全地手动编辑。
- `~/.config/tacit-skills/herald.yaml` — herald 的输出、索引和 Mermaid 配置。首次运行时自动创建；旧版 `~/.config/.herald.yaml` 会自动迁移。

运行时配置解析顺序：

1. 环境变量
2. `~/.config/tacit-skills/<skill-name>.yaml`（技能自身配置）
3. `.claude/settings.json`（项目级运行环境设置）
4. `~/.claude/settings.json`（用户级运行环境设置）

> Honcho 技能（`honcho-manage`、`honcho-recall`、`honcho-remember`）有意使用 `~/.honcho/`。这是 Honcho 自身的产品约定，并非 tacit-skills 配置，因此不会迁移到其他位置。

### 从旧目录结构迁移

如果你从曾将配置写入其他位置的旧版 tacit-skills 升级（例如 `~/.config/.herald.yaml`），请运行一次自带的迁移器：

```bash
python .scripts/migrate-configs.py            # 执行迁移
python .scripts/migrate-configs.py --dry-run  # 预览将要移动的内容
python .scripts/migrate-configs.py --check    # 若已完成迁移则返回 0
```

该脚本具备**幂等性**，迁移完成后再次运行不会执行任何操作。如果同一技能的新旧配置文件同时存在，迁移器会拒绝覆盖，并打印两个路径供你手动处理。各技能的脚本（例如 `herald/scripts/render.py`）也会在首次运行时执行相同迁移，因此独立迁移器主要用于“一次完成全部迁移”或批量升级。

如需登记新的旧路径映射，请向 `.scripts/migrate-configs.py` 中的 `LEGACY_MAPPINGS` 追加一个元组。

## 技能编写约定

任何需要在用户文件系统中**持久化内容**的新技能都必须遵守以下约束：

1. **统一根目录下，每个技能一个文件。** 只能写入一个路径：`~/.config/tacit-skills/<skill-name>.<ext>`。结构化配置使用 `.yaml`，确实需要 JSON 时才使用 `.json`，供 shell 加载的环境变量使用 `.env`。不要创建技能专属子目录，也不要写入仓库中的技能目录；仓库目录是只读产物，升级时会被覆盖。
2. **不要写入 `$CWD`、`~/.claude/` 或任意 `~/<dotdir>/`。** 唯一允许的例外是技能封装了拥有自身配置根目录的第三方产品，例如 Honcho 的 `~/.honcho/`。此时必须在 `SKILL.md` 和 README 的“配置”章节中明确说明，并且不要在 `tacit-skills/` 下创建镜像配置。
3. **以合理默认值自动创建。** 首次运行时，如果 `~/.config/tacit-skills/<skill>.<ext>` 不存在，应写入文档化的默认值（通过 `mkdir -p` 创建父目录），并在 stderr 中告知用户文件位置，不能让用户猜测配置存放在哪里。
4. **配置解析尽量零依赖。** 优先使用标准库解析精简的 `key: value` YAML 子集（参见 `herald/scripts/render.py:load_config`）；只有 schema 确实需要嵌套或列表时才引入完整 YAML 解析器。JSON 可直接使用标准库 `json`。
5. **位置变更必须提供迁移路径。** 如果后续版本重命名或移动配置文件，应在 `.scripts/migrate-configs.py` 的 `LEGACY_MAPPINGS` 中登记旧路径到新路径的映射，并在技能脚本中加入一次性自动迁移逻辑（参考 `herald/scripts/render.py` 中的 `LEGACY_CONFIG_PATH` 与 `ensure_config()` 模式），绝不能静默破坏现有用户配置。
6. **记录路径。** 每个持久化配置的技能都必须在其 `SKILL.md` 的 Setup 章节中注明准确路径，并在 README 的“配置/当前已注册”列表中同步更新。
7. **配置文件不得包含密钥。** Token、密码、API Key 等必须放在环境变量中，或通过用户管理的 `auth.env_file` 引用。`~/.config/tacit-skills/` 下的 YAML/JSON 应当可以安全备份到个人 Git 仓库而不泄露凭据。

无需持久化任何内容的技能（大多数技能，包括 `pivot`、`bailiff`、`blueprint`、`builder`、`charter`、`code-analyze`、`distill`、`inquest`、`json-to-schema`、`plumb`、`scout`、`smoke-client` 和 `warmup`）不应在 `~/.config/tacit-skills/` 下创建文件。能保持无状态时就保持无状态。

## 仓库布局

每个技能都位于仓库根目录下的独立目录中，包含 `SKILL.md`，并可选包含 `scripts/` 和 `references/` 子目录。**Claude Code 技能加载器会把每个非隐藏的顶层目录都视为候选技能**，因此仓库级工具统一放在隐藏目录中：

- `.scripts/` — 仓库级工具（`install.sh`、`release.sh`、`migrate-configs.py`、`test-install.sh`）
- `.policy/` — 策略变体（`core/`、`vec-memory/`），由安装器写入各厂商的 `policy_dir`
- `.agents/` — Agent 包装器（`bailiff.md`、`inquest.md`），由安装器写入各厂商的 `agents_dir`
- `.pkg/` — 与特定技能套件配套的可选应用和可分发软件包；当前包含 Honcho 套件的 Memboard Web UI
- `.claude/` — 运行环境状态与权限配置
- `bot_fleet/` — Grok Bot 多智能体舰队的有意嵌套技能包（一对顶层一技能约定的例外）；详见 [bot_fleet/README.md](./bot_fleet/README.md)

除非新目录确实是包含 `SKILL.md` 的技能，或像 `bot_fleet/` 这样有文档说明的有意嵌套包，否则不要添加新的非隐藏顶层目录。
