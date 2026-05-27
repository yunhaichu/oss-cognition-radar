# OSS Cognition Radar

从热门开源项目的公开工程痕迹中，反向提炼开发者的认知模式、设计取舍和治理方式。

这个项目不把 GitHub star 当成质量本身。star 只是发现候选项目的入口；真正的分析对象是 README、docs、examples、release、issue、PR、治理文件等可观察、可复核的工程证据。

## 核心定位

```text
不是：GitHub 热榜网站
而是：开源项目认知模式解剖器
```

它尝试回答：

- 作者如何重新定义问题？
- 项目的关键抽象是什么？
- 架构边界在哪里？
- 真正复杂的地方藏在哪里？
- 失败、恢复、兼容性和维护成本如何被处理？
- 治理方式体现了什么长期判断？
- 哪些思想可迁移，哪些势能不可复制？

## 使用

发现近期高信号候选项目：

```bash
python3 radar.py \
  --days 30 \
  --limit 20 \
  --min-stars 100 \
  --topic ai \
  --output reports/latest.md \
  --json-output reports/latest.json
```

深度分析单个项目：

```bash
python3 radar.py \
  --repo langchain-ai/langgraph \
  --output reports/langgraph.md \
  --json-output reports/langgraph.json
```

默认会把每次运行写入 SQLite：

```text
data/radar.sqlite
```

如果只想生成文件，不写数据库：

```bash
python3 radar.py --repo langchain-ai/langgraph --no-db
```

查询已经沉淀到 SQLite 的本地档案，不再访问 GitHub API：

```bash
python3 radar.py --archive-list --db data/radar.sqlite --limit 20
```

```bash
python3 radar.py --archive-search durable --db data/radar.sqlite --limit 10
```

`--archive-search` 会按需维护 SQLite FTS5 搜索索引，并输出 relevance backend、score、命中的文档数量和 source types。索引覆盖 repository、claims、claim gaps、evidence acquisition bindings、evidence 和 Repository Cognition Profile；若运行环境不支持 FTS5，或 FTS5 对中文片段没有命中，会自动回退到 `LIKE` 搜索。

```bash
python3 radar.py --archive-show langchain-ai/langgraph --db data/radar.sqlite
```

聚合已经归档的 evidence-to-claim bindings，观察跨项目重复出现的 claim-gap 修补模式：

```bash
python3 radar.py --archive-patterns --db data/radar.sqlite --limit 20

python3 radar.py --archive-patterns \
  --db data/radar.sqlite \
  --archive-signal-group drift \
  --limit 20
```

导出 profile path route detail 研究材料，可按设计动作、证据路线、仓库、confidence source 和 signal group 筛选，并同时保存 Markdown / JSON：

```bash
python3 radar.py \
  --archive-route-selectors \
  --db data/radar.sqlite \
  --archive-output reports/route-selectors.md \
  --json-output reports/route-selectors.json

python3 radar.py \
  --archive-route-detail \
  --db data/radar.sqlite \
  --profile-path-move 架构边界设计 \
  --profile-path-route source_entrypoint \
  --profile-path-repo openclaw/openclaw \
  --archive-output reports/route-detail.md \
  --json-output reports/route-detail.json

python3 radar.py \
  --archive-route-detail \
  --db data/radar.sqlite \
  --profile-path-preset reports/route-selectors.json \
  --archive-output reports/route-detail-presets.md \
  --json-output reports/route-detail-presets.json
```

自动校准 archive 中的 acquisition binding confidence。该步骤只使用归档内信号，会根据跨项目重复性、同仓库跨版本稳定性、release/issue/PR 时间序列、证据类型、证据极性、稳定链接和关键词稀疏度等归档信号生成 `archive_auto_v1` confidence。`archive_auto_v1` 会把分数拆成 heuristic 基础分、跨项目重复分、时间序列分、证据质量分和惩罚项，避免热门项目的绑定全部饱和为 high：

```bash
python3 radar.py \
  --archive-auto-calibrate \
  --db data/radar.sqlite \
  --archive-output reports/archive-auto-calibration.md \
  --json-output reports/archive-auto-calibration.json
```

归档查询默认输出到终端；如需保存 Markdown：

```bash
python3 radar.py \
  --archive-search governance \
  --db data/radar.sqlite \
  --archive-output reports/archive-search.md \
  --json-output reports/archive-search.json
```

归档查询也支持按分轨过滤：

```bash
python3 radar.py --archive-list --archive-track agent --min-track-score 50
```

生成本地浏览器 dashboard：

```bash
python3 radar.py \
  --archive-dashboard reports/archive-dashboard.html \
  --db data/radar.sqlite \
  --limit 200
```

也可以同时导出 dashboard 使用的 JSON：

```bash
python3 radar.py \
  --archive-dashboard \
  --db data/radar.sqlite \
  --json-output reports/archive-dashboard.json
```

如果设置了 `GITHUB_TOKEN`，API 限额会更高：

```bash
export GITHUB_TOKEN=ghp_xxx
```

## 当前输出

发现模式会输出：

- 项目基础信息
- star/day 近似增长信号
- 基于 SQLite 历史快照的 1d / 7d / 30d star 增长
- Dossier ID
- repository health：180 天 merged PR / closed issue、open PR、release cadence 样本、contributors 样本
- track score：按 agent / developer tools / local-first / protocol / general 分轨评分
- fork、issue、topic 等基础指标
- 初步 fake-star 风险提示
- 深度分析命令提示

深度模式会输出：

- 方法边界
- 项目档案
- 领域
- 作者如何重新定义问题
- 关键抽象
- 架构边界
- 复杂度藏处
- 实现层复核线索
- 治理模式
- 可复用思想
- 不可复制条件
- claim / evidence stable IDs
- claim 模板、推断依据、边界/反向证据
- claim support coverage：区分叙事、发布/协作、源码、测试/benchmark、配置支撑
- claim gap report：优先列出高价值但支撑薄弱的判断，并给出下一步证据采集建议
- targeted evidence acquisition：按 gap 缺口自动补采源码、测试、benchmark、配置、release、issue/PR 证据
- evidence type、polarity、signal tags
- repository health
- track score
- fake-star 风险与复核建议
- 可追溯证据链

JSON 输出会包含：

- `repository`
- `claims`
- `evidence`
- `query` 或 `method_boundary`
- `star_growth`
- `repository.health`
- `dossier_id`
- `claim_id`
- `evidence_stable_ids`
- `counter_evidence_ids`
- `counter_evidence_stable_ids`
- `template`
- `rationale`
- `support_coverage`
- `claim_gap_report`
- `evidence_acquisition`
- `evidence_type`
- `polarity`
- `signal_tags`
- `track_score`

SQLite 当前会保存：

- `runs`
- `repository_snapshots`
- `repository_health_snapshots`
- `evidence_items`
- `evidence_acquisition_bindings`
- `claims`
- `archive_search_fts`
- `archive_search_meta`

归档模式会基于这些表提供五类本地查询：

- `--archive-list`：按最新快照列出已归档项目，支持 track 和最低 track score 过滤
- `--archive-search TEXT`：用 SQLite FTS5 搜索 repository 元数据、claims、claim gaps、evidence acquisition bindings、evidence 和 Repository Cognition Profile 文本，并返回 relevance 信息
- `--archive-show owner/name`：优先展示最新 deep dossier，没有 deep 快照时回退到最新 discovery 快照；存在跨项目语义模式时会同时显示该仓库的 Repository Cognition Profile
- `--archive-patterns`：聚合最新 deep dossiers 中的 evidence acquisition bindings，按 claim 字段和缺口证据层输出跨项目重复模式、例子仓库和 evidence
- `--archive-route-detail`：批量导出 profile path route detail，下钻到具体设计动作、证据路线、仓库样例、path/pattern ID 和 evidence stable ID
- `--archive-route-selectors`：列出可用于 `--archive-route-detail` 的 design move、evidence route 和 repository selector 候选，并在 JSON 中附带 `route_detail_selector_preset_bundle_v1`
- `--profile-path-preset PATH` / `--profile-path-preset-id ID`：用于 `--archive-route-detail`，从 selector preset bundle 批量运行 route detail 导出；可用 preset ID 选择其中一组或多组 selector，导出前会生成 `route_detail_preset_validation_v1` 检查摘要
- `--archive-signal-group GROUP`：用于 `--archive-patterns` / `--archive-dashboard` / `--archive-route-detail` / `--archive-route-selectors`，按自动 confidence signal group 过滤，例如 `time_series`、`drift`、`pattern`、`evidence`
- `--archive-auto-calibrate`：按 archive 内部信号自动重算 acquisition binding confidence，并重建 archive search index
- `--archive-dashboard [PATH]`：生成一个可直接打开的静态 HTML dashboard，包含搜索、track 过滤、confidence source 过滤、最低分过滤、跨项目 patterns、项目详情、claims、claim gaps、evidence acquisition bindings、route detail selectors 和 evidence 摘要

`star_growth` 只有在数据库里存在对应窗口附近的历史快照时才会显示真实增量；否则会标记为 `insufficient history`。当前匹配窗口为：1d 使用 1–2 天前快照，7d 使用 7–10 天前快照，30d 使用 30–45 天前快照。这避免把几分钟前的重复运行或过旧快照误当作 1 天增长。

`repository.health` 是第一版健康度信号，包含 GitHub Search/API 可稳定获取的样本字段。`release_count_365d_sample` 和 `top_contributor_count_sample` 是 API 返回样本，不应当被当成完整全量统计。

`track_score` 会先把项目归入 `agent`、`developer_tools`、`local_first`、`protocol` 或 `general`，再使用不同权重合成 `momentum`、`collaboration`、`release`、`governance`、`evidence`、`ecosystem` 六类信号。发现模式还没有深度 evidence，因此 evidence 信号会偏低；深度分析后会更适合作为档案评分。

深度 dossier 会把 evidence 标成更细的类型和极性：

- `evidence_type`：例如 `positioning`、`governance`、`boundary`、`source_entrypoint`、`test_surface`、`benchmark`、`configuration`、`release_delta`、`user_friction`、`implementation_change`
- `polarity`：`supporting`、`boundary`、`negative`
- `signal_tags`：例如 `abstraction`、`complexity`、`recoverability`、`governance`、`performance`、`implementation`、`test_strategy`、`configuration`

claim 现在会记录 `template`、`rationale` 和 `support_coverage`，并把边界/反向证据放到 `counter_evidence_ids`。这让报告更像可审查的研究笔记，而不是单向总结。

`support_coverage` 会按每条 claim 直接引用的 evidence 计算支撑层级：

- `narrative_only`：主要由 README、文档或治理文本支撑
- `engineering_trace`：已有 release、issue、PR 等协作/发布痕迹支撑
- `source_backed`：已有源码入口证据支撑
- `validation_backed`：已有测试或 benchmark 证据支撑
- `source_and_validation`：同时有源码和测试/benchmark 支撑
- `configuration_backed`：主要由配置、CI、package metadata 等支撑

`claim_gap_report` 会基于 claim 的价值权重和支撑薄弱程度排序，优先提示哪些判断需要补源码、测试、benchmark、配置、release 或 issue/PR 证据。它是从 claim 当前证据派生出来的复核清单，不会伪装成新的事实来源。

深度模式现在会执行两阶段采样：先用初始 evidence 生成 claims 和 gap report，再根据具体 claim 字段、缺口层和 claim 关键词重排候选源码、测试、benchmark、配置、release、issue/PR，最后用扩展后的 evidence 重建 claims。`evidence_acquisition` 会记录请求的缺口层、新增证据数、新增 evidence ID、目标 claim 字段和 evidence-to-claim bindings；这些绑定会写入 SQLite，并在 `--archive-show` 与 dashboard 中显示每条新增证据补强了哪个 claim gap。

每条 acquisition binding 现在还会带第一版 `binding_confidence`：

- `score`：0–100 的启发式可靠度分数
- `label`：`low`、`medium` 或 `high`
- `calibration`：原始分数为 `heuristic_v1`；运行 `--archive-auto-calibrate` 后有效分数会变为 `archive_auto_v1`
- `signals`：分数来自哪些可解释信号，例如是否命中目标缺口层、证据层是否匹配、跨项目重复、同仓库跨版本稳定、release/issue/PR 活跃趋势、关键词命中和是否有稳定 artifact URL
- `signal_breakdown`：把原始信号自动分组为 `time_series`、`drift`、`pattern`、`evidence`、`calibration` 等可读维度；`--archive-show` 和 dashboard 详情页会直接展示这些分组
- `source`：`heuristic` 或 `auto`，dashboard 可按该来源过滤

自动校准不会删除原始 heuristic 分数。应用校准后，归档读取会把 `archive_auto_v1` 作为有效 confidence，同时保留 `heuristic` 子字段，方便比较自动归档信号和原始规则信号。校准报告会输出自动 confidence 的范围、label 分布和分数组件，便于判断 high/medium/low 是否真正拉开。

`--archive-patterns` 的 `pattern_score` 现在会同时考虑重复度、平均绑定可靠度和 `signal_breakdown` 的结构分。含有 `time_series`、`drift`、`pattern`、`evidence` 等自动信号的模式会在 JSON、Markdown 和 dashboard 中暴露 `signal_group_score`、`signal_groups` 和 `signal_labels`，并可用 `--archive-signal-group` 或 dashboard 的 Signal group 过滤器筛选。

patterns 现在会先做 `semantic_v1` 归并：claim 字段会归一到问题重定义、关键抽象、架构边界、复杂度管理、治理设计等认知类别；缺口证据层会归一到实现/验证、配置/流程、演化/协作、叙事/定位等证据族。JSON、Markdown 和 dashboard 会同时保留 `raw_fields`、`raw_missing_layers` 和 `raw_missing_layer_labels`，因此聚合不会切断原始证据链。

`--archive-patterns` 还会从 signal-ranked semantic patterns 自动派生 `cognition_summaries`。每条摘要包含稳定 `summary_id`、认知动作类别、可迁移规则、证据依据、自动复核动作、置信度、原始字段/证据层分布和支撑 patterns，用于把“哪些 claim-gap 修补模式反复出现”提升为“哪些可观察设计/认知动作反复出现”。该摘要完全来自 archive evidence 和自动信号。

系统还会从 `semantic_v1` patterns 自动派生 `repository_cognition_profiles`。每个仓库画像会显示该项目最强体现的跨项目设计动作、证据族、原始 claim 字段/证据层分布、支撑 semantic patterns 和 evidence examples；`--archive-show` 和 dashboard 的仓库详情页会直接展示 Repository Cognition Profile，`--archive-search` 和 dashboard 搜索也会纳入画像内容。CLI 搜索和 dashboard 仓库详情都会输出 profile-to-claim/evidence explanation paths，把设计动作连接到具体 claim gap、采集原因和 evidence stable ID，并按设计动作、缺口层和 evidence type 汇总 path-level 统计。`--archive-patterns` 和 dashboard 还会输出 `repository_cognition_profile_path_comparisons`，按同一设计动作跨仓库比较不同 claim gap layer 与 evidence type 组成的证据路线；dashboard 可以继续按设计动作、证据路线和仓库下钻这些 comparisons，并在 route detail 面板中展开完整仓库样例、confidence 信号和 evidence stable ID。route detail 面板和 `--archive-route-detail` 都可以按当前过滤范围导出 `route_detail_drilldown_v1` JSON 或 Markdown，把 evidence route、仓库样例、path/pattern ID 和 evidence stable ID 保存为可复用研究材料；`--archive-route-selectors` 和 dashboard JSON 都输出同一版 `route_detail_selectors_v1`，列出批处理可用的设计动作、证据路线和仓库 selector；selector JSON 和 dashboard route detail JSON 都会附带 `route_detail_selector_preset_bundle_v1`，可由 `--profile-path-preset` 直接批量运行 route detail 导出；preset 批处理会先输出 `route_detail_preset_validation_v1`，汇总 ready/unmatched preset、重复 ID 和预计 route/example 数；dashboard 的设计动作、证据路线和仓库下钻选项会优先使用该 selector payload，并把 selector values 纳入搜索匹配；同一 dashboard 过滤状态会写入 URL hash，Permalink 可以直接恢复搜索、track、confidence、signal、score、设计动作、证据路线和仓库范围。

实现层证据会从 Git tree 中限量抽取：

- 核心源码入口：`src`、`lib`、`packages`、`pkg`、`crates` 等目录中的主要源码文件
- 测试面：`tests`、`__tests__`、`*_test.*`、`*.spec.*` 等
- benchmark：`benchmark`、`benchmarks`、`bench` 等
- 配置面：`pyproject.toml`、`package.json`、`Cargo.toml`、`go.mod`、CI/workflow 等

## 方法原则

1. **证据优先**
   每条判断都应尽量回到公开 GitHub 工程痕迹。

2. **star 降权**
   star 是兴趣信号，不是质量代理。后续会加入真实增长快照、fork/PR/contributor 联合观察和异常增长惩罚。

3. **分析公共行为，不猜私密动机**
   本项目只归纳公开可见的工程模式，不声称证明作者的完整心理本质。

4. **从项目行为反推设计思想**
   真正有价值的不是“项目很火”，而是它如何定义问题、隐藏复杂度、暴露抽象、组织贡献和处理失败。

## 下一步

- 将 route detail selector 列表接入 dashboard 下钻控件的数据导出，统一 CLI 和浏览器可见 selector 结构
