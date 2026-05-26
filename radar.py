#!/usr/bin/env python3
"""Generate a high-signal GitHub project radar report.

The report treats popular repositories as evidence of developer taste. It does
not only rank heat; it tries to infer the design ideas behind each project.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import math
import os
import pathlib
import textwrap
import urllib.error
import urllib.parse
import urllib.request


API_ROOT = "https://api.github.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a GitHub project radar report.")
    parser.add_argument("--days", type=int, default=30, help="Look back this many days.")
    parser.add_argument("--limit", type=int, default=20, help="Number of projects in the report.")
    parser.add_argument("--min-stars", type=int, default=100, help="Minimum stars for candidate repos.")
    parser.add_argument("--topic", help="Optional GitHub topic filter, such as ai, rust, llm.")
    parser.add_argument("--language", help="Optional language filter, such as Python or TypeScript.")
    parser.add_argument("--output", default="reports/latest.md", help="Markdown report output path.")
    return parser.parse_args()


def github_get(path: str, params: dict[str, str | int] | None = None) -> dict:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        f"{API_ROOT}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-project-radar",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed: {exc.code} {body}") from exc


def search_repositories(days: int, min_stars: int, topic: str | None, language: str | None, limit: int) -> list[dict]:
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(days=days)).date().isoformat()
    query_parts = [f"created:>={since}", f"stars:>={min_stars}"]
    if topic:
        query_parts.append(f"topic:{topic}")
    if language:
        query_parts.append(f"language:{language}")

    data = github_get(
        "/search/repositories",
        {
            "q": " ".join(query_parts),
            "sort": "stars",
            "order": "desc",
            "per_page": min(max(limit * 2, 10), 100),
        },
    )
    return data.get("items", [])[: max(limit * 2, limit)]


def fetch_readme_excerpt(full_name: str) -> str:
    try:
        data = github_get(f"/repos/{full_name}/readme")
    except RuntimeError:
        return ""

    encoded = data.get("content", "")
    if not encoded:
        return ""

    raw = base64.b64decode(encoded).decode("utf-8", errors="replace")
    clean_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("[!", "<img", "<picture", "<!--")):
            continue
        clean_lines.append(stripped)
        if len(" ".join(clean_lines)) > 800:
            break
    return " ".join(clean_lines)[:900]


def days_between(iso_datetime: str, now: dt.datetime) -> float:
    created = dt.datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
    return max((now - created).total_seconds() / 86400, 1.0)


def score_repo(repo: dict, now: dt.datetime) -> float:
    age_days = days_between(repo["created_at"], now)
    stars = repo["stargazers_count"]
    forks = repo["forks_count"]
    open_issues = repo["open_issues_count"]
    stars_per_day = stars / age_days

    pushed_at = dt.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since_push = max((now - pushed_at).total_seconds() / 86400, 0)
    recent_push_bonus = max(0.0, 12.0 - days_since_push)

    issue_signal = min(open_issues, 200) / 25
    return stars_per_day * 0.45 + math.log1p(stars) * 8 + math.log1p(forks) * 4 + recent_push_bonus + issue_signal


def repo_learning_notes(repo: dict) -> list[str]:
    notes = []
    topics = set(repo.get("topics") or [])
    description = (repo.get("description") or "").lower()

    if {"ai", "llm", "agents", "rag"} & topics or any(word in description for word in ["ai", "llm", "agent", "rag"]):
        notes.append("把 AI 能力产品化或工程化，重点看它如何定义抽象边界、状态管理和失败处理。")
    if {"developer-tools", "cli", "sdk"} & topics or any(word in description for word in ["cli", "sdk", "developer"]):
        notes.append("开发者工具项目，重点看 API/CLI 是否让复杂能力变得可组合。")
    if {"database", "vector-database", "search"} & topics or any(word in description for word in ["database", "search", "vector"]):
        notes.append("基础设施项目，重点看性能、数据模型和易用性之间的取舍。")
    if repo["forks_count"] > 50:
        notes.append("fork 信号较强，说明项目可能已经触发二次开发或集成需求。")
    if not notes:
        notes.append("先读 README、examples 和核心模块，判断它解决的问题是否足够具体。")
    return notes


def repo_text(repo: dict) -> str:
    parts = [
        repo.get("name") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or []),
        repo.get("_readme_excerpt") or "",
    ]
    return " ".join(parts).lower()


def has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def infer_design_thesis(repo: dict) -> str:
    text = repo_text(repo)
    if has_any(text, ["local-first", "offline", "self-host", "self host", "on-device", "zero api key"]):
        return "把控制权还给用户：优先本地、自托管或低依赖，反对把核心能力锁进远端平台。"
    if has_any(text, ["agent", "agents", "workflow", "autonomous"]):
        return "把复杂工作流变成可委托的系统：核心判断是未来软件会围绕 agent 协作和可验证执行重组。"
    if has_any(text, ["fast", "performance", "latency", "runtime", "native", "zero dependencies"]):
        return "用性能和简单依赖构建信任：先把基础体验做到足够快、足够可控，再谈上层能力。"
    if has_any(text, ["cli", "sdk", "api", "developer"]):
        return "把能力包装成开发者可组合的接口：真正的产品不是页面，而是别人可以继续搭建的原语。"
    if has_any(text, ["database", "search", "vector", "storage", "index"]):
        return "先抓住数据模型：项目价值来自重新定义数据如何被存储、检索、迁移或理解。"
    return "从一个足够具体的痛点切入，用代码验证某种新的默认工作方式。"


def infer_tradeoffs(repo: dict) -> list[str]:
    text = repo_text(repo)
    tradeoffs = []
    if has_any(text, ["not a generic", "intentionally narrow", "focused", "opinionated"]):
        tradeoffs.append("选择窄而深，牺牲通用性来换取清晰边界和更高完成度。")
    if has_any(text, ["zero dependencies", "self-contained", "single binary"]):
        tradeoffs.append("减少外部依赖，把可部署性和可理解性放在功能堆叠之前。")
    if has_any(text, ["experimental", "not ready for production", "security vulnerabilities should be expected"]):
        tradeoffs.append("公开承认实验状态，用透明边界换取社区快速验证。")
    if has_any(text, ["local-first", "self-host", "offline", "zero api key"]):
        tradeoffs.append("优先用户主权和长期可控性，接受更高的本地安装和维护复杂度。")
    if has_any(text, ["plugin", "extension", "skills", "workflow"]):
        tradeoffs.append("通过插件/工作流扩展，把核心保持小，把变化交给生态。")
    if not tradeoffs:
        tradeoffs.append("需要继续读 examples、核心模块和 issue，确认它真正牺牲了什么来换取当前优势。")
    return tradeoffs


def infer_mental_model(repo: dict) -> list[str]:
    text = repo_text(repo)
    models = []
    if has_any(text, ["html", "markdown", "document", "slides", "presentation"]):
        models.append("媒介即产品：输出格式、阅读体验和传播路径本身就是设计对象。")
    if has_any(text, ["compiler", "language", "runtime", "protocol"]):
        models.append("重做底层协议/语言，而不是在旧接口上继续打补丁。")
    if has_any(text, ["preview", "sandbox", "export", "one-click"]):
        models.append("缩短反馈循环：让用户更快看到结果、更快交付、更少上下文切换。")
    if has_any(text, ["examples", "template", "starter"]):
        models.append("通过示例传播理念：降低学习成本比解释概念更重要。")
    if repo["stargazers_count"] / max(days_between(repo["created_at"], dt.datetime.now(dt.UTC)), 1.0) > 100:
        models.append("高传播速度说明它命中了一个正在形成共识、但现有工具尚未满足的缺口。")
    if not models:
        models.append("先看 README 的第一屏和 examples 目录：顶尖项目通常会很快暴露它对世界的默认假设。")
    return models


def render_philosophy(repo: dict) -> list[str]:
    lines = [
        "### 思想本质切片",
        "",
        f"- 核心命题：{infer_design_thesis(repo)}",
        "- 关键取舍：",
    ]
    for item in infer_tradeoffs(repo):
        lines.append(f"  - {item}")
    lines.append("- 开发者心智模型：")
    for item in infer_mental_model(repo):
        lines.append(f"  - {item}")
    lines.extend(
        [
            "- 下一步精读入口：README 第一屏、examples、核心 API 文件、最近合并的 PR、争议最多的 issue。",
            "",
        ]
    )
    return lines


def render_report(repos: list[dict], args: argparse.Namespace) -> str:
    now = dt.datetime.now(dt.UTC)
    lines = [
        "# GitHub 高信号项目雷达",
        "",
        f"- 生成时间：{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 时间窗口：最近 {args.days} 天创建",
        f"- 最低 star：{args.min_stars}",
        f"- 主题过滤：{args.topic or '无'}",
        f"- 语言过滤：{args.language or '无'}",
        "",
    ]

    for index, repo in enumerate(repos, 1):
        age_days = days_between(repo["created_at"], now)
        stars_per_day = repo["stargazers_count"] / age_days
        topics = ", ".join(repo.get("topics") or []) or "无"
        homepage = repo.get("homepage")
        readme = repo.get("_readme_excerpt") or "未抓到 README。"

        lines.extend(
            [
                f"## {index}. {repo['full_name']}",
                "",
                repo.get("description") or "无描述。",
                "",
                f"- 链接：{repo['html_url']}",
                f"- 官网：{homepage}" if homepage else "- 官网：无",
                f"- 语言：{repo.get('language') or '未知'}",
                f"- Stars：{repo['stargazers_count']}",
                f"- Forks：{repo['forks_count']}",
                f"- Open issues：{repo['open_issues_count']}",
                f"- 创建时间：{repo['created_at']}",
                f"- 最近推送：{repo['pushed_at']}",
                f"- Star/day：{stars_per_day:.1f}",
                f"- Radar score：{repo['_score']:.1f}",
                f"- Topics：{topics}",
                "",
                "### README 信号",
                "",
                textwrap.fill(readme, width=88),
                "",
            ]
        )
        lines.extend(render_philosophy(repo))
        lines.extend(["### 初步观察", ""])
        lines.extend(f"- {note}" for note in repo_learning_notes(repo))
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    now = dt.datetime.now(dt.UTC)
    candidates = search_repositories(args.days, args.min_stars, args.topic, args.language, args.limit)

    for repo in candidates:
        repo["_score"] = score_repo(repo, now)
    repos = sorted(candidates, key=lambda item: item["_score"], reverse=True)[: args.limit]

    for repo in repos:
        repo["_readme_excerpt"] = fetch_readme_excerpt(repo["full_name"])

    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(repos, args), encoding="utf-8")
    print(f"Wrote {output} with {len(repos)} repos.")


if __name__ == "__main__":
    main()
