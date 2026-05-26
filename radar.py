#!/usr/bin/env python3
"""OSS Cognition Radar.

This tool treats public open-source repositories as observable engineering
evidence. It ranks hot projects, but its main job is to build evidence-backed
project dossiers that infer reusable cognition, design, and governance patterns.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import sqlite3
import textwrap
import urllib.error
import urllib.parse
import urllib.request


API_ROOT = "https://api.github.com"
USER_AGENT = "oss-cognition-radar"
MAX_TEXT_CHARS = 5000
GROWTH_WINDOWS = {"1d": 1, "7d": 7, "30d": 30}
GROWTH_MAX_AGE_DAYS = {"1d": 2, "7d": 10, "30d": 45}
TRACK_WEIGHTS = {
    "agent": {
        "momentum": 0.25,
        "collaboration": 0.20,
        "release": 0.15,
        "governance": 0.10,
        "evidence": 0.20,
        "ecosystem": 0.10,
    },
    "developer_tools": {
        "momentum": 0.20,
        "collaboration": 0.25,
        "release": 0.20,
        "governance": 0.10,
        "evidence": 0.15,
        "ecosystem": 0.10,
    },
    "local_first": {
        "momentum": 0.15,
        "collaboration": 0.20,
        "release": 0.15,
        "governance": 0.15,
        "evidence": 0.20,
        "ecosystem": 0.15,
    },
    "protocol": {
        "momentum": 0.10,
        "collaboration": 0.20,
        "release": 0.10,
        "governance": 0.25,
        "evidence": 0.25,
        "ecosystem": 0.10,
    },
    "general": {
        "momentum": 0.25,
        "collaboration": 0.20,
        "release": 0.15,
        "governance": 0.15,
        "evidence": 0.15,
        "ecosystem": 0.10,
    },
}


@dataclasses.dataclass
class Evidence:
    """A traceable public artifact used to support a project claim."""

    evidence_id: str
    level: int
    kind: str
    title: str
    url: str
    quote: str
    stable_id: str = ""


@dataclasses.dataclass
class Claim:
    """An inferred project-level claim with supporting evidence."""

    field: str
    text: str
    evidence_ids: list[str]
    confidence: str
    claim_id: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infer OSS cognition patterns from GitHub projects.")
    parser.add_argument("--repo", help="Analyze one repository deeply, for example langchain-ai/langgraph.")
    parser.add_argument("--days", type=int, default=30, help="Discovery mode: look back this many days.")
    parser.add_argument("--limit", type=int, default=20, help="Discovery mode: number of projects in the report.")
    parser.add_argument("--min-stars", type=int, default=100, help="Discovery mode: minimum stars for candidates.")
    parser.add_argument("--topic", help="Discovery mode: optional GitHub topic filter, such as ai or local-first.")
    parser.add_argument("--language", help="Discovery mode: optional language filter, such as Python or TypeScript.")
    parser.add_argument("--output", default="reports/latest.md", help="Markdown report output path.")
    parser.add_argument("--json-output", help="Optional structured JSON output path.")
    parser.add_argument("--db", default="data/radar.sqlite", help="SQLite snapshot database path.")
    parser.add_argument("--no-db", action="store_true", help="Do not persist this run to SQLite.")
    parser.add_argument("--archive-list", action="store_true", help="List latest repository snapshots from SQLite.")
    parser.add_argument("--archive-search", metavar="TEXT", help="Search archived repositories, claims, and evidence.")
    parser.add_argument("--archive-show", metavar="OWNER/REPO", help="Show the latest archived dossier for one repository.")
    parser.add_argument(
        "--archive-track",
        choices=sorted(TRACK_WEIGHTS),
        help="Archive mode: filter repositories by project track.",
    )
    parser.add_argument("--min-track-score", type=float, default=0.0, help="Archive mode: minimum track score.")
    parser.add_argument("--archive-output", help="Archive mode: optional Markdown output path. Defaults to stdout.")
    return parser.parse_args()


def github_get(path: str, params: dict[str, str | int] | None = None) -> dict | list:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        f"{API_ROOT}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2026-03-10",
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


def github_get_optional(path: str, params: dict[str, str | int] | None = None) -> dict | list | None:
    try:
        return github_get(path, params)
    except RuntimeError:
        return None


def fetch_url_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_TEXT_CHARS + 2000)
    except urllib.error.URLError:
        return ""
    return data.decode("utf-8", errors="replace")[:MAX_TEXT_CHARS]


def decode_github_content(item: dict) -> str:
    encoded = item.get("content") or ""
    if not encoded:
        return ""
    return base64.b64decode(encoded).decode("utf-8", errors="replace")[:MAX_TEXT_CHARS]


def normalize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("[!", "<img", "<picture", "<!--")):
            continue
        lines.append(stripped)
    joined = " ".join(lines)
    joined = re.sub(r"<[^>]+>", " ", joined)
    joined = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", joined)
    joined = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", joined)
    return re.sub(r"\s+", " ", joined).strip()


def excerpt(text: str, limit: int = 700) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def days_between(iso_datetime: str, now: dt.datetime) -> float:
    created = dt.datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
    return max((now - created).total_seconds() / 86400, 1.0)


def has_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def evidence_refs(ids: list[str]) -> str:
    return ", ".join(f"`{item}`" for item in ids) if ids else "`无直接证据`"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def parse_iso_datetime(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def stable_id(prefix: str, *parts: str) -> str:
    raw = "::".join(part or "" for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def linear_score(value: int | float | None, cap: float) -> float:
    if value is None or cap <= 0:
        return 0.0
    return clamp((max(float(value), 0.0) / cap) * 100.0)


def log_score(value: int | float | None, cap: float) -> float:
    if value is None or cap <= 0:
        return 0.0
    return clamp((math.log1p(max(float(value), 0.0)) / math.log1p(cap)) * 100.0)


def repo_profile_text(summary: dict) -> str:
    parts = [
        summary.get("full_name") or "",
        summary.get("description") or "",
        summary.get("language") or "",
        " ".join(summary.get("topics") or []),
    ]
    return " ".join(parts).lower()


def classify_project_track(summary: dict) -> str:
    text = repo_profile_text(summary)
    if has_any(text, ["mcp", "protocol", "standard", "spec", "server", "context infrastructure"]):
        return "protocol"
    if has_any(text, ["local-first", "local first", "offline", "sync", "crdt", "collaborative"]):
        return "local_first"
    if has_any(text, ["agent", "agents", "llm", "rag", "ai-agents", "multiagent", "model"]):
        return "agent"
    if has_any(text, ["cli", "sdk", "developer-tools", "developer tool", "editor", "formatter", "linter", "compiler", "ide"]):
        return "developer_tools"
    return "general"


def search_repositories(days: int, min_stars: int, topic: str | None, language: str | None, limit: int) -> list[dict]:
    since = (dt.datetime.now(dt.UTC) - dt.timedelta(days=days)).date().isoformat()
    query_parts = [f"created:>={since}", f"stars:>={min_stars}", "archived:false"]
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
    if not isinstance(data, dict):
        return []
    return data.get("items", [])[: max(limit * 2, limit)]


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
    return stars_per_day * 0.35 + math.log1p(stars) * 8 + math.log1p(forks) * 4 + recent_push_bonus + issue_signal


def fetch_repository(full_name: str) -> dict:
    data = github_get(f"/repos/{full_name}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected repository response for {full_name}")
    return data


def fetch_readme(full_name: str) -> tuple[str, str]:
    data = github_get_optional(f"/repos/{full_name}/readme")
    if not isinstance(data, dict):
        return "", ""
    return decode_github_content(data), data.get("html_url") or f"https://github.com/{full_name}"


def fetch_tree_files(repo: dict) -> list[dict]:
    full_name = repo["full_name"]
    branch = repo.get("default_branch") or "main"
    data = github_get_optional(f"/repos/{full_name}/git/trees/{branch}", {"recursive": 1})
    if not isinstance(data, dict):
        return []
    return [item for item in data.get("tree", []) if item.get("type") == "blob"]


def important_paths(files: list[dict]) -> list[str]:
    candidates = []
    exact_names = {
        "contributing.md",
        "security.md",
        "code_of_conduct.md",
        "governance.md",
        "changelog.md",
        "architecture.md",
        "roadmap.md",
    }
    for item in files:
        path = item.get("path") or ""
        lowered = path.lower()
        name = lowered.rsplit("/", 1)[-1]
        if name in exact_names:
            candidates.append(path)
        elif lowered.startswith(("docs/", "examples/", "example/", ".github/")) and name in {
            "readme.md",
            "quickstart.md",
            "getting-started.md",
            "index.md",
            "contributing.md",
            "issue_template.md",
            "pull_request_template.md",
        }:
            candidates.append(path)
        elif lowered in {
            ".github/issue_template/bug_report.md",
            ".github/pull_request_template.md",
        }:
            candidates.append(path)
    return candidates[:8]


def fetch_file_text(repo: dict, path: str) -> tuple[str, str]:
    data = github_get_optional(f"/repos/{repo['full_name']}/contents/{urllib.parse.quote(path)}")
    if not isinstance(data, dict):
        return "", f"{repo['html_url']}/blob/{repo.get('default_branch', 'main')}/{path}"
    if data.get("download_url"):
        return fetch_url_text(data["download_url"]), data.get("html_url") or data["download_url"]
    return decode_github_content(data), data.get("html_url") or ""


def fetch_releases(full_name: str) -> list[dict]:
    data = github_get_optional(f"/repos/{full_name}/releases", {"per_page": 5})
    return data if isinstance(data, list) else []


def fetch_issues(full_name: str) -> list[dict]:
    data = github_get_optional(
        "/search/issues",
        {"q": f"repo:{full_name} is:issue", "sort": "comments", "order": "desc", "per_page": 5},
    )
    if not isinstance(data, dict):
        return []
    return data.get("items", [])


def fetch_pull_requests(full_name: str) -> list[dict]:
    query = f"repo:{full_name} is:pr is:merged -author:dependabot[bot] -label:dependencies"
    data = github_get_optional("/search/issues", {"q": query, "sort": "comments", "order": "desc", "per_page": 5})
    if not isinstance(data, dict):
        return []
    return data.get("items", [])


def search_issue_count(query: str) -> int | None:
    data = github_get_optional("/search/issues", {"q": query, "per_page": 1})
    if not isinstance(data, dict):
        return None
    return data.get("total_count")


def fetch_contributors(full_name: str) -> list[dict]:
    data = github_get_optional(f"/repos/{full_name}/contributors", {"per_page": 100})
    return data if isinstance(data, list) else []


def fetch_repository_health(repo: dict, releases: list[dict] | None = None) -> dict:
    full_name = repo["full_name"]
    now = utc_now()
    since_180 = (now - dt.timedelta(days=180)).date().isoformat()
    since_365 = (now - dt.timedelta(days=365)).date().isoformat()
    releases = releases if releases is not None else fetch_releases(full_name)
    release_dates = [
        release.get("published_at")
        for release in releases
        if release.get("published_at") and release.get("published_at") >= f"{since_365}T00:00:00Z"
    ]
    contributors = fetch_contributors(full_name)
    top_contributors = [
        {
            "login": item.get("login"),
            "contributions": item.get("contributions", 0),
            "html_url": item.get("html_url"),
        }
        for item in contributors[:10]
    ]

    merged_prs_180d = search_issue_count(f"repo:{full_name} is:pr is:merged merged:>={since_180}")
    closed_issues_180d = search_issue_count(f"repo:{full_name} is:issue is:closed closed:>={since_180}")
    open_prs = search_issue_count(f"repo:{full_name} is:pr is:open")

    return {
        "window_days": 180,
        "merged_prs_180d": merged_prs_180d,
        "closed_issues_180d": closed_issues_180d,
        "open_prs": open_prs,
        "release_count_365d_sample": len(release_dates),
        "latest_release_at": release_dates[0] if release_dates else None,
        "top_contributor_count_sample": len(contributors),
        "top_contributors": top_contributors,
        "has_license": bool(repo.get("license")),
        "has_homepage": bool(repo.get("homepage")),
        "pushed_within_30d": (now - parse_iso_datetime(repo["pushed_at"])).days <= 30,
    }


def build_evidence(repo: dict) -> list[Evidence]:
    evidence: list[Evidence] = []
    full_name = repo["full_name"]

    readme, readme_url = fetch_readme(full_name)
    if readme:
        evidence.append(Evidence("E1", 1, "README", "Project positioning and first-screen narrative", readme_url, excerpt(readme, 900)))

    files = fetch_tree_files(repo)
    for path in important_paths(files):
        text, url = fetch_file_text(repo, path)
        if text:
            evidence.append(Evidence(f"E{len(evidence) + 1}", 1, "File", path, url, excerpt(text, 700)))

    for release in fetch_releases(full_name):
        title = release.get("name") or release.get("tag_name") or "Release"
        body = release.get("body") or ""
        quote = excerpt(body, 550) or f"Published at {release.get('published_at') or 'unknown time'}."
        evidence.append(Evidence(f"E{len(evidence) + 1}", 1, "Release", title, release.get("html_url") or "", quote))

    for issue in fetch_issues(full_name):
        quote = excerpt(issue.get("body") or "", 500) or f"{issue.get('comments', 0)} comments; state={issue.get('state')}."
        evidence.append(Evidence(f"E{len(evidence) + 1}", 1, "Issue", issue.get("title") or "Issue", issue.get("html_url") or "", quote))

    for pr in fetch_pull_requests(full_name):
        quote = excerpt(pr.get("body") or "", 500) or f"state={pr.get('state')}; merged_at={pr.get('merged_at')}."
        evidence.append(Evidence(f"E{len(evidence) + 1}", 1, "Pull Request", pr.get("title") or "Pull request", pr.get("html_url") or "", quote))

    assign_evidence_ids(repo, evidence)
    return evidence


def assign_evidence_ids(repo: dict, evidence: list[Evidence]) -> None:
    for item in evidence:
        item.stable_id = stable_id("ev", repo["full_name"], item.kind, item.url or item.title)


def corpus(evidence: list[Evidence], repo: dict) -> str:
    parts = [repo.get("description") or "", " ".join(repo.get("topics") or [])]
    parts.extend(item.quote for item in evidence)
    return "\n".join(parts)


def matching_evidence(evidence: list[Evidence], words: list[str], fallback: int = 1) -> list[str]:
    matches = [item.evidence_id for item in evidence if has_any(item.quote + " " + item.title, words)]
    if matches:
        return matches[:4]
    return [item.evidence_id for item in evidence[:fallback]]


def infer_domain(repo: dict, text: str) -> str:
    topics = set(repo.get("topics") or [])
    if {"ai", "llm", "agent", "agents", "rag"} & topics or has_any(text, ["agent", "llm", "rag", "model"]):
        return "AI agent / AI engineering"
    if {"cli", "developer-tools", "sdk"} & topics or has_any(text, ["cli", "sdk", "developer tool"]):
        return "Developer tools"
    if {"local-first", "offline", "sync"} & topics or has_any(text, ["local-first", "offline", "sync"]):
        return "Local-first / collaborative systems"
    if has_any(text, ["protocol", "standard", "server", "mcp"]):
        return "Protocol / context infrastructure"
    return repo.get("language") or "General OSS"


def claim_problem_frame(evidence: list[Evidence], repo: dict, text: str) -> Claim:
    if has_any(text, ["durable", "checkpoint", "interrupt", "resume", "recover"]):
        claim = "项目把表面功能问题改写为可恢复运行、状态边界和失败处理问题。"
        ids = matching_evidence(evidence, ["durable", "checkpoint", "interrupt", "resume", "recover"])
    elif has_any(text, ["local-first", "self-host", "offline", "zero api key"]):
        claim = "项目把问题定义为用户控制权和长期可拥有性，而不只是功能可用性。"
        ids = matching_evidence(evidence, ["local-first", "self-host", "offline", "zero api key"])
    elif has_any(text, ["fast", "performance", "latency", "native", "zero dependencies"]):
        claim = "项目把竞争焦点放在速度、低依赖和可控部署上，用基础体验建立信任。"
        ids = matching_evidence(evidence, ["fast", "performance", "latency", "native", "zero dependencies"])
    elif has_any(text, ["agent", "workflow", "automation"]):
        claim = "项目把软件使用方式改写为可编排、可委托、可观察的工作流。"
        ids = matching_evidence(evidence, ["agent", "workflow", "automation"])
    else:
        claim = "项目从一个具体痛点切入，正在验证新的默认工作方式。"
        ids = matching_evidence(evidence, [repo.get("name", "")])
    return Claim("作者如何重新定义问题", claim, ids, "medium" if ids else "low")


def claim_key_abstractions(evidence: list[Evidence], text: str) -> Claim:
    abstractions = []
    keywords = {
        "graph/node/workflow": ["graph", "node", "workflow"],
        "checkpoint / durability": ["checkpoint", "durable", "durability"],
        "CLI / SDK": ["cli", "sdk", "api"],
        "plugin / extension": ["plugin", "extension", "skills"],
        "protocol / server": ["protocol", "server", "mcp"],
        "sync / local state": ["sync", "local-first", "offline"],
    }
    for label, words in keywords.items():
        if has_any(text, words):
            abstractions.append(label)
    if abstractions:
        claim = "关键抽象集中在：" + "、".join(abstractions[:4]) + "。"
        ids = matching_evidence(evidence, [word for words in keywords.values() for word in words])
    else:
        claim = "关键抽象尚需通过 examples 和核心 API 文件确认。"
        ids = matching_evidence(evidence, ["api", "example", "quickstart"])
    return Claim("关键抽象", claim, ids, "medium" if abstractions else "low")


def claim_boundaries(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["not a generic", "intentionally narrow", "focused", "low-level", "you don't need"]):
        claim = "项目主动声明边界，倾向用清晰分层换取可理解性和长期演进能力。"
        ids = matching_evidence(evidence, ["not a generic", "intentionally narrow", "focused", "low-level", "you don't need"])
    elif has_any(text, ["experimental", "not ready for production", "preview"]):
        claim = "项目把实验状态显式写出，用透明边界降低误用风险。"
        ids = matching_evidence(evidence, ["experimental", "not ready for production", "preview"])
    else:
        claim = "项目边界目前主要从 README 和 issue 侧面推断，后续需要抓取架构文档和 PR 讨论补强。"
        ids = matching_evidence(evidence, ["readme", "docs", "issue"])
    return Claim("架构边界", claim, ids, "medium" if ids else "low")


def claim_complexity(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["bug", "error", "issue", "checkpoint", "interrupt", "self-hosted", "compatibility"]):
        claim = "复杂度主要暴露在失败语义、兼容性、部署环境和状态一致性上，不能只看 README 的顺滑叙事。"
        ids = matching_evidence(evidence, ["bug", "error", "checkpoint", "interrupt", "self-hosted", "compatibility"])
    elif has_any(text, ["performance", "latency", "memory", "concurrency"]):
        claim = "复杂度集中在性能、资源使用和并发边界，适合继续精读 benchmark 与实现模块。"
        ids = matching_evidence(evidence, ["performance", "latency", "memory", "concurrency"])
    else:
        claim = "复杂度藏处尚不明确，需要进一步抓取高评论 issue、最近 PR 和核心目录。"
        ids = matching_evidence(evidence, ["issue", "pull request"])
    return Claim("复杂度藏处", claim, ids, "medium" if ids else "low")


def claim_governance(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["contributing", "code of conduct", "security", "issue template", "forum", "discussion"]):
        claim = "治理上倾向把贡献、支持、缺陷和安全问题分流，降低维护者认知负担。"
        ids = matching_evidence(evidence, ["contributing", "code of conduct", "security", "issue template", "forum", "discussion"])
    else:
        claim = "治理证据不足；需要检查 CONTRIBUTING、issue 模板、讨论区和响应时间。"
        ids = matching_evidence(evidence, ["contributing", "issue"])
    return Claim("治理模式", claim, ids, "medium" if ids else "low")


def fake_star_risk(repo: dict) -> str:
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    issues = repo.get("open_issues_count", 0)
    age_days = days_between(repo["created_at"], dt.datetime.now(dt.UTC))
    stars_per_day = stars / age_days
    fork_ratio = forks / stars if stars else 0
    if stars_per_day > 500 and fork_ratio < 0.02:
        return "高：star 增速极快但 fork 比例偏低，需要审计 stargazer 时间序列。"
    if stars_per_day > 150 and issues < 5:
        return "中：传播速度很快但协作痕迹偏少，需要交叉验证 PR、contributors 与外部采用。"
    return "低/中：当前元数据未显示明显异常，但 star 仍只能作为兴趣信号。"


def repo_summary(repo: dict, now: dt.datetime, include_health: bool = True) -> dict:
    age_days = days_between(repo["created_at"], now)
    stars = repo.get("stargazers_count", 0)
    license_info = repo.get("license") or {}
    full_name = repo.get("full_name")
    return {
        "dossier_id": stable_id("dossier", full_name or ""),
        "repository_slug": slugify(full_name or repo.get("name") or ""),
        "id": repo.get("id"),
        "full_name": full_name,
        "name": repo.get("name"),
        "owner": (repo.get("owner") or {}).get("login"),
        "html_url": repo.get("html_url"),
        "description": repo.get("description"),
        "homepage": repo.get("homepage"),
        "language": repo.get("language"),
        "stars": stars,
        "forks": repo.get("forks_count", 0),
        "watchers": repo.get("watchers_count", 0),
        "open_issues": repo.get("open_issues_count", 0),
        "created_at": repo.get("created_at"),
        "updated_at": repo.get("updated_at"),
        "pushed_at": repo.get("pushed_at"),
        "default_branch": repo.get("default_branch"),
        "archived": repo.get("archived", False),
        "license": license_info.get("key") or license_info.get("spdx_id"),
        "topics": repo.get("topics") or [],
        "score": repo.get("_score", score_repo(repo, now)),
        "stars_per_day": stars / age_days,
        "fake_star_risk": fake_star_risk(repo),
        "health": fetch_repository_health(repo) if include_health else {},
    }


def best_growth_delta(summary: dict) -> int | None:
    growth = summary.get("star_growth") or {}
    for label in ("30d", "7d", "1d"):
        item = growth.get(label) or {}
        if item.get("available") and item.get("delta") is not None:
            return item["delta"]
    return None


def latest_release_recency_score(latest_release_at: str | None, now: dt.datetime) -> float:
    if not latest_release_at:
        return 0.0
    try:
        age_days = (now - parse_iso_datetime(latest_release_at)).total_seconds() / 86400
    except ValueError:
        return 0.0
    if age_days <= 30:
        return 100.0
    if age_days <= 90:
        return 75.0
    if age_days <= 180:
        return 45.0
    return 15.0


def fake_star_confidence_score(summary: dict) -> float:
    risk = summary.get("fake_star_risk") or ""
    if risk.startswith("高"):
        return 20.0
    if risk.startswith("中"):
        return 55.0
    return 80.0


def compute_track_score(summary: dict, evidence_count: int = 0, claim_count: int = 0) -> dict:
    track = classify_project_track(summary)
    health = summary.get("health") or {}
    now = utc_now()
    growth_delta = best_growth_delta(summary)
    growth_signal = log_score(growth_delta, 5000) if growth_delta is not None else 0.0
    velocity_signal = linear_score(summary.get("stars_per_day"), 150)
    momentum = max(growth_signal, velocity_signal)

    collaboration = (
        linear_score(health.get("merged_prs_180d"), 300) * 0.45
        + linear_score(health.get("closed_issues_180d"), 300) * 0.25
        + linear_score(health.get("top_contributor_count_sample"), 100) * 0.20
        + linear_score(health.get("open_prs"), 150) * 0.10
    )
    release = (
        linear_score(health.get("release_count_365d_sample"), 5) * 0.65
        + latest_release_recency_score(health.get("latest_release_at"), now) * 0.35
    )
    governance = (
        (30.0 if health.get("has_license") else 0.0)
        + (25.0 if health.get("pushed_within_30d") else 0.0)
        + (15.0 if health.get("has_homepage") else 0.0)
        + fake_star_confidence_score(summary) * 0.30
    )
    evidence = linear_score(evidence_count, 18) * 0.70 + linear_score(claim_count, 8) * 0.30
    ecosystem = (
        log_score(summary.get("forks"), 5000) * 0.55
        + linear_score(health.get("top_contributor_count_sample"), 100) * 0.25
        + linear_score(len(summary.get("topics") or []), 20) * 0.20
    )

    signals = {
        "momentum": round(momentum, 1),
        "collaboration": round(collaboration, 1),
        "release": round(release, 1),
        "governance": round(governance, 1),
        "evidence": round(evidence, 1),
        "ecosystem": round(ecosystem, 1),
    }
    weights = TRACK_WEIGHTS[track]
    score = sum(signals[name] * weight for name, weight in weights.items())

    rationale = [
        f"classified as {track}",
        "uses tracked star growth when available, otherwise falls back to star/day velocity",
        "weights differ by project type so infrastructure/protocol projects are not judged like short-term demos",
    ]
    if evidence_count == 0:
        rationale.append("evidence score is low in discovery mode until a deep dossier is generated")

    return {
        "track": track,
        "score": round(score, 1),
        "signals": signals,
        "weights": weights,
        "rationale": rationale,
    }


def attach_track_scores(summaries: list[dict], evidence_counts: dict[str, int] | None = None, claim_counts: dict[str, int] | None = None) -> None:
    evidence_counts = evidence_counts or {}
    claim_counts = claim_counts or {}
    for summary in summaries:
        full_name = summary["full_name"]
        summary["track_score"] = compute_track_score(
            summary,
            evidence_count=evidence_counts.get(full_name, 0),
            claim_count=claim_counts.get(full_name, 0),
        )


def evidence_to_dict(evidence: Evidence) -> dict:
    return dataclasses.asdict(evidence)


def claim_to_dict(claim: Claim, evidence_map: dict[str, Evidence] | None = None) -> dict:
    data = dataclasses.asdict(claim)
    if evidence_map:
        data["evidence_stable_ids"] = [
            evidence_map[evidence_id].stable_id
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_map
        ]
    else:
        data["evidence_stable_ids"] = []
    return data


def build_deep_payload(repo: dict, evidence: list[Evidence], claims: list[Claim], run_at: dt.datetime) -> dict:
    summary = repo_summary(repo, run_at)
    evidence_map = {item.evidence_id: item for item in evidence}
    return {
        "schema_version": 1,
        "mode": "deep",
        "generated_at": run_at.isoformat(),
        "dossier_id": stable_id("dossier", repo["full_name"]),
        "method_boundary": "Only public GitHub engineering artifacts are used to infer observable, reviewable, transferable cognition/design/governance patterns.",
        "repository": summary,
        "claims": [claim_to_dict(item, evidence_map) for item in claims],
        "evidence": [evidence_to_dict(item) for item in evidence],
    }


def build_discovery_payload(repo_summaries: list[dict], args: argparse.Namespace, run_at: dt.datetime) -> dict:
    return {
        "schema_version": 1,
        "mode": "discovery",
        "generated_at": run_at.isoformat(),
        "query": {
            "days": args.days,
            "limit": args.limit,
            "min_stars": args.min_stars,
            "topic": args.topic,
            "language": args.language,
        },
        "repositories": repo_summaries,
    }


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            repo_full_name TEXT,
            query_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS repository_snapshots (
            run_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            html_url TEXT NOT NULL,
            description TEXT,
            language TEXT,
            stars INTEGER NOT NULL,
            forks INTEGER NOT NULL,
            watchers INTEGER NOT NULL,
            open_issues INTEGER NOT NULL,
            created_at TEXT,
            updated_at TEXT,
            pushed_at TEXT,
            default_branch TEXT,
            topics_json TEXT NOT NULL,
            score REAL NOT NULL,
            stars_per_day REAL NOT NULL,
            fake_star_risk TEXT NOT NULL,
            archived INTEGER NOT NULL,
            license TEXT,
            project_track TEXT,
            track_score REAL,
            track_score_json TEXT,
            PRIMARY KEY (run_id, full_name),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS evidence_items (
            run_id INTEGER NOT NULL,
            repo_full_name TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            stable_id TEXT,
            level INTEGER NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            quote TEXT NOT NULL,
            PRIMARY KEY (run_id, repo_full_name, evidence_id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS claims (
            run_id INTEGER NOT NULL,
            repo_full_name TEXT NOT NULL,
            claim_id TEXT,
            field TEXT NOT NULL,
            text TEXT NOT NULL,
            evidence_ids_json TEXT NOT NULL,
            evidence_stable_ids_json TEXT,
            confidence TEXT NOT NULL,
            PRIMARY KEY (run_id, repo_full_name, field),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS repository_health_snapshots (
            run_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            health_json TEXT NOT NULL,
            PRIMARY KEY (run_id, full_name),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );
        """
    )
    ensure_column(conn, "evidence_items", "stable_id", "TEXT")
    ensure_column(conn, "claims", "claim_id", "TEXT")
    ensure_column(conn, "claims", "evidence_stable_ids_json", "TEXT")
    ensure_column(conn, "repository_snapshots", "project_track", "TEXT")
    ensure_column(conn, "repository_snapshots", "track_score", "REAL")
    ensure_column(conn, "repository_snapshots", "track_score_json", "TEXT")


def empty_star_growth() -> dict:
    return {
        label: {
            "available": False,
            "delta": None,
            "baseline_stars": None,
            "baseline_at": None,
            "days_between": None,
            "reason": "insufficient history",
        }
        for label in GROWTH_WINDOWS
    }


def load_star_growth(db_path: str, summaries: list[dict], run_at: dt.datetime) -> dict[str, dict]:
    growth = {summary["full_name"]: empty_star_growth() for summary in summaries}
    path = pathlib.Path(db_path)
    if not path.exists():
        return growth

    with sqlite3.connect(path) as conn:
        init_db(conn)
        for summary in summaries:
            full_name = summary["full_name"]
            current_stars = summary["stars"]
            for label, days in GROWTH_WINDOWS.items():
                target = (run_at - dt.timedelta(days=days)).isoformat()
                earliest = (run_at - dt.timedelta(days=GROWTH_MAX_AGE_DAYS[label])).isoformat()
                row = conn.execute(
                    """
                    SELECT r.created_at, s.stars
                    FROM repository_snapshots s
                    JOIN runs r ON r.id = s.run_id
                    WHERE s.full_name = ? AND r.created_at <= ? AND r.created_at >= ?
                    ORDER BY r.created_at DESC
                    LIMIT 1
                    """,
                    (full_name, target, earliest),
                ).fetchone()
                if not row:
                    continue

                baseline_at, baseline_stars = row
                baseline_dt = parse_iso_datetime(baseline_at)
                actual_days = max((run_at - baseline_dt).total_seconds() / 86400, 0)
                growth[full_name][label] = {
                    "available": True,
                    "delta": current_stars - baseline_stars,
                    "baseline_stars": baseline_stars,
                    "baseline_at": baseline_at,
                    "days_between": actual_days,
                    "reason": None,
                }
    return growth


def attach_star_growth(summaries: list[dict], db_path: str | None, run_at: dt.datetime) -> None:
    if not db_path:
        growth = {summary["full_name"]: empty_star_growth() for summary in summaries}
    else:
        growth = load_star_growth(db_path, summaries, run_at)
    for summary in summaries:
        summary["star_growth"] = growth.get(summary["full_name"], empty_star_growth())


def insert_repo_snapshot(conn: sqlite3.Connection, run_id: int, summary: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO repository_snapshots (
            run_id, full_name, html_url, description, language, stars, forks,
            watchers, open_issues, created_at, updated_at, pushed_at,
            default_branch, topics_json, score, stars_per_day, fake_star_risk,
            archived, license, project_track, track_score, track_score_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            summary["full_name"],
            summary["html_url"],
            summary["description"],
            summary["language"],
            summary["stars"],
            summary["forks"],
            summary["watchers"],
            summary["open_issues"],
            summary["created_at"],
            summary["updated_at"],
            summary["pushed_at"],
            summary["default_branch"],
            json.dumps(summary["topics"], ensure_ascii=False),
            summary["score"],
            summary["stars_per_day"],
            summary["fake_star_risk"],
            int(summary["archived"]),
            summary["license"],
            (summary.get("track_score") or {}).get("track"),
            (summary.get("track_score") or {}).get("score"),
            json.dumps(summary.get("track_score") or {}, ensure_ascii=False),
        ),
    )


def insert_health_snapshot(conn: sqlite3.Connection, run_id: int, summary: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO repository_health_snapshots (
            run_id, full_name, health_json
        ) VALUES (?, ?, ?)
        """,
        (
            run_id,
            summary["full_name"],
            json.dumps(summary.get("health") or {}, ensure_ascii=False),
        ),
    )


def persist_deep_snapshot(db_path: str, payload: dict) -> int:
    path = pathlib.Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        init_db(conn)
        cursor = conn.execute(
            "INSERT INTO runs (created_at, mode, repo_full_name, query_json) VALUES (?, ?, ?, ?)",
            (
                payload["generated_at"],
                payload["mode"],
                payload["repository"]["full_name"],
                json.dumps({"repo": payload["repository"]["full_name"]}, ensure_ascii=False),
            ),
        )
        run_id = int(cursor.lastrowid)
        insert_repo_snapshot(conn, run_id, payload["repository"])
        insert_health_snapshot(conn, run_id, payload["repository"])
        for item in payload["evidence"]:
            conn.execute(
                """
                INSERT INTO evidence_items (
                    run_id, repo_full_name, evidence_id, stable_id, level, kind, title, url, quote
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    payload["repository"]["full_name"],
                    item["evidence_id"],
                    item.get("stable_id"),
                    item["level"],
                    item["kind"],
                    item["title"],
                    item["url"],
                    item["quote"],
                ),
            )
        for item in payload["claims"]:
            conn.execute(
                """
                INSERT INTO claims (
                    run_id, repo_full_name, claim_id, field, text, evidence_ids_json, evidence_stable_ids_json, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    payload["repository"]["full_name"],
                    item.get("claim_id"),
                    item["field"],
                    item["text"],
                    json.dumps(item["evidence_ids"], ensure_ascii=False),
                    json.dumps(item.get("evidence_stable_ids") or [], ensure_ascii=False),
                    item["confidence"],
                ),
            )
        conn.commit()
        return run_id


def persist_discovery_snapshot(db_path: str, payload: dict) -> int:
    path = pathlib.Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        init_db(conn)
        cursor = conn.execute(
            "INSERT INTO runs (created_at, mode, repo_full_name, query_json) VALUES (?, ?, ?, ?)",
            (
                payload["generated_at"],
                payload["mode"],
                None,
                json.dumps(payload["query"], ensure_ascii=False),
            ),
        )
        run_id = int(cursor.lastrowid)
        for summary in payload["repositories"]:
            insert_repo_snapshot(conn, run_id, summary)
            insert_health_snapshot(conn, run_id, summary)
        conn.commit()
        return run_id


def safe_json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def normalize_repo_arg(value: str) -> str:
    normalized = value.strip().removesuffix("/")
    github_prefix = "https://github.com/"
    if normalized.startswith(github_prefix):
        normalized = normalized[len(github_prefix) :]
    return normalized.removesuffix(".git")


def row_to_archive_summary(row: sqlite3.Row) -> dict:
    full_name = row["full_name"]
    track_score = safe_json_loads(row["track_score_json"], {}) or {}
    if not track_score and (row["project_track"] or row["track_score"] is not None):
        track_score = {
            "track": row["project_track"] or "unknown",
            "score": row["track_score"] or 0.0,
            "signals": {},
            "weights": {},
            "rationale": ["loaded from an archived snapshot without full track score JSON"],
        }

    return {
        "run_id": row["run_id"],
        "run_created_at": row["run_created_at"],
        "run_mode": row["run_mode"],
        "dossier_id": stable_id("dossier", full_name),
        "full_name": full_name,
        "html_url": row["html_url"],
        "description": row["description"],
        "homepage": None,
        "language": row["language"],
        "stars": row["stars"],
        "forks": row["forks"],
        "watchers": row["watchers"],
        "open_issues": row["open_issues"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "pushed_at": row["pushed_at"],
        "default_branch": row["default_branch"],
        "topics": safe_json_loads(row["topics_json"], []),
        "score": row["score"],
        "stars_per_day": row["stars_per_day"],
        "fake_star_risk": row["fake_star_risk"],
        "archived": bool(row["archived"]),
        "license": row["license"],
        "track_score": track_score,
        "health": {},
    }


def connect_archive_db(db_path: str) -> sqlite3.Connection | None:
    path = pathlib.Path(db_path)
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def query_latest_archive_snapshots(
    conn: sqlite3.Connection,
    limit: int,
    track: str | None = None,
    min_track_score: float = 0.0,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.*, r.id AS run_id, r.created_at AS run_created_at, r.mode AS run_mode
        FROM repository_snapshots s
        JOIN runs r ON r.id = s.run_id
        WHERE s.run_id = (
            SELECT s2.run_id
            FROM repository_snapshots s2
            JOIN runs r2 ON r2.id = s2.run_id
            WHERE s2.full_name = s.full_name
            ORDER BY r2.created_at DESC, s2.run_id DESC
            LIMIT 1
        )
        AND (? IS NULL OR s.project_track = ?)
        AND (? <= 0 OR COALESCE(s.track_score, 0) >= ?)
        ORDER BY COALESCE(s.track_score, 0) DESC, s.stars DESC
        LIMIT ?
        """,
        (track, track, min_track_score, min_track_score, max(limit, 1)),
    ).fetchall()
    summaries = [row_to_archive_summary(row) for row in rows]
    for summary in summaries:
        summary["health"] = load_archive_health(conn, summary["run_id"], summary["full_name"])
    return summaries


def query_archive_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    track: str | None = None,
    min_track_score: float = 0.0,
) -> list[dict]:
    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT s.*, r.id AS run_id, r.created_at AS run_created_at, r.mode AS run_mode
        FROM repository_snapshots s
        JOIN runs r ON r.id = s.run_id
        WHERE s.run_id = (
            SELECT s2.run_id
            FROM repository_snapshots s2
            JOIN runs r2 ON r2.id = s2.run_id
            WHERE s2.full_name = s.full_name
            ORDER BY r2.created_at DESC, s2.run_id DESC
            LIMIT 1
        )
        AND (? IS NULL OR s.project_track = ?)
        AND (? <= 0 OR COALESCE(s.track_score, 0) >= ?)
        AND (
            LOWER(s.full_name) LIKE ?
            OR LOWER(COALESCE(s.description, '')) LIKE ?
            OR LOWER(COALESCE(s.language, '')) LIKE ?
            OR LOWER(COALESCE(s.topics_json, '')) LIKE ?
            OR EXISTS (
                SELECT 1
                FROM claims c
                WHERE c.repo_full_name = s.full_name
                AND LOWER(COALESCE(c.field, '') || ' ' || COALESCE(c.text, '')) LIKE ?
            )
            OR EXISTS (
                SELECT 1
                FROM evidence_items e
                WHERE e.repo_full_name = s.full_name
                AND LOWER(COALESCE(e.kind, '') || ' ' || COALESCE(e.title, '') || ' ' || COALESCE(e.quote, '')) LIKE ?
            )
        )
        ORDER BY COALESCE(s.track_score, 0) DESC, s.stars DESC
        LIMIT ?
        """,
        (
            track,
            track,
            min_track_score,
            min_track_score,
            like,
            like,
            like,
            like,
            like,
            like,
            max(limit, 1),
        ),
    ).fetchall()
    entries = []
    for row in rows:
        summary = row_to_archive_summary(row)
        summary["health"] = load_archive_health(conn, summary["run_id"], summary["full_name"])
        entries.append(
            {
                "repository": summary,
                "matched_claims": query_archive_claim_matches(conn, summary["full_name"], query),
                "matched_evidence": query_archive_evidence_matches(conn, summary["full_name"], query),
            }
        )
    return entries


def query_archive_show(conn: sqlite3.Connection, full_name: str) -> dict | None:
    normalized = normalize_repo_arg(full_name)
    row = conn.execute(
        """
        SELECT s.*, r.id AS run_id, r.created_at AS run_created_at, r.mode AS run_mode
        FROM repository_snapshots s
        JOIN runs r ON r.id = s.run_id
        WHERE LOWER(s.full_name) = LOWER(?)
        ORDER BY CASE WHEN r.mode = 'deep' THEN 0 ELSE 1 END, r.created_at DESC, s.run_id DESC
        LIMIT 1
        """,
        (normalized,),
    ).fetchone()
    if not row:
        return None
    summary = row_to_archive_summary(row)
    summary["health"] = load_archive_health(conn, summary["run_id"], summary["full_name"])
    return {
        "repository": summary,
        "claims": query_archive_claims(conn, summary["run_id"], summary["full_name"]),
        "evidence": query_archive_evidence(conn, summary["run_id"], summary["full_name"]),
    }


def load_archive_health(conn: sqlite3.Connection, run_id: int, full_name: str) -> dict:
    row = conn.execute(
        """
        SELECT health_json
        FROM repository_health_snapshots
        WHERE run_id = ? AND full_name = ?
        """,
        (run_id, full_name),
    ).fetchone()
    return safe_json_loads(row["health_json"], {}) if row else {}


def query_archive_claims(conn: sqlite3.Connection, run_id: int, full_name: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT claim_id, field, text, evidence_ids_json, evidence_stable_ids_json, confidence
        FROM claims
        WHERE run_id = ? AND repo_full_name = ?
        ORDER BY rowid
        """,
        (run_id, full_name),
    ).fetchall()
    return [
        {
            "claim_id": row["claim_id"],
            "field": row["field"],
            "text": row["text"],
            "evidence_ids": safe_json_loads(row["evidence_ids_json"], []),
            "evidence_stable_ids": safe_json_loads(row["evidence_stable_ids_json"], []),
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def query_archive_evidence(conn: sqlite3.Connection, run_id: int, full_name: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT evidence_id, stable_id, level, kind, title, url, quote
        FROM evidence_items
        WHERE run_id = ? AND repo_full_name = ?
        ORDER BY evidence_id
        """,
        (run_id, full_name),
    ).fetchall()
    return [
        {
            "evidence_id": row["evidence_id"],
            "stable_id": row["stable_id"],
            "level": row["level"],
            "kind": row["kind"],
            "title": row["title"],
            "url": row["url"],
            "quote": row["quote"],
        }
        for row in rows
    ]


def query_archive_claim_matches(conn: sqlite3.Connection, full_name: str, query: str, limit: int = 3) -> list[dict]:
    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT run_id, claim_id, field, text, confidence
        FROM claims
        WHERE repo_full_name = ?
        AND LOWER(COALESCE(field, '') || ' ' || COALESCE(text, '')) LIKE ?
        ORDER BY run_id DESC, rowid
        LIMIT ?
        """,
        (full_name, like, limit),
    ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "claim_id": row["claim_id"],
            "field": row["field"],
            "text": row["text"],
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def query_archive_evidence_matches(conn: sqlite3.Connection, full_name: str, query: str, limit: int = 3) -> list[dict]:
    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT run_id, evidence_id, stable_id, kind, title, url, quote
        FROM evidence_items
        WHERE repo_full_name = ?
        AND LOWER(COALESCE(kind, '') || ' ' || COALESCE(title, '') || ' ' || COALESCE(quote, '')) LIKE ?
        ORDER BY run_id DESC, evidence_id
        LIMIT ?
        """,
        (full_name, like, limit),
    ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "evidence_id": row["evidence_id"],
            "stable_id": row["stable_id"],
            "kind": row["kind"],
            "title": row["title"],
            "url": row["url"],
            "quote": row["quote"],
        }
        for row in rows
    ]


def archive_message_payload(mode: str, args: argparse.Namespace, message: str) -> dict:
    return {
        "schema_version": 1,
        "mode": mode,
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "message": message,
    }


def archive_filters_payload(args: argparse.Namespace) -> dict:
    return {
        "limit": args.limit,
        "track": args.archive_track,
        "min_track_score": args.min_track_score,
    }


def archive_list_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    return {
        "schema_version": 1,
        "mode": "archive_list",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "filters": archive_filters_payload(args),
        "repositories": query_latest_archive_snapshots(
            conn,
            args.limit,
            track=args.archive_track,
            min_track_score=args.min_track_score,
        ),
    }


def archive_search_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    query = args.archive_search.strip()
    return {
        "schema_version": 1,
        "mode": "archive_search",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "query": query,
        "filters": archive_filters_payload(args),
        "matches": query_archive_search(
            conn,
            query,
            args.limit,
            track=args.archive_track,
            min_track_score=args.min_track_score,
        ),
    }


def archive_show_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    dossier = query_archive_show(conn, args.archive_show)
    payload = {
        "schema_version": 1,
        "mode": "archive_show",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "repository_query": args.archive_show,
    }
    if dossier is None:
        payload["message"] = f"No archived repository found for {args.archive_show}."
        return payload
    payload.update(dossier)
    return payload


def archive_score_text(summary: dict) -> str:
    score = summary.get("track_score") or {}
    track = score.get("track") or "unknown"
    value = score.get("score")
    if isinstance(value, (int, float)):
        return f"{track} / {value:.1f}"
    return f"{track} / unknown"


def one_line(value: str | None, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def render_archive_repo_brief(summary: dict, db_path: str) -> list[str]:
    topics = ", ".join(summary.get("topics") or []) or "无"
    return [
        summary.get("description") or "无描述。",
        "",
        f"- 链接：{summary.get('html_url') or '无'}",
        f"- 最近归档：run_id={summary.get('run_id')} / {summary.get('run_created_at')} / {summary.get('run_mode')}",
        f"- 语言：{summary.get('language') or '未知'}",
        f"- Stars：{summary.get('stars', 0)}",
        f"- Forks：{summary.get('forks', 0)}",
        f"- Open issues：{summary.get('open_issues', 0)}",
        f"- Track score：{archive_score_text(summary)}",
        f"- Dossier ID：{summary.get('dossier_id')}",
        f"- Fake-star 风险：{summary.get('fake_star_risk') or '未知'}",
        f"- Topics：{topics}",
        f"- 查看档案：`python3 radar.py --archive-show {summary.get('full_name')} --db {db_path}`",
    ]


def render_archive_list(payload: dict) -> str:
    if payload.get("message"):
        return "\n".join(["# OSS Cognition Archive", "", payload["message"], ""])
    lines = [
        "# OSS Cognition Archive",
        "",
        f"- 数据库：{payload['db']}",
        f"- 生成时间：{payload['generated_at']}",
        f"- 结果数：{len(payload['repositories'])}",
        f"- Track 过滤：{payload['filters'].get('track') or '无'}",
        f"- 最低 track score：{payload['filters'].get('min_track_score') or 0}",
        "",
    ]
    for index, summary in enumerate(payload["repositories"], 1):
        lines.extend([f"## {index}. {summary['full_name']}", ""])
        lines.extend(render_archive_repo_brief(summary, payload["db"]))
        lines.append("")
    return "\n".join(lines)


def render_archive_search(payload: dict) -> str:
    if payload.get("message"):
        return "\n".join(["# OSS Cognition Archive Search", "", payload["message"], ""])
    lines = [
        "# OSS Cognition Archive Search",
        "",
        f"- 数据库：{payload['db']}",
        f"- 查询：{payload['query']}",
        f"- 结果数：{len(payload['matches'])}",
        f"- Track 过滤：{payload['filters'].get('track') or '无'}",
        f"- 最低 track score：{payload['filters'].get('min_track_score') or 0}",
        "",
    ]
    for index, entry in enumerate(payload["matches"], 1):
        summary = entry["repository"]
        lines.extend([f"## {index}. {summary['full_name']}", ""])
        lines.extend(render_archive_repo_brief(summary, payload["db"]))
        lines.append("")
        if entry["matched_claims"]:
            lines.extend(["### Matched claims", ""])
            for claim in entry["matched_claims"]:
                lines.extend(
                    [
                        f"- `{claim.get('claim_id') or 'no-claim-id'}` {claim['field']} ({claim['confidence']}): "
                        f"{one_line(claim['text'])}",
                    ]
                )
            lines.append("")
        if entry["matched_evidence"]:
            lines.extend(["### Matched evidence", ""])
            for item in entry["matched_evidence"]:
                lines.extend(
                    [
                        f"- `{item.get('stable_id') or item.get('evidence_id')}` {item['kind']} - {item['title']}: "
                        f"{one_line(item['quote'])}",
                    ]
                )
            lines.append("")
    return "\n".join(lines)


def render_archive_show(payload: dict) -> str:
    if payload.get("message"):
        return "\n".join(["# OSS Cognition Archived Dossier", "", payload["message"], ""])

    summary = payload["repository"]
    lines = [
        "# OSS Cognition Archived Dossier",
        "",
        f"- 数据库：{payload['db']}",
        f"- 生成时间：{payload['generated_at']}",
        "",
        f"## {summary['full_name']}",
        "",
    ]
    lines.extend(render_archive_repo_brief(summary, payload["db"]))
    lines.append("")
    lines.extend(render_repository_health(summary))
    lines.extend(render_track_score(summary))
    lines.extend(["", "## Claims", ""])
    if not payload.get("claims"):
        lines.extend(["该归档快照没有深度 claim；请先运行 `python3 radar.py --repo owner/name`。", ""])
    for claim in payload.get("claims", []):
        stable_refs = claim.get("evidence_stable_ids") or []
        refs = ", ".join(f"`{item}`" for item in stable_refs) if stable_refs else evidence_refs(claim.get("evidence_ids") or [])
        lines.extend(
            [
                f"### {claim['field']}",
                "",
                claim["text"],
                "",
                f"- Claim ID：`{claim.get('claim_id') or '无'}`",
                f"- 证据：{refs}",
                f"- 置信度：{claim['confidence']}",
                "",
            ]
        )

    lines.extend(["## Evidence", ""])
    if not payload.get("evidence"):
        lines.extend(["该归档快照没有证据链。", ""])
    for item in payload.get("evidence", []):
        lines.extend(
            [
                f"### {item['evidence_id']}. {item['kind']} - {item['title']}",
                "",
                f"- Stable ID：`{item.get('stable_id') or '无'}`",
                f"- 证据层级：L{item['level']}",
                f"- 链接：{item.get('url') or '无'}",
                f"- 摘录：{textwrap.fill(item.get('quote') or '无摘录。', width=88)}",
                "",
            ]
        )
    return "\n".join(lines)


def emit_archive_result(markdown: str, payload: dict, args: argparse.Namespace) -> None:
    if args.archive_output:
        write_report(args.archive_output, markdown)
    else:
        print(markdown)
    if args.json_output:
        write_json(args.json_output, payload)


def handle_archive(args: argparse.Namespace) -> None:
    modes = [
        bool(args.archive_list),
        args.archive_search is not None,
        args.archive_show is not None,
    ]
    if sum(modes) != 1:
        raise SystemExit("Choose exactly one archive mode: --archive-list, --archive-search, or --archive-show.")
    if args.archive_search is not None and not args.archive_search.strip():
        raise SystemExit("--archive-search requires non-empty text.")

    conn = connect_archive_db(args.db)
    if conn is None:
        payload = archive_message_payload("archive", args, f"Archive database not found: {args.db}")
        emit_archive_result(render_archive_list(payload), payload, args)
        return

    try:
        with conn:
            if args.archive_list:
                payload = archive_list_payload(conn, args)
                markdown = render_archive_list(payload)
            elif args.archive_search is not None:
                payload = archive_search_payload(conn, args)
                markdown = render_archive_search(payload)
            else:
                payload = archive_show_payload(conn, args)
                markdown = render_archive_show(payload)
    finally:
        conn.close()
    emit_archive_result(markdown, payload, args)


def render_star_growth(summary: dict) -> list[str]:
    growth = summary.get("star_growth") or empty_star_growth()
    lines = ["- Star growth:"]
    for label in GROWTH_WINDOWS:
        item = growth.get(label) or {}
        if item.get("available"):
            days_between_value = item.get("days_between")
            days_text = f"{days_between_value:.1f}d" if isinstance(days_between_value, (int, float)) else "unknown"
            lines.append(
                f"  - {label}: {item['delta']:+d} stars since {item['baseline_at']} ({days_text})"
            )
        else:
            lines.append(f"  - {label}: insufficient history")
    return lines


def render_repository_health(summary: dict) -> list[str]:
    health = summary.get("health") or {}
    if not health:
        return ["- Repository health: unavailable"]
    lines = [
        "- Repository health:",
        f"  - merged PRs / 180d: {health.get('merged_prs_180d', 'unknown')}",
        f"  - closed issues / 180d: {health.get('closed_issues_180d', 'unknown')}",
        f"  - open PRs: {health.get('open_prs', 'unknown')}",
        f"  - releases in latest API sample / 365d: {health.get('release_count_365d_sample', 0)}",
        f"  - latest release: {health.get('latest_release_at') or 'unknown'}",
        f"  - contributor sample size: {health.get('top_contributor_count_sample', 0)}",
    ]
    contributors = health.get("top_contributors") or []
    if contributors:
        top = ", ".join(
            f"{item.get('login')}({item.get('contributions', 0)})"
            for item in contributors[:5]
            if item.get("login")
        )
        lines.append(f"  - top contributors sample: {top}")
    return lines


def render_track_score(summary: dict) -> list[str]:
    score = summary.get("track_score") or {}
    if not score:
        return ["- Track score: unavailable"]
    signals = score.get("signals") or {}
    signal_text = ", ".join(f"{name}={value}" for name, value in signals.items())
    return [
        f"- Project track: {score.get('track', 'unknown')}",
        f"- Track score: {score.get('score', 0):.1f}",
        f"- Track signals: {signal_text}",
    ]


def build_claims(repo: dict, evidence: list[Evidence]) -> list[Claim]:
    text = corpus(evidence, repo)
    claims = [
        Claim("领域", infer_domain(repo, text), matching_evidence(evidence, ["agent", "cli", "local-first", "protocol"]), "medium"),
        claim_problem_frame(evidence, repo, text),
        claim_key_abstractions(evidence, text),
        claim_boundaries(evidence, text),
        claim_complexity(evidence, text),
        claim_governance(evidence, text),
        Claim(
            "可复用思想",
            "把公开工程工件拆成问题重定义、关键抽象、边界声明、复杂度藏处和治理方式，再把这些模式迁移到自己的设计评审中。",
            [item.evidence_id for item in evidence[:3]],
            "medium",
        ),
        Claim(
            "不可复制条件",
            "热度、生态位、品牌、发布时间窗口和既有社区势能不可直接复制；可迁移的是方法，不是势能本身。",
            [item.evidence_id for item in evidence[:3]],
            "medium",
        ),
    ]
    for claim in claims:
        claim.claim_id = stable_id("claim", repo["full_name"], claim.field)
    return claims


def render_evidence_table(evidence: list[Evidence]) -> list[str]:
    lines = ["### 证据链", ""]
    if not evidence:
        return lines + ["未抓到可用证据。", ""]
    for item in evidence:
        lines.extend(
            [
                f"**{item.evidence_id}. {item.kind} - {item.title}**",
                "",
                f"- Stable ID：`{item.stable_id}`",
                f"- 证据层级：L{item.level}",
                f"- 链接：{item.url or '无'}",
                f"- 摘录：{textwrap.fill(item.quote or '无摘录。', width=88)}",
                "",
            ]
        )
    return lines


def render_deep_report(repo: dict, summary: dict, evidence: list[Evidence], claims: list[Claim]) -> str:
    now = dt.datetime.now(dt.UTC)
    topics = ", ".join(repo.get("topics") or []) or "无"
    lines = [
        "# OSS 认知模式项目档案",
        "",
        f"- 生成时间：{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 项目：{summary['full_name']}",
        f"- 链接：{summary['html_url']}",
        f"- 描述：{summary.get('description') or '无'}",
        f"- 语言：{summary.get('language') or '未知'}",
        f"- Stars：{summary['stars']}",
        f"- Forks：{summary['forks']}",
        f"- Open issues：{summary['open_issues']}",
        f"- 创建时间：{summary['created_at']}",
        f"- 最近推送：{summary['pushed_at']}",
        f"- Star/day：{summary['stars_per_day']:.1f}",
        f"- Dossier ID：{summary['dossier_id']}",
        f"- Topics：{topics}",
        "",
    ]
    lines.extend(render_star_growth(summary))
    lines.extend(render_repository_health(summary))
    lines.extend(render_track_score(summary))
    lines.extend(
        [
            "",
            "## 方法边界",
            "",
            "本报告只根据公开 GitHub 工程痕迹归纳可观察、可复核、可迁移的认知与治理模式；它不声称证明作者私密动机或完整心理本质。",
            "",
            "## 项目档案",
            "",
        ]
    )
    for claim in claims:
        lines.extend(
            [
                f"### {claim.field}",
                "",
                claim.text,
                "",
                f"- Claim ID：`{claim.claim_id}`",
                f"- 证据：{evidence_refs(claim.evidence_ids)}",
                f"- 置信度：{claim.confidence}",
                "",
            ]
        )

    lines.extend(
        [
            "## 风险与复核",
            "",
            f"- Fake-star 风险：{fake_star_risk(repo)}",
            "- 复核建议：优先人工阅读证据链中涉及 README 第一屏、examples、最近 release、高评论 issue 和最近合并 PR 的条目。",
            "",
        ]
    )
    lines.extend(render_evidence_table(evidence))
    return "\n".join(lines)


def render_discovery_report(repo_summaries: list[dict], args: argparse.Namespace) -> str:
    now = dt.datetime.now(dt.UTC)
    lines = [
        "# OSS Cognition Radar",
        "",
        f"- 生成时间：{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"- 时间窗口：最近 {args.days} 天创建",
        f"- 最低 star：{args.min_stars}",
        f"- 主题过滤：{args.topic or '无'}",
        f"- 语言过滤：{args.language or '无'}",
        "",
        "这个视图只负责发现候选项目。要提炼认知模式，请使用：",
        "",
        "```bash",
        "python3 radar.py --repo owner/name --output reports/owner-name.md",
        "```",
        "",
    ]

    for index, summary in enumerate(repo_summaries, 1):
        topics = ", ".join(summary.get("topics") or []) or "无"
        lines.extend(
            [
                f"## {index}. {summary['full_name']}",
                "",
                summary.get("description") or "无描述。",
                "",
                f"- 链接：{summary['html_url']}",
                f"- 语言：{summary.get('language') or '未知'}",
                f"- Stars：{summary['stars']}",
                f"- Forks：{summary['forks']}",
                f"- Open issues：{summary['open_issues']}",
                f"- Star/day：{summary['stars_per_day']:.1f}",
                f"- Dossier ID：{summary['dossier_id']}",
                f"- Radar score：{summary['score']:.1f}",
                f"- Fake-star 风险：{summary['fake_star_risk']}",
                f"- Topics：{topics}",
            ]
        )
        lines.extend(render_star_growth(summary))
        lines.extend(render_repository_health(summary))
        lines.extend(render_track_score(summary))
        lines.append("")
    return "\n".join(lines)


def write_report(path: str, content: str) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"Wrote {output}.")


def write_json(path: str, payload: dict) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}.")


def main() -> None:
    args = parse_args()
    run_at = utc_now()

    if args.archive_list or args.archive_search is not None or args.archive_show is not None:
        handle_archive(args)
        return

    if args.repo:
        repo = fetch_repository(args.repo)
        evidence = build_evidence(repo)
        claims = build_claims(repo, evidence)
        payload = build_deep_payload(repo, evidence, claims, run_at)
        attach_star_growth([payload["repository"]], None if args.no_db else args.db, run_at)
        attach_track_scores(
            [payload["repository"]],
            evidence_counts={payload["repository"]["full_name"]: len(evidence)},
            claim_counts={payload["repository"]["full_name"]: len(claims)},
        )
        write_report(args.output, render_deep_report(repo, payload["repository"], evidence, claims))
        if args.json_output:
            write_json(args.json_output, payload)
        if not args.no_db:
            run_id = persist_deep_snapshot(args.db, payload)
            print(f"Stored SQLite snapshot run_id={run_id} in {args.db}.")
        return

    candidates = search_repositories(args.days, args.min_stars, args.topic, args.language, args.limit)
    for repo in candidates:
        repo["_score"] = score_repo(repo, run_at)
    repos = sorted(candidates, key=lambda item: item["_score"], reverse=True)[: args.limit]
    repo_summaries = [repo_summary(repo, run_at) for repo in repos]
    attach_star_growth(repo_summaries, None if args.no_db else args.db, run_at)
    attach_track_scores(repo_summaries)
    payload = build_discovery_payload(repo_summaries, args, run_at)
    write_report(args.output, render_discovery_report(repo_summaries, args))
    if args.json_output:
        write_json(args.json_output, payload)
    if not args.no_db:
        run_id = persist_discovery_snapshot(args.db, payload)
        print(f"Stored SQLite snapshot run_id={run_id} in {args.db}.")


if __name__ == "__main__":
    main()
