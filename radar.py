#!/usr/bin/env python3
"""Generate a high-signal GitHub project radar report."""

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
                "### 值得学习的开发者思想",
                "",
            ]
        )
        for note in repo_learning_notes(repo):
            lines.append(f"- {note}")
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
