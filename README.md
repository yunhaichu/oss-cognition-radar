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

```bash
python3 radar.py --archive-show langchain-ai/langgraph --db data/radar.sqlite
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
- 治理模式
- 可复用思想
- 不可复制条件
- claim / evidence stable IDs
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
- `track_score`

SQLite 当前会保存：

- `runs`
- `repository_snapshots`
- `repository_health_snapshots`
- `evidence_items`
- `claims`

归档模式会基于这些表提供三类本地查询：

- `--archive-list`：按最新快照列出已归档项目，支持 track 和最低 track score 过滤
- `--archive-search TEXT`：搜索 repository 元数据、claims 和 evidence 文本
- `--archive-show owner/name`：优先展示最新 deep dossier，没有 deep 快照时回退到最新 discovery 快照

`star_growth` 只有在数据库里存在对应窗口附近的历史快照时才会显示真实增量；否则会标记为 `insufficient history`。当前匹配窗口为：1d 使用 1–2 天前快照，7d 使用 7–10 天前快照，30d 使用 30–45 天前快照。这避免把几分钟前的重复运行或过旧快照误当作 1 天增长。

`repository.health` 是第一版健康度信号，包含 GitHub Search/API 可稳定获取的样本字段。`release_count_365d_sample` 和 `top_contributor_count_sample` 是 API 返回样本，不应当被当成完整全量统计。

`track_score` 会先把项目归入 `agent`、`developer_tools`、`local_first`、`protocol` 或 `general`，再使用不同权重合成 `momentum`、`collaboration`、`release`、`governance`、`evidence`、`ecosystem` 六类信号。发现模式还没有深度 evidence，因此 evidence 信号会偏低；深度分析后会更适合作为档案评分。

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

- 在 SQLite 归档查询基础上做浏览器 dashboard / 知识库视图
