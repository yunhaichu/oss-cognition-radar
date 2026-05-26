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

如果设置了 `GITHUB_TOKEN`，API 限额会更高：

```bash
export GITHUB_TOKEN=ghp_xxx
```

## 当前输出

发现模式会输出：

- 项目基础信息
- star/day 近似增长信号
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
- fake-star 风险与复核建议
- 可追溯证据链

JSON 输出会包含：

- `repository`
- `claims`
- `evidence`
- `query` 或 `method_boundary`

SQLite 当前会保存：

- `runs`
- `repository_snapshots`
- `evidence_items`
- `claims`

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

- 基于 SQLite 快照计算 1d / 7d / 30d 真实 star 增长
- 抓取高评论 issue、最近合并 PR、release cadence、contributors
- 为不同项目类型建立分轨评分：agent、developer tools、local-first、protocol
- 基于 JSON dossier 做仪表盘或知识库
