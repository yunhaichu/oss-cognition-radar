# GitHub Project Radar

一个从零开始的 GitHub 热门项目雷达。它不追踪“人说了什么”，而是看开发者正在做什么：近期活跃、增长快、设计表达清楚的开源项目。

第一版只依赖 Python 标准库，通过 GitHub REST API 抓取最近创建且 star 较高的项目，计算一个简单的热度/质量分数，并生成 Markdown 报告。

## 使用

```bash
python3 radar.py --days 30 --limit 20 --min-stars 100 --output reports/latest.md
```

可选参数：

```bash
python3 radar.py \
  --days 30 \
  --limit 20 \
  --min-stars 100 \
  --topic ai \
  --output reports/ai.md
```

如果设置了 `GITHUB_TOKEN`，API 限额会更高：

```bash
export GITHUB_TOKEN=ghp_xxx
```

## 当前评分逻辑

```text
score =
  stars_per_day * 0.45
+ log(stars) * 8
+ log(forks) * 4
+ recent_push_bonus
+ issue_activity_signal
```

报告会包含：

- 项目基础信息
- 热度信号
- 主题标签
- README 摘要片段
- 初步“值得学习的开发者思想”观察点

## 方向

后续可以继续加：

- GitHub Trending 抓取
- Hacker News 共振信号
- README/issue/PR 的 AI 分析
- SQLite 历史趋势
- 每周自动报告
