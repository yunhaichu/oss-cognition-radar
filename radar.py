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
MAX_IMPLEMENTATION_FILE_SIZE = 120_000
GROWTH_WINDOWS = {"1d": 1, "7d": 7, "30d": 30}
GROWTH_MAX_AGE_DAYS = {"1d": 2, "7d": 10, "30d": 45}
ARCHIVE_SEARCH_INDEX_VERSION = 9
BINDING_CONFIDENCE_BASE = 35
BINDING_CONFIDENCE_SIGNAL_WEIGHTS = {
    "requested_missing_layer": 22,
    "target_layer": 12,
    "evidence_layer_match": 18,
    "stable_artifact_url": 5,
    "typed_evidence": 5,
}
BINDING_CONFIDENCE_KEYWORD_HIT_WEIGHT = 5
BINDING_CONFIDENCE_KEYWORD_HIT_MAX = 15
AUTO_CONFIDENCE_CALIBRATION = "archive_auto_v1"
AUTO_CONFIDENCE_ARCHIVE_WEIGHTS = {
    "cross_version_binding_3plus": 9,
    "cross_version_binding_2plus": 5,
    "cross_version_evidence_drift": -4,
    "repo_history_3plus": 3,
    "repo_activity_sustained": 4,
    "repo_activity_declining": -8,
    "release_cadence_stable": 3,
    "release_cadence_missing": -7,
    "source_or_validation_evidence": 9,
    "configuration_or_release_evidence": 6,
    "generic_evidence": -9,
    "negative_or_boundary_polarity": -12,
    "stable_artifact_url": 2,
    "keyword_sparse": -7,
}
AUTO_CONFIDENCE_REPEAT_THRESHOLDS = {
    "cross_project_repositories": [5, 3, 2],
    "repeated_bindings": [5, 3],
}
AUTO_CONFIDENCE_SCORING = {
    "base": 42,
    "heuristic_floor": 55,
    "heuristic_scale": 0.45,
    "heuristic_max": 22,
    "repeat_repo_weight": 3.5,
    "repeat_binding_weight": 0.9,
    "repeat_max": 22,
    "high_threshold": 85,
    "medium_threshold": 65,
}
CONFIDENCE_SIGNAL_GROUPS = [
    ("time_series", "Time series"),
    ("drift", "Version drift"),
    ("pattern", "Archive pattern"),
    ("evidence", "Evidence quality"),
    ("calibration", "Calibration"),
    ("other", "Other"),
]
CONFIDENCE_SIGNAL_GROUP_CHOICES = [group for group, _label in CONFIDENCE_SIGNAL_GROUPS]
PATTERN_SIGNAL_GROUP_WEIGHTS = {
    "time_series": 10,
    "drift": 10,
    "pattern": 5,
    "evidence": 5,
    "calibration": 0,
    "other": 0,
}
SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
    ".rb",
    ".php",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
}
CONFIG_FILENAMES = {
    "package.json",
    "pyproject.toml",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "gradle.properties",
    "requirements.txt",
    "setup.py",
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "makefile",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    ".github/workflows/test.yml",
}
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
    evidence_type: str = "general"
    polarity: str = "supporting"
    signal_tags: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Claim:
    """An inferred project-level claim with supporting evidence."""

    field: str
    text: str
    evidence_ids: list[str]
    confidence: str
    claim_id: str = ""
    template: str = ""
    rationale: str = ""
    counter_evidence_ids: list[str] = dataclasses.field(default_factory=list)
    support_coverage: dict[str, object] = dataclasses.field(default_factory=dict)


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
        "--archive-patterns",
        action="store_true",
        help="Group archived acquisition bindings into cross-project claim-gap repair patterns.",
    )
    parser.add_argument(
        "--archive-auto-calibrate",
        action="store_true",
        help="Automatically recalibrate archived acquisition binding confidence from archive evidence signals.",
    )
    parser.add_argument(
        "--archive-dashboard",
        nargs="?",
        const="reports/archive-dashboard.html",
        metavar="PATH",
        help="Generate a standalone HTML dashboard from the SQLite archive.",
    )
    parser.add_argument(
        "--archive-track",
        choices=sorted(TRACK_WEIGHTS),
        help="Archive mode: filter repositories by project track.",
    )
    parser.add_argument("--min-track-score", type=float, default=0.0, help="Archive mode: minimum track score.")
    parser.add_argument(
        "--archive-signal-group",
        choices=CONFIDENCE_SIGNAL_GROUP_CHOICES,
        help="Archive patterns/dashboard mode: filter acquisition patterns by automatic confidence signal group.",
    )
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


def infer_signal_tags(kind: str, title: str, quote: str) -> list[str]:
    text = f"{kind} {title} {quote}".lower()
    rules = {
        "problem_frame": ["problem", "why", "goal", "build", "solve", "定位", "目标"],
        "abstraction": ["api", "sdk", "graph", "node", "workflow", "protocol", "interface", "plugin"],
        "boundary": ["not", "non-goal", "unsupported", "experimental", "preview", "deprecated", "archival", "no longer", "限制", "边界"],
        "complexity": ["bug", "error", "issue", "compatibility", "migration", "concurrency", "state", "cache", "timeout"],
        "governance": ["contributing", "code of conduct", "security", "issue template", "discussion", "roadmap"],
        "recoverability": ["durable", "checkpoint", "resume", "recover", "interrupt", "rollback"],
        "performance": ["fast", "performance", "latency", "memory", "benchmark"],
        "local_control": ["local-first", "self-host", "offline", "sync", "privacy"],
        "release_cadence": ["release", "changelog", "version", "breaking", "migration"],
        "security": ["security", "encryption", "vulnerability", "cve"],
        "implementation": ["class ", "def ", "function ", "interface ", "struct ", "impl ", "module ", "export "],
        "test_strategy": ["test", "spec", "assert", "fixture", "mock", "snapshot", "pytest", "describe("],
        "configuration": ["dependencies", "scripts", "workspace", "tool.", "lint", "build", "ci", "workflow"],
    }
    return [tag for tag, words in rules.items() if has_any(text, words)]


def infer_evidence_type(kind: str, title: str, quote: str) -> str:
    text = f"{title} {quote}".lower()
    if kind == "README":
        return "positioning"
    if kind == "Release":
        return "release_delta"
    if kind == "Issue":
        return "user_friction"
    if kind == "Pull Request":
        return "implementation_change"
    if kind == "Source":
        return "source_entrypoint"
    if kind == "Test":
        return "test_surface"
    if kind == "Benchmark":
        return "benchmark"
    if kind == "Config":
        return "configuration"
    if has_any(text, ["contributing", "code of conduct", "security", "issue template", "pull_request_template"]):
        return "governance"
    if has_any(text, ["architecture", "roadmap", "non-goal", "not ready", "experimental", "deprecated", "archival", "no longer"]):
        return "boundary"
    if has_any(text, ["quickstart", "getting-started", "examples", "usage"]):
        return "usage_surface"
    return "supporting_artifact"


def infer_polarity(kind: str, title: str, quote: str, evidence_type: str) -> str:
    text = f"{kind} {title} {quote}".lower()
    if evidence_type == "boundary" or has_any(
        text,
        ["non-goal", "unsupported", "experimental", "preview", "deprecated", "archival", "no longer", "not ready"],
    ):
        return "boundary"
    negative_terms = ["bug", "confusing", "annoying", "broken", "failed", "failure", "regression", "crash"]
    if kind == "Issue" or any(re.search(rf"\b{re.escape(term)}\b", text) for term in negative_terms):
        return "negative"
    return "supporting"


def make_evidence(
    evidence_id: str,
    level: int,
    kind: str,
    title: str,
    url: str,
    quote: str,
    evidence_type: str | None = None,
) -> Evidence:
    resolved_type = evidence_type or infer_evidence_type(kind, title, quote)
    tags = infer_signal_tags(kind, title, quote)
    return Evidence(
        evidence_id,
        level,
        kind,
        title,
        url,
        quote,
        evidence_type=resolved_type,
        polarity=infer_polarity(kind, title, quote, resolved_type),
        signal_tags=tags,
    )


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


def path_parts(path: str) -> list[str]:
    return [part.lower() for part in path.split("/") if part]


def source_extension(path: str) -> str:
    return pathlib.PurePosixPath(path).suffix.lower()


def is_generated_or_vendor_path(path: str) -> bool:
    lowered = path.lower()
    parts = set(path_parts(path))
    if parts & {"node_modules", "vendor", "dist", "build", "target", ".next", "coverage", "__pycache__"}:
        return True
    return any(
        marker in lowered
        for marker in [
            ".min.js",
            ".bundle.js",
            "generated",
            "snapshot",
            "fixtures/",
            "testdata/",
            "golden/",
        ]
    )


def classify_implementation_path(path: str) -> str | None:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = set(path_parts(path))
    suffix = source_extension(path)
    if is_generated_or_vendor_path(path):
        return None
    if (
        "benchmark" in parts
        or "benchmarks" in parts
        or "benches" in parts
        or name.startswith(("bench_", "benchmark_"))
        or name.endswith(("_bench.py", "_benchmark.py", "_bench_test.go"))
    ):
        return "benchmark"
    if (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or name.startswith(("test_", "spec_"))
        or name.endswith(("_test.go", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", "_test.py"))
    ):
        return "test_surface"
    if lowered in CONFIG_FILENAMES or name in CONFIG_FILENAMES:
        return "configuration"
    if suffix in SOURCE_EXTENSIONS:
        return "source_entrypoint"
    return None


def implementation_path_score(path: str, evidence_type: str, repo: dict) -> tuple[int, int, str]:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    stem = pathlib.PurePosixPath(name).stem
    parts = path_parts(path)
    repo_name = (repo.get("name") or "").lower().replace("-", "_")
    score = 0

    if evidence_type == "configuration":
        score += 80
        if name in {"pyproject.toml", "package.json", "cargo.toml", "go.mod"}:
            score += 20
        if lowered.startswith(".github/workflows/"):
            score += 8
    elif evidence_type == "benchmark":
        score += 70
        if "benchmark" in lowered:
            score += 15
    elif evidence_type == "test_surface":
        score += 60
        if name.startswith("test_") or name.endswith(("_test.py", "_test.go")):
            score += 12
    else:
        score += 50
        if name in {"index.ts", "index.js", "main.py", "main.go", "lib.rs", "mod.rs", "__init__.py"}:
            score += 28
        if stem in {"api", "client", "server", "core", "graph", "runtime", "engine", "state", "model"}:
            score += 20
        if parts and parts[0] in {"src", "lib", "libs", "pkg", "packages", "crates", "internal", "cmd"}:
            score += 16
        if repo_name and repo_name in lowered.replace("-", "_"):
            score += 10
        if "example" in parts or "examples" in parts:
            score -= 18

    depth_penalty = min(len(parts), 10)
    return (-score, depth_penalty, lowered)


def implementation_paths(files: list[dict], repo: dict) -> list[tuple[str, str]]:
    buckets: dict[str, list[tuple[tuple[int, int, str], str]]] = {
        "source_entrypoint": [],
        "test_surface": [],
        "benchmark": [],
        "configuration": [],
    }
    limits = {
        "source_entrypoint": 5,
        "test_surface": 4,
        "benchmark": 3,
        "configuration": 4,
    }
    for item in files:
        path = item.get("path") or ""
        if not path:
            continue
        size = item.get("size") or 0
        if size and size > MAX_IMPLEMENTATION_FILE_SIZE:
            continue
        evidence_type = classify_implementation_path(path)
        if not evidence_type:
            continue
        buckets[evidence_type].append((implementation_path_score(path, evidence_type, repo), path))

    selected: list[tuple[str, str]] = []
    for evidence_type in ("source_entrypoint", "test_surface", "benchmark", "configuration"):
        ranked = sorted(buckets[evidence_type], key=lambda item: item[0])
        selected.extend((path, evidence_type) for _, path in ranked[: limits[evidence_type]])
    return selected


def implementation_kind(evidence_type: str) -> str:
    return {
        "source_entrypoint": "Source",
        "test_surface": "Test",
        "benchmark": "Benchmark",
        "configuration": "Config",
    }.get(evidence_type, "File")


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


def fetch_releases_sample(full_name: str, per_page: int = 5) -> list[dict]:
    data = github_get_optional(f"/repos/{full_name}/releases", {"per_page": per_page})
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


def fetch_issue_search(full_name: str, query_suffix: str, per_page: int = 2) -> list[dict]:
    data = github_get_optional(
        "/search/issues",
        {
            "q": f"repo:{full_name} {query_suffix}",
            "sort": "comments",
            "order": "desc",
            "per_page": per_page,
        },
    )
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
        evidence.append(
            make_evidence(
                "E1",
                1,
                "README",
                "Project positioning and first-screen narrative",
                readme_url,
                excerpt(readme, 900),
                "positioning",
            )
        )

    files = fetch_tree_files(repo)
    selected_doc_paths = important_paths(files)
    selected_doc_path_set = set(selected_doc_paths)
    for path in selected_doc_paths:
        text, url = fetch_file_text(repo, path)
        if text:
            evidence.append(make_evidence(f"E{len(evidence) + 1}", 1, "File", path, url, excerpt(text, 700)))

    for path, evidence_type in implementation_paths(files, repo):
        if path in selected_doc_path_set:
            continue
        text, url = fetch_file_text(repo, path)
        if text:
            evidence.append(
                make_evidence(
                    f"E{len(evidence) + 1}",
                    1,
                    implementation_kind(evidence_type),
                    path,
                    url,
                    excerpt(text, 700),
                    evidence_type,
                )
            )

    for release in fetch_releases(full_name):
        title = release.get("name") or release.get("tag_name") or "Release"
        body = release.get("body") or ""
        quote = excerpt(body, 550) or f"Published at {release.get('published_at') or 'unknown time'}."
        evidence.append(
            make_evidence(f"E{len(evidence) + 1}", 1, "Release", title, release.get("html_url") or "", quote)
        )

    for issue in fetch_issues(full_name):
        quote = excerpt(issue.get("body") or "", 500) or f"{issue.get('comments', 0)} comments; state={issue.get('state')}."
        evidence.append(
            make_evidence(f"E{len(evidence) + 1}", 1, "Issue", issue.get("title") or "Issue", issue.get("html_url") or "", quote)
        )

    for pr in fetch_pull_requests(full_name):
        quote = excerpt(pr.get("body") or "", 500) or f"state={pr.get('state')}; merged_at={pr.get('merged_at')}."
        evidence.append(
            make_evidence(f"E{len(evidence) + 1}", 1, "Pull Request", pr.get("title") or "Pull request", pr.get("html_url") or "", quote)
        )

    assign_evidence_ids(repo, evidence)
    return evidence


GAP_LAYER_TO_IMPLEMENTATION_TYPE = {
    "source": "source_entrypoint",
    "tests": "test_surface",
    "benchmarks": "benchmark",
    "configuration": "configuration",
}
TARGETED_IMPLEMENTATION_LIMITS = {
    "source_entrypoint": 5,
    "test_surface": 5,
    "benchmark": 3,
    "configuration": 3,
}
TARGETED_PER_GAP_LAYER_LIMITS = {
    "source_entrypoint": 2,
    "test_surface": 2,
    "benchmark": 1,
    "configuration": 1,
}
CLAIM_FIELD_KEYWORDS = {
    "作者如何重新定义问题": ["durable", "checkpoint", "workflow", "roadmap", "proposal", "feedback", "problem"],
    "关键抽象": ["api", "interface", "graph", "node", "workflow", "checkpoint", "runtime", "client", "server", "sdk"],
    "架构边界": ["boundary", "unsupported", "deprecated", "internal", "experimental", "limit", "policy"],
    "复杂度藏处": ["bug", "error", "performance", "compatibility", "concurrency", "checkpoint", "state", "memory", "latency"],
    "治理模式": ["contributing", "security", "issue", "template", "support", "discussion", "maintainer", "review"],
    "可复用思想": ["example", "adoption", "pattern", "discussion", "integration", "extension"],
    "不可复制条件": ["roadmap", "release", "community", "adoption", "ecosystem", "migration"],
    "实现层复核线索": ["source", "test", "benchmark", "config", "api", "runtime"],
    "领域": ["api", "sdk", "agent", "cli", "protocol", "server"],
}
LAYER_KEYWORDS = {
    "source": ["src", "lib", "core", "api", "runtime", "engine", "server", "client"],
    "tests": ["test", "spec", "suite", "conformance", "integration", "e2e"],
    "benchmarks": ["benchmark", "bench", "performance", "latency", "memory"],
    "configuration": ["config", "workflow", "ci", "package", "pyproject", "cargo", "module"],
    "collaboration": ["issue", "pr", "discussion", "support", "bug", "feedback"],
    "release": ["release", "changelog", "migration", "version", "breaking"],
}


def evidence_key(item: Evidence) -> str:
    return item.url or f"{item.kind}:{item.title}"


def ordered_missing_layers(gaps: list[dict]) -> list[str]:
    layers: list[str] = []
    for gap in gaps:
        for layer in gap.get("missing_layers") or []:
            if layer not in layers:
                layers.append(layer)
    return layers


def sorted_gaps_for_acquisition(gaps: list[dict]) -> list[dict]:
    return sorted(
        gaps,
        key=lambda item: (
            -(item.get("priority_score") or 0),
            item.get("support_score") or 0,
            item.get("field") or "",
        ),
    )


def unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for term in terms:
        cleaned = str(term or "").strip().lower()
        if len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def claim_gap_keywords(gap: dict) -> list[str]:
    field = gap.get("field") or ""
    terms = CLAIM_FIELD_KEYWORDS.get(field, []).copy()
    for layer in (gap.get("missing_layers") or []) + (gap.get("target_layers") or []):
        terms.extend(LAYER_KEYWORDS.get(layer, []))
    terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}", " ".join([field, gap.get("recommendation") or ""])))
    return unique_terms(terms)[:12]


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    lowered = text.lower().replace("-", "_")
    return sum(1 for keyword in keywords if keyword.replace("-", "_") in lowered)


def targeted_path_score(path: str, evidence_type: str, repo: dict, gap: dict) -> tuple[int, int, int, str]:
    base_score, depth_penalty, lowered = implementation_path_score(path, evidence_type, repo)
    keywords = claim_gap_keywords(gap)
    keyword_bonus = keyword_hit_count(path, keywords) * 18
    layer = evidence_support_layer(
        Evidence("", 0, implementation_kind(evidence_type), path, "", "", evidence_type=evidence_type)
    )
    layer_bonus = 10 if layer in (gap.get("missing_layers") or []) else 0
    priority_bonus = min(int(gap.get("priority_score") or 0), 100) // 10
    return (base_score - keyword_bonus - layer_bonus - priority_bonus, -keyword_bonus, depth_penalty, lowered)


def targeted_implementation_paths(
    files: list[dict],
    repo: dict,
    gaps: list[dict],
    existing_paths: set[str],
) -> list[tuple[str, str, dict]]:
    candidates_by_type: dict[str, list[tuple[dict, str, str]]] = {
        "source_entrypoint": [],
        "test_surface": [],
        "benchmark": [],
        "configuration": [],
    }
    for gap in sorted_gaps_for_acquisition(gaps):
        wanted_types = {
            GAP_LAYER_TO_IMPLEMENTATION_TYPE[layer]
            for layer in gap.get("missing_layers") or []
            if layer in GAP_LAYER_TO_IMPLEMENTATION_TYPE
        }
        if not wanted_types:
            continue
        for item in files:
            path = item.get("path") or ""
            if not path or path in existing_paths:
                continue
            size = item.get("size") or 0
            if size and size > MAX_IMPLEMENTATION_FILE_SIZE:
                continue
            evidence_type = classify_implementation_path(path)
            if evidence_type not in wanted_types:
                continue
            candidates_by_type[evidence_type].append((gap, path, evidence_type))

    selected: list[tuple[str, str, dict]] = []
    selected_paths: set[str] = set()
    counts_by_type: dict[str, int] = {}
    for gap in sorted_gaps_for_acquisition(gaps):
        for layer in gap.get("missing_layers") or []:
            evidence_type = GAP_LAYER_TO_IMPLEMENTATION_TYPE.get(layer)
            if not evidence_type:
                continue
            if counts_by_type.get(evidence_type, 0) >= TARGETED_IMPLEMENTATION_LIMITS[evidence_type]:
                continue
            candidates = [
                (targeted_path_score(path, item_type, repo, gap), path, item_gap)
                for item_gap, path, item_type in candidates_by_type.get(evidence_type, [])
                if item_gap is gap and path not in selected_paths
            ]
            ranked = sorted(candidates, key=lambda item: item[0])
            layer_limit = TARGETED_PER_GAP_LAYER_LIMITS.get(evidence_type, 1)
            for _, path, item_gap in ranked[:layer_limit]:
                if counts_by_type.get(evidence_type, 0) >= TARGETED_IMPLEMENTATION_LIMITS[evidence_type]:
                    break
                selected.append((path, evidence_type, item_gap))
                selected_paths.add(path)
                counts_by_type[evidence_type] = counts_by_type.get(evidence_type, 0) + 1
    return selected


def artifact_keyword_score(title: str, body: str, gap: dict) -> int:
    text = f"{title} {body}"
    return keyword_hit_count(text, claim_gap_keywords(gap)) * 10 + min(len(body or ""), 2000) // 200


def gap_query_terms(gap: dict, layer: str, limit: int = 3) -> list[str]:
    terms = claim_gap_keywords(gap)
    layer_terms = [term for term in terms if term in LAYER_KEYWORDS.get(layer, [])]
    ordered = unique_terms(layer_terms + terms)
    return ordered[:limit] or LAYER_KEYWORDS.get(layer, ["api"])[:limit]


def append_unique_evidence(additions: list[Evidence], item: Evidence, seen_keys: set[str]) -> bool:
    key = evidence_key(item)
    if key in seen_keys:
        return False
    seen_keys.add(key)
    additions.append(item)
    return True


def binding_confidence_label(score: int | float) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def auto_confidence_label(score: int | float) -> str:
    if score >= AUTO_CONFIDENCE_SCORING["high_threshold"]:
        return "high"
    if score >= AUTO_CONFIDENCE_SCORING["medium_threshold"]:
        return "medium"
    return "low"


def confidence_label_for_calibration(score: int | float, calibration: str | None = None) -> str:
    if calibration == AUTO_CONFIDENCE_CALIBRATION:
        return auto_confidence_label(score)
    return binding_confidence_label(score)


def normalized_binding_signal(signal: str) -> str:
    if signal.startswith("keyword_hits:"):
        return "keyword_hits"
    if signal.startswith("typed_evidence:"):
        return "typed_evidence"
    return signal


def confidence_signal_group(signal: str) -> str:
    if signal.startswith(("repo_activity:", "repo_history:", "release_cadence:")):
        return "time_series"
    if signal.startswith("cross_version_"):
        return "drift"
    if signal.startswith(("cross_project_repeated:", "repeated_binding:")):
        return "pattern"
    if signal in {
        "stable_artifact_url",
        "keyword_sparse",
        "generic_evidence",
        "requested_missing_layer",
        "target_layer",
        "evidence_layer_match",
    } or signal.startswith(
        (
            "source_or_validation_evidence:",
            "engineering_trace_evidence:",
            "boundary_polarity:",
            "keyword_hits:",
            "typed_evidence:",
        )
    ):
        return "evidence"
    if signal in {AUTO_CONFIDENCE_CALIBRATION, "heuristic_v1"}:
        return "calibration"
    return "other"


def confidence_signal_label(signal: str) -> str:
    labels = {
        AUTO_CONFIDENCE_CALIBRATION: AUTO_CONFIDENCE_CALIBRATION,
        "heuristic_v1": "heuristic_v1",
        "stable_artifact_url": "stable artifact URL",
        "keyword_sparse": "keyword sparse",
        "generic_evidence": "generic evidence",
        "requested_missing_layer": "requested missing layer",
        "target_layer": "target layer",
        "evidence_layer_match": "evidence layer match",
    }
    if signal in labels:
        return labels[signal]
    if ":" not in signal:
        return signal.replace("_", " ")
    name, value = signal.split(":", 1)
    name_labels = {
        "cross_project_repeated": "cross-project repeated",
        "repeated_binding": "repeated binding",
        "cross_version_binding_stable": "cross-version stable",
        "cross_version_evidence_drift": "evidence drift",
        "repo_history": "repository history",
        "repo_activity": "repository activity",
        "release_cadence": "release cadence",
        "source_or_validation_evidence": "source/validation evidence",
        "engineering_trace_evidence": "engineering trace",
        "boundary_polarity": "boundary polarity",
        "keyword_hits": "keyword hits",
        "typed_evidence": "typed evidence",
    }
    return f"{name_labels.get(name, name.replace('_', ' '))} {value}"


def confidence_signal_breakdown(signals: list | tuple | None) -> list[dict]:
    buckets = {
        group: {"group": group, "label": label, "signals": []}
        for group, label in CONFIDENCE_SIGNAL_GROUPS
    }
    if isinstance(signals, str):
        signals = [signals]
    elif not isinstance(signals, (list, tuple, set)):
        signals = []
    seen = set()
    for raw_signal in signals or []:
        signal = str(raw_signal)
        if not signal or signal in seen:
            continue
        seen.add(signal)
        group = confidence_signal_group(signal)
        buckets[group]["signals"].append(
            {
                "raw": signal,
                "label": confidence_signal_label(signal),
            }
        )
    return [buckets[group] for group, _label in CONFIDENCE_SIGNAL_GROUPS if buckets[group]["signals"]]


def confidence_signal_group_names(confidence: dict | None) -> list[str]:
    if not confidence:
        return []
    breakdown = confidence.get("signal_breakdown") or confidence_signal_breakdown(confidence.get("signals") or [])
    names = []
    for group in breakdown:
        name = str(group.get("group") or "")
        if name and name not in names:
            names.append(name)
    return names


def confidence_signal_group_score(confidence: dict | None) -> int:
    return sum(PATTERN_SIGNAL_GROUP_WEIGHTS.get(group, 0) for group in confidence_signal_group_names(confidence))


def confidence_signal_labels(confidence: dict | None) -> list[str]:
    if not confidence:
        return []
    breakdown = confidence.get("signal_breakdown") or confidence_signal_breakdown(confidence.get("signals") or [])
    labels = []
    for group in breakdown:
        for signal in group.get("signals") or []:
            label = str(signal.get("label") or signal.get("raw") or "")
            if label and label not in labels:
                labels.append(label)
    return labels


def binding_confidence_weight_snapshot() -> dict:
    return {
        "base": BINDING_CONFIDENCE_BASE,
        "signals": dict(BINDING_CONFIDENCE_SIGNAL_WEIGHTS),
        "keyword_hits": {
            "per_hit": BINDING_CONFIDENCE_KEYWORD_HIT_WEIGHT,
            "max": BINDING_CONFIDENCE_KEYWORD_HIT_MAX,
        },
    }


def auto_confidence_scoring_snapshot() -> dict:
    return {
        "scoring": dict(AUTO_CONFIDENCE_SCORING),
        "archive_signal_weights": dict(AUTO_CONFIDENCE_ARCHIVE_WEIGHTS),
        "repeat_signal_thresholds": dict(AUTO_CONFIDENCE_REPEAT_THRESHOLDS),
        "label_thresholds": {
            "high": AUTO_CONFIDENCE_SCORING["high_threshold"],
            "medium": AUTO_CONFIDENCE_SCORING["medium_threshold"],
        },
    }


def binding_confidence_for(item: Evidence, gap: dict, layer: str, keywords: list[str]) -> dict:
    score = BINDING_CONFIDENCE_BASE
    signals = ["heuristic_v1"]
    missing_layers = gap.get("missing_layers") or []
    target_layers = gap.get("target_layers") or []

    if layer in missing_layers:
        score += BINDING_CONFIDENCE_SIGNAL_WEIGHTS["requested_missing_layer"]
        signals.append("requested_missing_layer")
    elif layer in target_layers:
        score += BINDING_CONFIDENCE_SIGNAL_WEIGHTS["target_layer"]
        signals.append("target_layer")

    actual_layer = evidence_support_layer(item)
    if actual_layer == layer:
        score += BINDING_CONFIDENCE_SIGNAL_WEIGHTS["evidence_layer_match"]
        signals.append("evidence_layer_match")

    hit_count = keyword_hit_count(f"{item.title} {item.quote}", keywords)
    if hit_count:
        score += min(hit_count * BINDING_CONFIDENCE_KEYWORD_HIT_WEIGHT, BINDING_CONFIDENCE_KEYWORD_HIT_MAX)
        signals.append(f"keyword_hits:{hit_count}")

    if item.url:
        score += BINDING_CONFIDENCE_SIGNAL_WEIGHTS["stable_artifact_url"]
        signals.append("stable_artifact_url")

    if item.evidence_type != "general":
        score += BINDING_CONFIDENCE_SIGNAL_WEIGHTS["typed_evidence"]
        signals.append(f"typed_evidence:{item.evidence_type}")

    score = int(clamp(score, 0, 100))
    return {
        "score": score,
        "label": binding_confidence_label(score),
        "calibration": "heuristic_v1",
        "signals": signals,
        "signal_breakdown": confidence_signal_breakdown(signals),
    }


def make_acquisition_binding(item: Evidence, gap: dict, layer: str, keywords: list[str]) -> dict:
    return {
        "evidence_id": item.evidence_id,
        "claim_id": gap.get("claim_id") or "",
        "field": gap.get("field") or "",
        "missing_layer": layer,
        "missing_layer_label": SUPPORT_LAYER_LABELS.get(layer, layer),
        "keywords": keywords[:8],
        "reason": gap.get("gap_reason") or "",
        "binding_confidence": binding_confidence_for(item, gap, layer, keywords),
    }


def acquire_targeted_evidence(repo: dict, evidence: list[Evidence], gaps: list[dict]) -> tuple[list[Evidence], list[dict]]:
    missing_layers = ordered_missing_layers(gaps)
    if not missing_layers:
        return [], []

    full_name = repo["full_name"]
    additions: list[Evidence] = []
    bindings: list[dict] = []
    seen_keys = {evidence_key(item) for item in evidence}
    existing_paths = {
        item.title
        for item in evidence
        if item.evidence_type in {"source_entrypoint", "test_surface", "benchmark", "configuration"}
    }

    def next_id() -> str:
        return f"E{len(evidence) + len(additions) + 1}"

    if set(missing_layers) & set(GAP_LAYER_TO_IMPLEMENTATION_TYPE):
        for path, evidence_type, gap in targeted_implementation_paths(
            fetch_tree_files(repo),
            repo,
            gaps,
            existing_paths,
        ):
            text, url = fetch_file_text(repo, path)
            if not text:
                continue
            item = make_evidence(
                next_id(),
                2,
                implementation_kind(evidence_type),
                path,
                url,
                excerpt(text, 700),
                evidence_type,
            )
            if append_unique_evidence(additions, item, seen_keys):
                layer = evidence_support_layer(item)
                bindings.append(make_acquisition_binding(item, gap, layer, claim_gap_keywords(gap)))
            existing_paths.add(path)

    if "release" in missing_layers:
        release_candidates = fetch_releases_sample(full_name, per_page=10)
        release_gaps = [gap for gap in sorted_gaps_for_acquisition(gaps) if "release" in (gap.get("missing_layers") or [])]
        for gap in release_gaps:
            ranked_releases = sorted(
                release_candidates,
                key=lambda release: -artifact_keyword_score(
                    release.get("name") or release.get("tag_name") or "Release",
                    release.get("body") or "",
                    gap,
                ),
            )
            for release in ranked_releases[:2]:
                title = release.get("name") or release.get("tag_name") or "Release"
                body = release.get("body") or ""
                quote = excerpt(body, 550) or f"Published at {release.get('published_at') or 'unknown time'}."
                item = make_evidence(
                    next_id(),
                    2,
                    "Release",
                    title,
                    release.get("html_url") or "",
                    quote,
                    "release_delta",
                )
                if append_unique_evidence(additions, item, seen_keys):
                    bindings.append(make_acquisition_binding(item, gap, "release", claim_gap_keywords(gap)))
                if sum(1 for added in additions if added.kind == "Release") >= 4:
                    break
            if sum(1 for added in additions if added.kind == "Release") >= 4:
                break

    if "collaboration" in missing_layers:
        collaboration_gaps = [
            gap for gap in sorted_gaps_for_acquisition(gaps) if "collaboration" in (gap.get("missing_layers") or [])
        ]
        for gap in collaboration_gaps:
            for term in gap_query_terms(gap, "collaboration", limit=3):
                issue_candidates = fetch_issue_search(full_name, f"is:issue {term}", per_page=3)
                ranked_issues = sorted(
                    issue_candidates,
                    key=lambda issue: -artifact_keyword_score(issue.get("title") or "", issue.get("body") or "", gap),
                )
                for issue in ranked_issues[:2]:
                    quote = excerpt(issue.get("body") or "", 500) or (
                        f"{issue.get('comments', 0)} comments; state={issue.get('state')}."
                    )
                    item = make_evidence(
                        next_id(),
                        2,
                        "Issue",
                        issue.get("title") or "Issue",
                        issue.get("html_url") or "",
                        quote,
                        "user_friction",
                    )
                    if append_unique_evidence(additions, item, seen_keys):
                        bindings.append(make_acquisition_binding(item, gap, "collaboration", claim_gap_keywords(gap)))
                pr_candidates = fetch_issue_search(
                    full_name,
                    f"is:pr is:merged -author:dependabot[bot] -label:dependencies {term}",
                    per_page=3,
                )
                ranked_prs = sorted(
                    pr_candidates,
                    key=lambda pr: -artifact_keyword_score(pr.get("title") or "", pr.get("body") or "", gap),
                )
                for pr in ranked_prs[:2]:
                    quote = excerpt(pr.get("body") or "", 500) or f"state={pr.get('state')}; merged_at={pr.get('merged_at')}."
                    item = make_evidence(
                        next_id(),
                        2,
                        "Pull Request",
                        pr.get("title") or "Pull request",
                        pr.get("html_url") or "",
                        quote,
                        "implementation_change",
                    )
                    if append_unique_evidence(additions, item, seen_keys):
                        bindings.append(make_acquisition_binding(item, gap, "collaboration", claim_gap_keywords(gap)))
                collaboration_count = sum(1 for added in additions if added.kind in {"Issue", "Pull Request"})
                if collaboration_count >= 6:
                    break
            if sum(1 for added in additions if added.kind in {"Issue", "Pull Request"}) >= 6:
                break

    return additions, bindings


def build_evidence_acquisition_summary(gaps: list[dict], targeted_evidence: list[Evidence], bindings: list[dict]) -> dict:
    requested_layers = ordered_missing_layers(gaps)
    added_counts: dict[str, int] = {}
    for item in targeted_evidence:
        layer = evidence_support_layer(item)
        added_counts[layer] = added_counts.get(layer, 0) + 1
    confidence_scores = [
        (binding.get("binding_confidence") or {}).get("score")
        for binding in bindings
        if isinstance((binding.get("binding_confidence") or {}).get("score"), (int, float))
    ]
    claim_fields = []
    for binding in bindings:
        field = binding.get("field")
        if field and field not in claim_fields:
            claim_fields.append(field)
    return {
        "strategy": "claim_gap_targeted",
        "requested_layers": requested_layers,
        "requested_layer_labels": [SUPPORT_LAYER_LABELS.get(layer, layer) for layer in requested_layers],
        "added_total": len(targeted_evidence),
        "added_counts": added_counts,
        "added_evidence_ids": [item.evidence_id for item in targeted_evidence],
        "binding_count": len(bindings),
        "bindings": bindings,
        "average_binding_confidence": round(sum(confidence_scores) / len(confidence_scores), 1) if confidence_scores else None,
        "minimum_binding_confidence": min(confidence_scores) if confidence_scores else None,
        "target_claim_fields": claim_fields,
        "status": "expanded" if targeted_evidence else "no_additional_evidence",
    }


def bind_acquired_evidence_to_claims(
    claims: list[Claim],
    evidence: list[Evidence],
    bindings: list[dict],
    max_refs_per_claim: int = 8,
) -> None:
    if not bindings:
        return
    evidence_map = {item.evidence_id: item for item in evidence}
    claims_by_id = {claim.claim_id: claim for claim in claims if claim.claim_id}
    claims_by_field = {claim.field: claim for claim in claims}
    for binding in bindings:
        evidence_id = binding.get("evidence_id")
        if evidence_id not in evidence_map:
            continue
        claim = claims_by_id.get(binding.get("claim_id") or "") or claims_by_field.get(binding.get("field") or "")
        if not claim or evidence_id in claim.evidence_ids:
            continue
        if len(claim.evidence_ids) >= max_refs_per_claim:
            continue
        claim.evidence_ids.append(evidence_id)
    for claim in claims:
        claim.support_coverage = claim_support_coverage(claim, evidence_map)


def assign_evidence_ids(repo: dict, evidence: list[Evidence]) -> None:
    for item in evidence:
        item.stable_id = stable_id("ev", repo["full_name"], item.kind, item.url or item.title)


def corpus(evidence: list[Evidence], repo: dict) -> str:
    parts = [repo.get("description") or "", " ".join(repo.get("topics") or [])]
    parts.extend(" ".join([item.title, item.quote, item.evidence_type, item.polarity, " ".join(item.signal_tags)]) for item in evidence)
    return "\n".join(parts)


def matching_evidence(
    evidence: list[Evidence],
    words: list[str],
    fallback: int = 1,
    preferred_tags: list[str] | None = None,
    polarities: set[str] | None = None,
) -> list[str]:
    preferred_tags = preferred_tags or []
    polarities = polarities or {"supporting", "boundary"}
    matches = [
        item
        for item in evidence
        if item.polarity in polarities and has_any(item.quote + " " + item.title + " " + " ".join(item.signal_tags), words)
    ]
    matches.sort(
        key=lambda item: (
            0 if set(item.signal_tags) & set(preferred_tags) else 1,
            0 if item.polarity == "supporting" else 1,
            item.level,
            item.evidence_id,
        )
    )
    if matches:
        return [item.evidence_id for item in matches[:4]]
    return [item.evidence_id for item in evidence[:fallback]]


def counter_evidence(
    evidence: list[Evidence],
    words: list[str] | None = None,
    limit: int = 3,
) -> list[str]:
    words = words or []
    candidates = [
        item
        for item in evidence
        if item.polarity in {"negative", "boundary"}
        and (not words or has_any(item.quote + " " + item.title + " " + " ".join(item.signal_tags), words))
    ]
    candidates.sort(key=lambda item: (0 if item.polarity == "boundary" else 1, item.level, item.evidence_id))
    return [item.evidence_id for item in candidates[:limit]]


SUPPORT_LAYER_ORDER = ["narrative", "release", "collaboration", "configuration", "source", "tests", "benchmarks"]
SUPPORT_LAYER_LABELS = {
    "narrative": "叙事",
    "release": "发布",
    "collaboration": "协作",
    "configuration": "配置",
    "source": "源码",
    "tests": "测试",
    "benchmarks": "Benchmark",
}
SUPPORT_LEVEL_LABELS = {
    "source_and_validation": "源码 + 测试/benchmark 支撑",
    "source_backed": "源码支撑",
    "validation_backed": "测试/benchmark 支撑",
    "configuration_backed": "配置支撑",
    "engineering_trace": "协作/发布痕迹支撑",
    "narrative_only": "叙事支撑",
    "no_direct_evidence": "缺少直接证据",
}


def evidence_support_layer(item: Evidence) -> str:
    if item.evidence_type == "source_entrypoint":
        return "source"
    if item.evidence_type == "test_surface":
        return "tests"
    if item.evidence_type == "benchmark":
        return "benchmarks"
    if item.evidence_type == "configuration":
        return "configuration"
    if item.kind == "Release" or item.evidence_type == "release_delta":
        return "release"
    if item.kind in {"Issue", "Pull Request"} or item.evidence_type in {"user_friction", "implementation_change"}:
        return "collaboration"
    return "narrative"


def support_level_for_layers(layers: set[str], evidence_count: int) -> str:
    if evidence_count == 0:
        return "no_direct_evidence"
    has_validation = bool(layers & {"tests", "benchmarks"})
    if "source" in layers and has_validation:
        return "source_and_validation"
    if "source" in layers:
        return "source_backed"
    if has_validation:
        return "validation_backed"
    if "configuration" in layers:
        return "configuration_backed"
    if layers & {"release", "collaboration"}:
        return "engineering_trace"
    return "narrative_only"


def support_score_for_layers(layers: set[str], evidence_count: int) -> int:
    if evidence_count == 0:
        return 0
    score = 0
    if "narrative" in layers:
        score = max(score, 20)
    if "release" in layers:
        score = max(score, 35)
    if "collaboration" in layers:
        score = max(score, 40)
    if "configuration" in layers:
        score = max(score, 45)
    if "source" in layers:
        score = max(score, 65)
    if "tests" in layers:
        score = max(score, 55 if "source" not in layers else 80)
    if "benchmarks" in layers:
        score = max(score, 60 if "source" not in layers else 85)
    if "source" in layers and {"tests", "benchmarks"} <= layers:
        score = max(score, 90)
    return min(100, score + min(max(evidence_count - 1, 0), 5) * 2)


def claim_support_coverage(claim: Claim, evidence_map: dict[str, Evidence]) -> dict[str, object]:
    layer_evidence_ids: dict[str, list[str]] = {layer: [] for layer in SUPPORT_LAYER_ORDER}
    for evidence_id in claim.evidence_ids:
        item = evidence_map.get(evidence_id)
        if not item:
            continue
        layer_evidence_ids[evidence_support_layer(item)].append(evidence_id)

    layer_evidence_ids = {layer: ids for layer, ids in layer_evidence_ids.items() if ids}
    layers = [layer for layer in SUPPORT_LAYER_ORDER if layer in layer_evidence_ids]
    layer_set = set(layers)
    evidence_count = sum(len(ids) for ids in layer_evidence_ids.values())
    level = support_level_for_layers(layer_set, evidence_count)
    label = SUPPORT_LEVEL_LABELS[level]
    layer_labels = [SUPPORT_LAYER_LABELS.get(layer, layer) for layer in layers]
    return {
        "level": level,
        "label": label,
        "score": support_score_for_layers(layer_set, evidence_count),
        "layers": layers,
        "layer_labels": layer_labels,
        "layer_counts": {layer: len(ids) for layer, ids in layer_evidence_ids.items()},
        "layer_evidence_ids": layer_evidence_ids,
        "summary": f"{label}；覆盖层：{', '.join(layer_labels) if layer_labels else '无'}",
    }


def support_coverage_text(coverage: dict | None) -> str:
    if not coverage:
        return "未计算"
    label = coverage.get("label") or SUPPORT_LEVEL_LABELS["no_direct_evidence"]
    layers = coverage.get("layer_labels") or []
    score = coverage.get("score")
    layer_text = "、".join(str(item) for item in layers) if layers else "无"
    if isinstance(score, (int, float)):
        return f"{label}（{layer_text}，{score}/100）"
    return f"{label}（{layer_text}）"


CLAIM_GAP_FIELD_WEIGHTS = {
    "关键抽象": 100,
    "复杂度藏处": 95,
    "作者如何重新定义问题": 90,
    "架构边界": 85,
    "治理模式": 75,
    "可复用思想": 70,
    "不可复制条件": 60,
    "实现层复核线索": 50,
    "领域": 35,
}
CLAIM_GAP_LEVEL_WEIGHTS = {
    "no_direct_evidence": 100,
    "narrative_only": 90,
    "engineering_trace": 70,
    "configuration_backed": 60,
    "validation_backed": 45,
    "source_backed": 35,
    "source_and_validation": 0,
}
CLAIM_GAP_TARGET_LAYERS = {
    "作者如何重新定义问题": ["source", "tests", "release"],
    "关键抽象": ["source", "tests", "benchmarks"],
    "架构边界": ["source", "tests", "configuration"],
    "复杂度藏处": ["source", "tests", "benchmarks"],
    "治理模式": ["configuration", "collaboration"],
    "可复用思想": ["source", "tests", "collaboration"],
    "不可复制条件": ["collaboration", "release"],
    "实现层复核线索": ["source", "tests", "benchmarks", "configuration"],
    "领域": ["source"],
}
CLAIM_GAP_RECOMMENDATIONS = {
    "source": "补核心源码入口、公共 API 或架构模块证据",
    "tests": "补单元/集成/端到端测试证据，确认抽象是否被验证",
    "benchmarks": "补 benchmark 或性能测试证据，确认复杂度与性能判断",
    "configuration": "补配置、CI、package metadata 或部署文件证据",
    "collaboration": "补 issue/PR 讨论证据，确认用户摩擦和维护者取舍",
    "release": "补 release/changelog 证据，确认判断是否进入真实演进轨迹",
    "narrative": "补 README/docs 之外的工程证据，避免只引用项目自述",
}
CLAIM_GAP_REASONS = {
    "no_direct_evidence": "该判断缺少直接 evidence 引用，当前不可复核。",
    "narrative_only": "该判断主要由叙事材料支撑，容易把项目自述误当作实现事实。",
    "engineering_trace": "该判断已有协作或发布痕迹，但还缺少可读源码/测试层复核。",
    "configuration_backed": "该判断已有配置面证据，但还缺少源码或测试证明实际行为。",
    "validation_backed": "该判断已有测试或 benchmark 证据，但还缺少对应源码入口来解释机制。",
    "source_backed": "该判断已有源码证据，但还缺少测试或 benchmark 来确认行为边界。",
    "source_and_validation": "该判断已覆盖源码和验证层，暂不属于高优先级 gap。",
}
COGNITION_FIELD_PROFILES = {
    "作者如何重新定义问题": {
        "category": "problem_framing",
        "label": "问题重定义",
        "move": "先重写问题边界，再选择工程形态",
        "transfer_rule": "先确认项目把什么问题改写成了更小、更可执行的工程对象，再评估技术方案。",
    },
    "关键抽象": {
        "category": "abstraction_design",
        "label": "关键抽象设计",
        "move": "把复杂能力压进少数可组合抽象",
        "transfer_rule": "优先寻找公共 API、核心类型和测试中反复出现的抽象，而不是只看功能列表。",
    },
    "架构边界": {
        "category": "boundary_design",
        "label": "架构边界设计",
        "move": "用边界、配置和验证把可承诺范围固定下来",
        "transfer_rule": "观察项目明确支持什么、不支持什么，以及这些边界是否被源码和测试固定。",
    },
    "复杂度藏处": {
        "category": "complexity_management",
        "label": "复杂度管理",
        "move": "把难点集中在可测试、可替换、可观测的位置",
        "transfer_rule": "优先检查错误处理、性能、状态、并发和兼容性证据，判断复杂度是否被有意收拢。",
    },
    "治理模式": {
        "category": "governance_design",
        "label": "治理设计",
        "move": "用配置、流程和协作痕迹维持长期演化",
        "transfer_rule": "看贡献规范、CI、issue/PR 和 release 是否形成稳定维护机制。",
    },
    "可复用思想": {
        "category": "transferable_principle",
        "label": "可迁移思想",
        "move": "把可迁移部分沉淀为示例、源码、测试和协作模式",
        "transfer_rule": "只迁移被源码、测试或真实协作反复支撑的思想，避免迁移项目势能本身。",
    },
    "不可复制条件": {
        "category": "context_constraint",
        "label": "不可复制条件",
        "move": "把项目势能与上下文依赖拆开看",
        "transfer_rule": "把社区、生态、发布节奏和维护者结构当作条件变量，而不是默认可复制资产。",
    },
    "实现层复核线索": {
        "category": "implementation_grounding",
        "label": "实现层复核",
        "move": "把高层判断回落到源码、测试、benchmark 和配置",
        "transfer_rule": "高层设计判断必须能被实现层 artifact 复核，否则只能作为研究提示。",
    },
    "领域": {
        "category": "domain_positioning",
        "label": "领域定位",
        "move": "通过工程 artifact 重新确认项目实际所在的问题域",
        "transfer_rule": "不要只按 README 定位项目，需用 API、源码和使用面确认真实领域边界。",
    },
}
DEFAULT_COGNITION_FIELD_PROFILE = {
    "category": "general_engineering_move",
    "label": "通用工程动作",
    "move": "把项目主张转成可复核工程证据",
    "transfer_rule": "只保留能被 archive evidence 重复支撑的工程动作。",
}
COGNITION_LAYER_ACTIONS = {
    "source": "用源码或公共 API 复核机制",
    "tests": "用测试验证行为边界",
    "benchmarks": "用 benchmark 约束性能和复杂度判断",
    "configuration": "用配置、CI 或 package metadata 固化流程",
    "collaboration": "用 issue/PR 协作痕迹观察真实摩擦",
    "release": "用 release/changelog 验证演化轨迹",
    "narrative": "用叙事材料提出初始假设",
}


def claim_value(claim: Claim | dict, key: str, default=None):
    if isinstance(claim, dict):
        return claim.get(key, default)
    return getattr(claim, key, default)


def normalize_support_coverage(coverage: dict | None) -> dict:
    coverage = coverage or {}
    level = coverage.get("level") or "no_direct_evidence"
    score = coverage.get("score", 0)
    if not isinstance(score, (int, float)):
        score = 0
    layers = coverage.get("layers") or []
    layer_labels = coverage.get("layer_labels") or [
        SUPPORT_LAYER_LABELS.get(layer, layer) for layer in layers
    ]
    return {
        **coverage,
        "level": level,
        "label": coverage.get("label") or SUPPORT_LEVEL_LABELS.get(level, level),
        "score": int(score),
        "layers": layers,
        "layer_labels": layer_labels,
    }


def target_layers_for_claim(field: str) -> list[str]:
    return CLAIM_GAP_TARGET_LAYERS.get(field, ["source", "tests"])


def claim_gap_recommendation(missing_layers: list[str]) -> str:
    if not missing_layers:
        return "当前 direct evidence 已覆盖核心实现与验证层；后续可继续自动采样新增 release、issue、PR 和实现层变更。"
    return "；".join(CLAIM_GAP_RECOMMENDATIONS.get(layer, layer) for layer in missing_layers[:3])


def build_claim_gap_report(claims: list[Claim] | list[dict], limit: int = 8) -> list[dict]:
    gaps = []
    for claim in claims:
        field = str(claim_value(claim, "field", ""))
        coverage = normalize_support_coverage(claim_value(claim, "support_coverage", {}))
        level = coverage["level"]
        if level == "source_and_validation" and coverage["score"] >= 80:
            continue

        current_layers = set(coverage["layers"])
        target_layers = target_layers_for_claim(field)
        missing_layers = [layer for layer in target_layers if layer not in current_layers]
        if not missing_layers and level != "source_and_validation":
            missing_layers = [layer for layer in ("source", "tests") if layer not in current_layers]

        confidence = str(claim_value(claim, "confidence", "low") or "low")
        confidence_bonus = {"high": 10, "medium": 5}.get(confidence, 0)
        field_weight = CLAIM_GAP_FIELD_WEIGHTS.get(field, 55)
        weakness = CLAIM_GAP_LEVEL_WEIGHTS.get(level, 50)
        priority_score = min(100, round(field_weight * 0.55 + weakness * 0.35 + confidence_bonus))
        gaps.append(
            {
                "claim_id": claim_value(claim, "claim_id", ""),
                "field": field,
                "confidence": confidence,
                "support_level": level,
                "support_label": coverage["label"],
                "support_score": coverage["score"],
                "current_layers": coverage["layers"],
                "current_layer_labels": coverage["layer_labels"],
                "target_layers": target_layers,
                "target_layer_labels": [SUPPORT_LAYER_LABELS.get(layer, layer) for layer in target_layers],
                "missing_layers": missing_layers,
                "missing_layer_labels": [SUPPORT_LAYER_LABELS.get(layer, layer) for layer in missing_layers],
                "priority_score": priority_score,
                "gap_reason": CLAIM_GAP_REASONS.get(level, "该判断需要补充更强的工程证据。"),
                "recommendation": claim_gap_recommendation(missing_layers),
                "evidence_ids": claim_value(claim, "evidence_ids", []) or [],
            }
        )
    gaps.sort(key=lambda item: (-item["priority_score"], item["support_score"], item["field"]))
    return gaps[:limit]


def make_claim(
    field: str,
    text: str,
    evidence_ids: list[str],
    confidence: str,
    template: str,
    rationale: str,
    counter_ids: list[str] | None = None,
) -> Claim:
    return Claim(
        field,
        text,
        evidence_ids,
        confidence,
        template=template,
        rationale=rationale,
        counter_evidence_ids=counter_ids or [],
    )


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
        ids = matching_evidence(
            evidence,
            ["durable", "checkpoint", "interrupt", "resume", "recover"],
            preferred_tags=["recoverability", "complexity"],
        )
    elif has_any(text, ["local-first", "self-host", "offline", "zero api key"]):
        claim = "项目把问题定义为用户控制权和长期可拥有性，而不只是功能可用性。"
        ids = matching_evidence(
            evidence,
            ["local-first", "self-host", "offline", "zero api key"],
            preferred_tags=["local_control"],
        )
    elif has_any(text, ["fast", "performance", "latency", "native", "zero dependencies"]):
        claim = "项目把竞争焦点放在速度、低依赖和可控部署上，用基础体验建立信任。"
        ids = matching_evidence(
            evidence,
            ["fast", "performance", "latency", "native", "zero dependencies"],
            preferred_tags=["performance"],
        )
    elif has_any(text, ["agent", "workflow", "automation"]):
        claim = "项目把软件使用方式改写为可编排、可委托、可观察的工作流。"
        ids = matching_evidence(evidence, ["agent", "workflow", "automation"], preferred_tags=["abstraction"])
    else:
        claim = "项目从一个具体痛点切入，正在验证新的默认工作方式。"
        ids = matching_evidence(evidence, [repo.get("name", "")])
    return make_claim(
        "作者如何重新定义问题",
        claim,
        ids,
        "medium" if ids else "low",
        "定位叙事 -> 问题重定义 -> 可迁移判断",
        "优先使用 README/release/PR 中的定位与变更证据，避免只凭 star 或描述推断。",
        counter_evidence(evidence, ["not", "experimental", "deprecated", "bug", "error", "confusing"]),
    )


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
        ids = matching_evidence(
            evidence,
            [word for words in keywords.values() for word in words],
            preferred_tags=["abstraction"],
        )
    else:
        claim = "关键抽象尚需通过 examples 和核心 API 文件确认。"
        ids = matching_evidence(evidence, ["api", "example", "quickstart"], preferred_tags=["abstraction"])
    return make_claim(
        "关键抽象",
        claim,
        ids,
        "medium" if abstractions else "low",
        "词汇/接口反复出现 -> 抽象候选 -> 需要实现层复核",
        "只把公开文档和变更记录中反复出现的名词视为抽象候选，不把营销词直接当架构事实。",
        counter_evidence(evidence, ["deprecated", "no longer", "confusing", "boilerplate", "complex"]),
    )


def claim_boundaries(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["not a generic", "intentionally narrow", "focused", "low-level", "you don't need"]):
        claim = "项目主动声明边界，倾向用清晰分层换取可理解性和长期演进能力。"
        ids = matching_evidence(
            evidence,
            ["not a generic", "intentionally narrow", "focused", "low-level", "you don't need"],
            preferred_tags=["boundary"],
            polarities={"supporting", "boundary"},
        )
    elif has_any(text, ["experimental", "not ready for production", "preview"]):
        claim = "项目把实验状态显式写出，用透明边界降低误用风险。"
        ids = matching_evidence(
            evidence,
            ["experimental", "not ready for production", "preview"],
            preferred_tags=["boundary"],
            polarities={"boundary"},
        )
    else:
        claim = "项目边界目前主要从 README 和 issue 侧面推断，后续需要抓取架构文档和 PR 讨论补强。"
        ids = matching_evidence(evidence, ["readme", "docs", "issue"], preferred_tags=["boundary"])
    return make_claim(
        "架构边界",
        claim,
        ids,
        "medium" if ids else "low",
        "显式非目标/限制 -> 边界判断 -> 误用风险",
        "边界类 claim 优先引用 polarity=boundary 的证据；没有显式边界时降低置信度。",
        counter_evidence(evidence, ["experimental", "unsupported", "not ready", "deprecated", "no longer"]),
    )


def claim_complexity(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["bug", "error", "issue", "checkpoint", "interrupt", "self-hosted", "compatibility"]):
        claim = "复杂度主要暴露在失败语义、兼容性、部署环境和状态一致性上，不能只看 README 的顺滑叙事。"
        ids = matching_evidence(
            evidence,
            ["bug", "error", "checkpoint", "interrupt", "self-hosted", "compatibility"],
            preferred_tags=["complexity", "recoverability"],
            polarities={"supporting", "negative", "boundary"},
        )
    elif has_any(text, ["performance", "latency", "memory", "concurrency"]):
        claim = "复杂度集中在性能、资源使用和并发边界，适合继续精读 benchmark 与实现模块。"
        ids = matching_evidence(
            evidence,
            ["performance", "latency", "memory", "concurrency"],
            preferred_tags=["performance", "complexity"],
            polarities={"supporting", "negative", "boundary"},
        )
    else:
        claim = "复杂度藏处尚不明确，需要进一步抓取高评论 issue、最近 PR 和核心目录。"
        ids = matching_evidence(evidence, ["issue", "pull request"], preferred_tags=["complexity"])
    return make_claim(
        "复杂度藏处",
        claim,
        ids,
        "medium" if ids else "low",
        "缺陷/PR/发布变更 -> 复杂度暴露点 -> 后续精读方向",
        "复杂度 claim 必须把 issue、bug、兼容性或实现变更作为一等证据，而不是只引用 README。",
        counter_evidence(evidence, ["bug", "error", "confusing", "compatibility", "deprecated"]),
    )


def claim_governance(evidence: list[Evidence], text: str) -> Claim:
    if has_any(text, ["contributing", "code of conduct", "security", "issue template", "forum", "discussion"]):
        claim = "治理上倾向把贡献、支持、缺陷和安全问题分流，降低维护者认知负担。"
        ids = matching_evidence(
            evidence,
            ["contributing", "code of conduct", "security", "issue template", "forum", "discussion"],
            preferred_tags=["governance", "security"],
        )
    else:
        claim = "治理证据不足；需要检查 CONTRIBUTING、issue 模板、讨论区和响应时间。"
        ids = matching_evidence(evidence, ["contributing", "issue"], preferred_tags=["governance"])
    return make_claim(
        "治理模式",
        claim,
        ids,
        "medium" if ids else "low",
        "贡献入口/模板/安全流程 -> 治理结构 -> 维护者认知负担",
        "治理 claim 优先引用 CONTRIBUTING、模板、安全文件和 issue 分流证据。",
        counter_evidence(evidence, ["bug", "confusing", "discussion", "support"]),
    )


def claim_implementation_layer(evidence: list[Evidence]) -> Claim:
    implementation_types = {"source_entrypoint", "test_surface", "benchmark", "configuration"}
    selected = [item for item in evidence if item.evidence_type in implementation_types]
    selected.sort(
        key=lambda item: (
            {
                "source_entrypoint": 0,
                "test_surface": 1,
                "benchmark": 2,
                "configuration": 3,
            }.get(item.evidence_type, 9),
            item.evidence_id,
        )
    )
    ids = [item.evidence_id for item in selected[:5]]
    types = {item.evidence_type for item in selected}
    if {"source_entrypoint", "test_surface"} <= types:
        claim = "项目的认知模式可以继续从源码入口和测试面复核，避免只停留在 README、issue 和 release 叙事。"
        confidence = "medium"
    elif "source_entrypoint" in types:
        claim = "项目已经抓到源码入口证据，但测试/benchmark 证据不足，后续复核仍偏实现阅读。"
        confidence = "medium"
    elif selected:
        claim = "项目已有部分实现层证据，但不足以稳定支撑架构判断，需要扩展源码和测试采样。"
        confidence = "low"
    else:
        claim = "本次未抓到实现层证据；当前 dossier 仍主要依赖文档、issue、PR 和 release。"
        confidence = "low"
    return make_claim(
        "实现层复核线索",
        claim,
        ids,
        confidence,
        "源码/测试/benchmark/config -> claim 可复核性",
        "实现层证据用于校验前面的抽象、复杂度和治理判断，降低纯文本叙事带来的偏差。",
        counter_evidence(evidence, ["deprecated", "no longer", "experimental", "bug", "failed"]),
    )


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
        data["counter_evidence_stable_ids"] = [
            evidence_map[evidence_id].stable_id
            for evidence_id in claim.counter_evidence_ids
            if evidence_id in evidence_map
        ]
    else:
        data["evidence_stable_ids"] = []
        data["counter_evidence_stable_ids"] = []
    return data


def build_deep_payload(
    repo: dict,
    evidence: list[Evidence],
    claims: list[Claim],
    run_at: dt.datetime,
    evidence_acquisition: dict | None = None,
) -> dict:
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
        "claim_gap_report": build_claim_gap_report(claims),
        "evidence_acquisition": evidence_acquisition or {},
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
            evidence_type TEXT,
            polarity TEXT,
            signal_tags_json TEXT,
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
            counter_evidence_ids_json TEXT,
            counter_evidence_stable_ids_json TEXT,
            template TEXT,
            rationale TEXT,
            support_coverage_json TEXT,
            confidence TEXT NOT NULL,
            PRIMARY KEY (run_id, repo_full_name, field),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS evidence_acquisition_bindings (
            run_id INTEGER NOT NULL,
            repo_full_name TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            evidence_stable_id TEXT,
            claim_id TEXT NOT NULL DEFAULT '',
            field TEXT NOT NULL,
            missing_layer TEXT NOT NULL,
            missing_layer_label TEXT,
            keywords_json TEXT NOT NULL,
            reason TEXT,
            binding_confidence_score REAL,
            binding_confidence_label TEXT,
            binding_calibration TEXT,
            binding_confidence_signals_json TEXT,
            auto_confidence_score REAL,
            auto_confidence_label TEXT,
            auto_calibration TEXT,
            auto_confidence_signals_json TEXT,
            auto_calibrated_at TEXT,
            PRIMARY KEY (run_id, repo_full_name, evidence_id, field, missing_layer),
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
    ensure_column(conn, "evidence_items", "evidence_type", "TEXT")
    ensure_column(conn, "evidence_items", "polarity", "TEXT")
    ensure_column(conn, "evidence_items", "signal_tags_json", "TEXT")
    ensure_column(conn, "claims", "claim_id", "TEXT")
    ensure_column(conn, "claims", "evidence_stable_ids_json", "TEXT")
    ensure_column(conn, "claims", "counter_evidence_ids_json", "TEXT")
    ensure_column(conn, "claims", "counter_evidence_stable_ids_json", "TEXT")
    ensure_column(conn, "claims", "template", "TEXT")
    ensure_column(conn, "claims", "rationale", "TEXT")
    ensure_column(conn, "claims", "support_coverage_json", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "binding_confidence_score", "REAL")
    ensure_column(conn, "evidence_acquisition_bindings", "binding_confidence_label", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "binding_calibration", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "binding_confidence_signals_json", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "auto_confidence_score", "REAL")
    ensure_column(conn, "evidence_acquisition_bindings", "auto_confidence_label", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "auto_calibration", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "auto_confidence_signals_json", "TEXT")
    ensure_column(conn, "evidence_acquisition_bindings", "auto_calibrated_at", "TEXT")
    ensure_column(conn, "repository_snapshots", "project_track", "TEXT")
    ensure_column(conn, "repository_snapshots", "track_score", "REAL")
    ensure_column(conn, "repository_snapshots", "track_score_json", "TEXT")


def ensure_archive_search_schema(conn: sqlite3.Connection) -> tuple[bool, str | None]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS archive_search_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            rebuilt_at TEXT NOT NULL,
            source_run_count INTEGER NOT NULL,
            source_snapshot_count INTEGER NOT NULL,
            source_claim_count INTEGER NOT NULL,
            source_evidence_count INTEGER NOT NULL,
            source_binding_count INTEGER NOT NULL DEFAULT 0,
            indexed_documents INTEGER NOT NULL,
            index_version INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    ensure_column(conn, "archive_search_meta", "index_version", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "archive_search_meta", "source_binding_count", "INTEGER NOT NULL DEFAULT 0")
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS archive_search_fts USING fts5(
                repo_full_name UNINDEXED,
                run_id UNINDEXED,
                source_type UNINDEXED,
                source_id UNINDEXED,
                title,
                body,
                track,
                track_score UNINDEXED,
                tokenize='unicode61'
            )
            """
        )
    except sqlite3.OperationalError as exc:
        return False, str(exc)
    return True, None


def archive_source_counts(conn: sqlite3.Connection) -> dict:
    return {
        "source_run_count": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
        "source_snapshot_count": conn.execute("SELECT COUNT(*) FROM repository_snapshots").fetchone()[0],
        "source_claim_count": conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        "source_evidence_count": conn.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0],
        "source_binding_count": conn.execute("SELECT COUNT(*) FROM evidence_acquisition_bindings").fetchone()[0],
    }


def archive_search_index_current(conn: sqlite3.Connection, counts: dict) -> bool:
    row = conn.execute(
        """
        SELECT source_run_count, source_snapshot_count, source_claim_count,
               source_evidence_count, source_binding_count, index_version
        FROM archive_search_meta
        WHERE id = 1
        """
    ).fetchone()
    if not row:
        return False
    return (
        row[0] == counts["source_run_count"]
        and row[1] == counts["source_snapshot_count"]
        and row[2] == counts["source_claim_count"]
        and row[3] == counts["source_evidence_count"]
        and row[4] == counts["source_binding_count"]
        and row[5] == ARCHIVE_SEARCH_INDEX_VERSION
    )


def rebuild_archive_search_index(conn: sqlite3.Connection) -> dict:
    available, reason = ensure_archive_search_schema(conn)
    if not available:
        return {"available": False, "backend": "like", "reason": reason, "rebuilt": False}

    counts = archive_source_counts(conn)
    if archive_search_index_current(conn, counts):
        row = conn.execute(
            "SELECT rebuilt_at, indexed_documents FROM archive_search_meta WHERE id = 1"
        ).fetchone()
        return {
            "available": True,
            "backend": "fts5",
            "reason": None,
            "rebuilt": False,
            "rebuilt_at": row[0] if row else None,
            "indexed_documents": row[1] if row else 0,
            "index_version": ARCHIVE_SEARCH_INDEX_VERSION,
            **counts,
        }

    conn.execute("DELETE FROM archive_search_fts")
    indexed_documents = 0

    repo_rows = conn.execute(
        """
        SELECT s.run_id, s.full_name, s.description, s.language, s.topics_json,
               s.fake_star_risk, s.project_track, s.track_score, r.mode
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
        """
    ).fetchall()
    for row in repo_rows:
        run_id, full_name, description, language, topics_json, risk, track, track_score, mode = row
        body = " ".join(
            str(item or "")
            for item in [
                description,
                language,
                " ".join(safe_json_loads(topics_json, [])),
                risk,
                track,
                mode,
            ]
        )
        conn.execute(
            """
            INSERT INTO archive_search_fts (
                repo_full_name, run_id, source_type, source_id, title, body, track, track_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (full_name, run_id, "repository", full_name, full_name, body, track, track_score),
        )
        indexed_documents += 1

    claim_rows = conn.execute(
        """
        SELECT c.run_id, c.repo_full_name, COALESCE(c.claim_id, c.field), c.field,
               c.text, c.confidence, c.template, c.rationale, c.support_coverage_json,
               c.evidence_ids_json, s.project_track, s.track_score
        FROM claims c
        LEFT JOIN repository_snapshots s
          ON s.run_id = c.run_id AND s.full_name = c.repo_full_name
        """
    ).fetchall()
    claims_by_snapshot: dict[tuple[int, str, str | None, float | None], list[dict]] = {}
    for row in claim_rows:
        (
            run_id,
            full_name,
            source_id,
            field,
            text,
            confidence,
            template,
            rationale,
            coverage_json,
            evidence_ids_json,
            track,
            track_score,
        ) = row
        coverage = safe_json_loads(coverage_json, {})
        coverage_terms = " ".join(
            str(item or "")
            for item in [
                coverage.get("level"),
                coverage.get("label"),
                coverage.get("summary"),
                " ".join(coverage.get("layers") or []),
                " ".join(coverage.get("layer_labels") or []),
            ]
        )
        conn.execute(
            """
            INSERT INTO archive_search_fts (
                repo_full_name, run_id, source_type, source_id, title, body, track, track_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                run_id,
                "claim",
                source_id,
                field,
                f"{text} {confidence} {template or ''} {rationale or ''} {coverage_terms}",
                track,
                track_score,
            ),
        )
        indexed_documents += 1
        claims_by_snapshot.setdefault((run_id, full_name, track, track_score), []).append(
            {
                "claim_id": source_id,
                "field": field,
                "text": text,
                "confidence": confidence,
                "support_coverage": coverage,
                "evidence_ids": safe_json_loads(evidence_ids_json, []),
            }
        )

    for (run_id, full_name, track, track_score), claim_group in claims_by_snapshot.items():
        for item in build_claim_gap_report(claim_group):
            body = " ".join(
                str(value or "")
                for value in [
                    "claim_gap",
                    item.get("support_level"),
                    item.get("support_label"),
                    item.get("gap_reason"),
                    item.get("recommendation"),
                    " ".join(item.get("missing_layers") or []),
                    " ".join(item.get("missing_layer_labels") or []),
                    " ".join(item.get("current_layers") or []),
                    " ".join(item.get("current_layer_labels") or []),
                ]
            )
            conn.execute(
                """
                INSERT INTO archive_search_fts (
                    repo_full_name, run_id, source_type, source_id, title, body, track, track_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    full_name,
                    run_id,
                    "claim_gap",
                    item.get("claim_id") or item.get("field"),
                    f"Gap - {item.get('field')}",
                    body,
                    track,
                    track_score,
                ),
            )
            indexed_documents += 1

    evidence_rows = conn.execute(
        """
        SELECT e.run_id, e.repo_full_name, COALESCE(e.stable_id, e.evidence_id), e.kind,
               e.title, e.quote, e.evidence_type, e.polarity, e.signal_tags_json,
               s.project_track, s.track_score
        FROM evidence_items e
        LEFT JOIN repository_snapshots s
          ON s.run_id = e.run_id AND s.full_name = e.repo_full_name
        """
    ).fetchall()
    for row in evidence_rows:
        run_id, full_name, source_id, kind, title, quote, evidence_type, polarity, tags_json, track, track_score = row
        tags = " ".join(safe_json_loads(tags_json, []))
        conn.execute(
            """
            INSERT INTO archive_search_fts (
                repo_full_name, run_id, source_type, source_id, title, body, track, track_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                run_id,
                "evidence",
                source_id,
                f"{kind} - {title}",
                f"{quote} {evidence_type or ''} {polarity or ''} {tags}",
                track,
                track_score,
            ),
        )
        indexed_documents += 1

    binding_rows = conn.execute(
        """
        SELECT b.run_id, b.repo_full_name, b.evidence_id, b.evidence_stable_id,
               b.claim_id, b.field, b.missing_layer, b.missing_layer_label,
               b.keywords_json, b.reason, b.binding_confidence_score,
               b.binding_confidence_label, b.binding_calibration,
               b.binding_confidence_signals_json, b.auto_confidence_score,
               b.auto_confidence_label, b.auto_calibration,
               b.auto_confidence_signals_json, b.auto_calibrated_at,
               e.kind, e.title, e.quote,
               s.project_track, s.track_score
        FROM evidence_acquisition_bindings b
        LEFT JOIN evidence_items e
          ON e.run_id = b.run_id
         AND e.repo_full_name = b.repo_full_name
         AND e.evidence_id = b.evidence_id
        LEFT JOIN repository_snapshots s
          ON s.run_id = b.run_id AND s.full_name = b.repo_full_name
        """
    ).fetchall()
    for row in binding_rows:
        (
            run_id,
            full_name,
            evidence_id,
            evidence_stable_id,
            claim_id,
            field,
            missing_layer,
            missing_layer_label,
            keywords_json,
            reason,
            confidence_score,
            confidence_label,
            calibration,
            confidence_signals_json,
            auto_score,
            auto_label,
            auto_calibration,
            auto_signals_json,
            auto_calibrated_at,
            kind,
            title,
            quote,
            track,
            track_score,
        ) = row
        keywords = " ".join(safe_json_loads(keywords_json, []))
        confidence_terms = " ".join(
            str(value or "")
            for value in [
                confidence_score,
                confidence_label,
                calibration,
                " ".join(safe_json_loads(confidence_signals_json, [])),
                auto_score,
                auto_label,
                auto_calibration,
                " ".join(safe_json_loads(auto_signals_json, [])),
                auto_calibrated_at,
            ]
        )
        body = " ".join(
            str(value or "")
            for value in [
                "acquisition_binding",
                "claim_gap",
                claim_id,
                field,
                missing_layer,
                missing_layer_label,
                keywords,
                reason,
                confidence_terms,
                kind,
                title,
                quote,
            ]
        )
        conn.execute(
            """
            INSERT INTO archive_search_fts (
                repo_full_name, run_id, source_type, source_id, title, body, track, track_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                run_id,
                "acquisition_binding",
                f"{evidence_id}|{field}|{missing_layer}",
                f"Acquisition - {field} - {missing_layer_label or missing_layer}",
                body,
                track,
                track_score,
            ),
        )
        indexed_documents += 1

    rebuilt_at = utc_now().isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO archive_search_meta (
            id, rebuilt_at, source_run_count, source_snapshot_count,
            source_claim_count, source_evidence_count, source_binding_count,
            indexed_documents, index_version
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rebuilt_at,
            counts["source_run_count"],
            counts["source_snapshot_count"],
            counts["source_claim_count"],
            counts["source_evidence_count"],
            counts["source_binding_count"],
            indexed_documents,
            ARCHIVE_SEARCH_INDEX_VERSION,
        ),
    )
    return {
        "available": True,
        "backend": "fts5",
        "reason": None,
        "rebuilt": True,
        "rebuilt_at": rebuilt_at,
        "indexed_documents": indexed_documents,
        "index_version": ARCHIVE_SEARCH_INDEX_VERSION,
        **counts,
    }


def fts_query_from_user(query: str) -> str:
    terms = re.findall(r"[\w\u0080-\uffff][\w\u0080-\uffff./:@+-]*", query, flags=re.UNICODE)
    if not terms:
        terms = [query.strip()]
    quoted = []
    for term in terms:
        cleaned = term.strip().replace('"', '""')
        if cleaned:
            quoted.append(f'"{cleaned}"')
    return " OR ".join(quoted) if quoted else '""'


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


def normalize_binding_confidence(binding: dict | None) -> dict:
    confidence = (binding or {}).get("binding_confidence") or {}
    score = confidence.get("score")
    try:
        score = int(float(score))
    except (TypeError, ValueError):
        score = 50
    score = int(clamp(score, 0, 100))
    label = confidence.get("label") or binding_confidence_label(score)
    calibration = confidence.get("calibration") or "legacy_or_imported"
    signals = confidence.get("signals") or []
    signal_breakdown = confidence.get("signal_breakdown") or confidence_signal_breakdown(signals)
    return {
        "score": score,
        "label": label,
        "calibration": calibration,
        "signals": signals,
        "signal_breakdown": signal_breakdown,
    }


def insert_acquisition_bindings(conn: sqlite3.Connection, run_id: int, payload: dict) -> None:
    repository = payload["repository"]["full_name"]
    evidence_stable_ids = {
        item.get("evidence_id"): item.get("stable_id")
        for item in payload.get("evidence") or []
        if item.get("evidence_id")
    }
    bindings = ((payload.get("evidence_acquisition") or {}).get("bindings") or [])
    for binding in bindings:
        evidence_id = binding.get("evidence_id")
        field = binding.get("field") or ""
        layer = binding.get("missing_layer") or ""
        if not evidence_id or not field or not layer:
            continue
        confidence = normalize_binding_confidence(binding)
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_acquisition_bindings (
                run_id, repo_full_name, evidence_id, evidence_stable_id, claim_id,
                field, missing_layer, missing_layer_label, keywords_json, reason,
                binding_confidence_score, binding_confidence_label, binding_calibration,
                binding_confidence_signals_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                repository,
                evidence_id,
                binding.get("evidence_stable_id") or evidence_stable_ids.get(evidence_id),
                binding.get("claim_id") or "",
                field,
                layer,
                binding.get("missing_layer_label") or SUPPORT_LAYER_LABELS.get(layer, layer),
                json.dumps(binding.get("keywords") or [], ensure_ascii=False),
                binding.get("reason") or "",
                confidence["score"],
                confidence["label"],
                confidence["calibration"],
                json.dumps(confidence["signals"], ensure_ascii=False),
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
                    run_id, repo_full_name, evidence_id, stable_id, level, kind, title, url, quote,
                    evidence_type, polarity, signal_tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item.get("evidence_type"),
                    item.get("polarity"),
                    json.dumps(item.get("signal_tags") or [], ensure_ascii=False),
                ),
            )
        for item in payload["claims"]:
            conn.execute(
                """
                INSERT INTO claims (
                    run_id, repo_full_name, claim_id, field, text, evidence_ids_json,
                    evidence_stable_ids_json, counter_evidence_ids_json,
                    counter_evidence_stable_ids_json, template, rationale, support_coverage_json, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    payload["repository"]["full_name"],
                    item.get("claim_id"),
                    item["field"],
                    item["text"],
                    json.dumps(item["evidence_ids"], ensure_ascii=False),
                    json.dumps(item.get("evidence_stable_ids") or [], ensure_ascii=False),
                    json.dumps(item.get("counter_evidence_ids") or [], ensure_ascii=False),
                    json.dumps(item.get("counter_evidence_stable_ids") or [], ensure_ascii=False),
                    item.get("template"),
                    item.get("rationale"),
                    json.dumps(item.get("support_coverage") or {}, ensure_ascii=False),
                    item["confidence"],
                ),
            )
        insert_acquisition_bindings(conn, run_id, payload)
        rebuild_archive_search_index(conn)
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
        rebuild_archive_search_index(conn)
        conn.commit()
        return run_id


def safe_json_loads(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def binding_confidence_from_row(row: sqlite3.Row) -> dict:
    row_keys = row.keys()
    heuristic_score = row["binding_confidence_score"] if "binding_confidence_score" in row_keys else None
    try:
        heuristic_score = int(float(heuristic_score))
    except (TypeError, ValueError):
        heuristic_score = 50
    heuristic_score = int(clamp(heuristic_score, 0, 100))
    heuristic_label = (
        row["binding_confidence_label"] if "binding_confidence_label" in row_keys else None
    ) or binding_confidence_label(heuristic_score)
    heuristic_calibration = (
        row["binding_calibration"] if "binding_calibration" in row_keys else None
    ) or "legacy_or_imported"
    signals_json = row["binding_confidence_signals_json"] if "binding_confidence_signals_json" in row_keys else None
    heuristic_signals = safe_json_loads(signals_json, [])
    heuristic_breakdown = confidence_signal_breakdown(heuristic_signals)
    heuristic_confidence = {
        "score": heuristic_score,
        "label": heuristic_label,
        "calibration": heuristic_calibration,
        "signals": heuristic_signals,
        "signal_breakdown": heuristic_breakdown,
    }

    auto_score = row["auto_confidence_score"] if "auto_confidence_score" in row_keys else None
    try:
        auto_score = int(float(auto_score))
    except (TypeError, ValueError):
        auto_score = None

    if auto_score is None:
        return {
            "score": heuristic_score,
            "label": heuristic_label,
            "calibration": heuristic_calibration,
            "signals": heuristic_signals,
            "signal_breakdown": heuristic_breakdown,
            "source": "heuristic",
            "heuristic": heuristic_confidence,
        }

    auto_score = int(clamp(auto_score, 0, 100))
    auto_calibration = (
        row["auto_calibration"] if "auto_calibration" in row_keys else None
    ) or AUTO_CONFIDENCE_CALIBRATION
    auto_label = (
        row["auto_confidence_label"] if "auto_confidence_label" in row_keys else None
    ) or confidence_label_for_calibration(auto_score, auto_calibration)
    auto_signals_json = row["auto_confidence_signals_json"] if "auto_confidence_signals_json" in row_keys else None
    auto_signals = safe_json_loads(auto_signals_json, [])
    auto_breakdown = confidence_signal_breakdown(auto_signals)
    return {
        "score": auto_score,
        "label": auto_label,
        "calibration": auto_calibration,
        "signals": auto_signals,
        "signal_breakdown": auto_breakdown,
        "source": "auto",
        "heuristic": heuristic_confidence,
        "auto_calibration": {
            "score": auto_score,
            "label": auto_label,
            "calibration": auto_calibration,
            "signals": auto_signals,
            "signal_breakdown": auto_breakdown,
            "calibrated_at": row["auto_calibrated_at"] if "auto_calibrated_at" in row_keys else None,
        },
    }


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


def query_archive_search_fts(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    track: str | None = None,
    min_track_score: float = 0.0,
) -> list[dict]:
    fts_query = fts_query_from_user(query)
    hit_rows = conn.execute(
        """
        SELECT repo_full_name, source_type, rank
        FROM archive_search_fts
        WHERE archive_search_fts MATCH ?
        ORDER BY rank ASC
        LIMIT 1000
        """,
        (fts_query,),
    ).fetchall()
    ranked: dict[str, dict] = {}
    for row in hit_rows:
        full_name = row["repo_full_name"]
        item = ranked.setdefault(
            full_name,
            {
                "repo_full_name": full_name,
                "rank": row["rank"],
                "matched_documents": 0,
                "source_types": set(),
            },
        )
        item["rank"] = min(item["rank"], row["rank"])
        item["matched_documents"] += 1
        item["source_types"].add(row["source_type"])

    if not ranked:
        return []

    placeholders = ",".join("?" for _ in ranked)
    rows = conn.execute(
        f"""
        SELECT s.*, r.id AS run_id, r.created_at AS run_created_at, r.mode AS run_mode,
               s.full_name AS ranked_full_name
        FROM repository_snapshots s
        JOIN runs r ON r.id = s.run_id
        WHERE s.full_name IN ({placeholders})
        AND s.run_id = (
            SELECT s2.run_id
            FROM repository_snapshots s2
            JOIN runs r2 ON r2.id = s2.run_id
            WHERE s2.full_name = s.full_name
            ORDER BY r2.created_at DESC, s2.run_id DESC
            LIMIT 1
        )
        AND (? IS NULL OR s.project_track = ?)
        AND (? <= 0 OR COALESCE(s.track_score, 0) >= ?)
        """,
        (*ranked.keys(), track, track, min_track_score, min_track_score),
    ).fetchall()

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            ranked[row["ranked_full_name"]]["rank"],
            -(row["track_score"] or 0),
            -(row["stars"] or 0),
        ),
    )[: max(limit, 1)]

    entries = []
    for row in sorted_rows:
        summary = row_to_archive_summary(row)
        summary["health"] = load_archive_health(conn, summary["run_id"], summary["full_name"])
        info = ranked[summary["full_name"]]
        source_types = sorted(info["source_types"])
        entries.append(
            {
                "repository": summary,
                "relevance": {
                    "backend": "fts5",
                    "score": round(max(0.0, -float(info["rank"] or 0.0)), 6),
                    "rank": info["rank"],
                    "matched_documents": info["matched_documents"],
                    "source_types": source_types,
                    "query": fts_query,
                },
                "matched_claims": query_archive_claim_matches(conn, summary["full_name"], query, backend="fts5"),
                "matched_gaps": query_archive_gap_matches(conn, summary["full_name"], query, backend="fts5"),
                "matched_bindings": query_archive_binding_matches(conn, summary["full_name"], query, backend="fts5"),
                "matched_evidence": query_archive_evidence_matches(conn, summary["full_name"], query, backend="fts5"),
            }
        )
    return entries


def query_archive_search_like(
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
                AND LOWER(COALESCE(c.field, '') || ' ' || COALESCE(c.text, '') || ' ' || COALESCE(c.support_coverage_json, '')) LIKE ?
            )
            OR EXISTS (
                SELECT 1
                FROM evidence_items e
                WHERE e.repo_full_name = s.full_name
                AND LOWER(COALESCE(e.kind, '') || ' ' || COALESCE(e.title, '') || ' ' || COALESCE(e.quote, '')) LIKE ?
            )
            OR EXISTS (
                SELECT 1
                FROM evidence_acquisition_bindings b
                WHERE b.repo_full_name = s.full_name
                AND LOWER(
                    COALESCE(b.field, '') || ' ' ||
                    COALESCE(b.missing_layer, '') || ' ' ||
                    COALESCE(b.missing_layer_label, '') || ' ' ||
                    COALESCE(b.keywords_json, '') || ' ' ||
                    COALESCE(b.reason, '') || ' ' ||
                    COALESCE(b.binding_confidence_label, '') || ' ' ||
                    COALESCE(b.binding_calibration, '') || ' ' ||
                    COALESCE(b.binding_confidence_signals_json, '') || ' ' ||
                    COALESCE(b.auto_confidence_label, '') || ' ' ||
                    COALESCE(b.auto_calibration, '') || ' ' ||
                    COALESCE(b.auto_confidence_signals_json, '') || ' ' ||
                    COALESCE(b.auto_calibrated_at, '')
                ) LIKE ?
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
                "relevance": {
                    "backend": "like",
                    "score": None,
                    "rank": None,
                    "matched_documents": None,
                    "source_types": [],
                    "query": query,
                },
                "matched_claims": query_archive_claim_matches(conn, summary["full_name"], query),
                "matched_gaps": query_archive_gap_matches(conn, summary["full_name"], query),
                "matched_bindings": query_archive_binding_matches(conn, summary["full_name"], query),
                "matched_evidence": query_archive_evidence_matches(conn, summary["full_name"], query),
            }
        )
    return entries


def query_archive_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    track: str | None = None,
    min_track_score: float = 0.0,
    index_status: dict | None = None,
) -> list[dict]:
    status = index_status or rebuild_archive_search_index(conn)
    if status.get("available"):
        try:
            results = query_archive_search_fts(conn, query, limit, track, min_track_score)
            if results:
                return results
        except sqlite3.Error:
            return query_archive_search_like(conn, query, limit, track, min_track_score)
    return query_archive_search_like(conn, query, limit, track, min_track_score)


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
    claims = query_archive_claims(conn, summary["run_id"], summary["full_name"])
    gaps = build_claim_gap_report(claims)
    evidence = query_archive_evidence(conn, summary["run_id"], summary["full_name"])
    bindings = query_archive_acquisition_bindings(conn, summary["run_id"], summary["full_name"])
    attach_acquisition_bindings(evidence, bindings)
    return {
        "repository": summary,
        "claims": claims,
        "claim_gap_report": gaps,
        "evidence_acquisition": archive_evidence_acquisition_summary(gaps, evidence, bindings),
        "evidence": evidence,
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
        SELECT claim_id, field, text, evidence_ids_json, evidence_stable_ids_json,
               counter_evidence_ids_json, counter_evidence_stable_ids_json,
               template, rationale, support_coverage_json, confidence
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
            "counter_evidence_ids": safe_json_loads(row["counter_evidence_ids_json"], []),
            "counter_evidence_stable_ids": safe_json_loads(row["counter_evidence_stable_ids_json"], []),
            "template": row["template"],
            "rationale": row["rationale"],
            "support_coverage": safe_json_loads(row["support_coverage_json"], {}),
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def query_archive_evidence(conn: sqlite3.Connection, run_id: int, full_name: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT evidence_id, stable_id, level, kind, title, url, quote,
               evidence_type, polarity, signal_tags_json
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
            "evidence_type": row["evidence_type"] or "general",
            "polarity": row["polarity"] or "supporting",
            "signal_tags": safe_json_loads(row["signal_tags_json"], []),
        }
        for row in rows
    ]


def query_archive_acquisition_bindings(conn: sqlite3.Connection, run_id: int, full_name: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT evidence_id, evidence_stable_id, claim_id, field, missing_layer,
               missing_layer_label, keywords_json, reason,
               binding_confidence_score, binding_confidence_label, binding_calibration,
               binding_confidence_signals_json, auto_confidence_score,
               auto_confidence_label, auto_calibration,
               auto_confidence_signals_json, auto_calibrated_at
        FROM evidence_acquisition_bindings
        WHERE run_id = ? AND repo_full_name = ?
        ORDER BY rowid
        """,
        (run_id, full_name),
    ).fetchall()
    return [
        {
            "evidence_id": row["evidence_id"],
            "evidence_stable_id": row["evidence_stable_id"],
            "claim_id": row["claim_id"],
            "field": row["field"],
            "missing_layer": row["missing_layer"],
            "missing_layer_label": row["missing_layer_label"] or SUPPORT_LAYER_LABELS.get(row["missing_layer"], row["missing_layer"]),
            "keywords": safe_json_loads(row["keywords_json"], []),
            "reason": row["reason"],
            "binding_confidence": binding_confidence_from_row(row),
        }
        for row in rows
    ]


def attach_acquisition_bindings(evidence: list[dict], bindings: list[dict]) -> None:
    by_evidence_id: dict[str, list[dict]] = {}
    by_stable_id: dict[str, list[dict]] = {}
    for binding in bindings:
        if binding.get("evidence_id"):
            by_evidence_id.setdefault(binding["evidence_id"], []).append(binding)
        if binding.get("evidence_stable_id"):
            by_stable_id.setdefault(binding["evidence_stable_id"], []).append(binding)

    for item in evidence:
        matches = by_evidence_id.get(item.get("evidence_id") or "", [])
        if not matches:
            matches = by_stable_id.get(item.get("stable_id") or "", [])
        if matches:
            item["acquisition_bindings"] = matches


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def archive_evidence_acquisition_summary(gaps: list[dict], evidence: list[dict], bindings: list[dict]) -> dict:
    if not bindings:
        return {}
    evidence_ids = unique_ordered([binding.get("evidence_id", "") for binding in bindings])
    requested_layers = unique_ordered([binding.get("missing_layer", "") for binding in bindings])
    added_counts: dict[str, int] = {}
    confidence_source_counts: dict[str, int] = {}
    confidence_scores = [
        (binding.get("binding_confidence") or {}).get("score")
        for binding in bindings
        if isinstance((binding.get("binding_confidence") or {}).get("score"), (int, float))
    ]
    for binding in bindings:
        layer = binding.get("missing_layer") or "unknown"
        added_counts[layer] = added_counts.get(layer, 0) + 1
        confidence = binding.get("binding_confidence") or {}
        count_value(confidence_source_counts, confidence.get("source") or "heuristic")
    return {
        "strategy": "claim_gap_targeted",
        "requested_layers": requested_layers,
        "requested_layer_labels": [SUPPORT_LAYER_LABELS.get(layer, layer) for layer in requested_layers],
        "added_total": len(evidence_ids),
        "added_counts": added_counts,
        "added_evidence_ids": evidence_ids,
        "binding_count": len(bindings),
        "bindings": bindings,
        "average_binding_confidence": round(sum(confidence_scores) / len(confidence_scores), 1) if confidence_scores else None,
        "minimum_binding_confidence": min(confidence_scores) if confidence_scores else None,
        "confidence_sources": top_count_items(confidence_source_counts),
        "target_claim_fields": unique_ordered([binding.get("field", "") for binding in bindings]),
        "status": "expanded",
        "source": "archive",
    }


def query_archive_claim_matches(
    conn: sqlite3.Connection,
    full_name: str,
    query: str,
    limit: int = 3,
    backend: str = "like",
) -> list[dict]:
    if backend == "fts5":
        fts_query = fts_query_from_user(query)
        rows = conn.execute(
            """
            SELECT c.run_id, c.claim_id, c.field, c.text, c.template, c.rationale, c.confidence,
                   c.support_coverage_json, archive_search_fts.rank AS relevance_rank
            FROM archive_search_fts
            JOIN claims c
              ON c.run_id = archive_search_fts.run_id
             AND c.repo_full_name = archive_search_fts.repo_full_name
             AND COALESCE(c.claim_id, c.field) = archive_search_fts.source_id
            WHERE archive_search_fts MATCH ?
              AND archive_search_fts.repo_full_name = ?
              AND archive_search_fts.source_type = 'claim'
            ORDER BY rank ASC, c.run_id DESC
            LIMIT ?
            """,
            (fts_query, full_name, limit),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "claim_id": row["claim_id"],
                "field": row["field"],
                "text": row["text"],
                "template": row["template"],
                "rationale": row["rationale"],
                "confidence": row["confidence"],
                "support_coverage": safe_json_loads(row["support_coverage_json"], {}),
                "relevance": {"backend": "fts5", "score": round(max(0.0, -float(row["relevance_rank"] or 0.0)), 6)},
            }
            for row in rows
        ]

    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT run_id, claim_id, field, text, template, rationale, support_coverage_json, confidence
        FROM claims
        WHERE repo_full_name = ?
        AND LOWER(COALESCE(field, '') || ' ' || COALESCE(text, '') || ' ' || COALESCE(support_coverage_json, '')) LIKE ?
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
            "template": row["template"],
            "rationale": row["rationale"],
            "confidence": row["confidence"],
            "support_coverage": safe_json_loads(row["support_coverage_json"], {}),
            "relevance": {"backend": "like", "score": None},
        }
        for row in rows
    ]


def query_archive_gap_matches(
    conn: sqlite3.Connection,
    full_name: str,
    query: str,
    limit: int = 3,
    backend: str = "like",
) -> list[dict]:
    if backend == "fts5":
        fts_query = fts_query_from_user(query)
        rows = conn.execute(
            """
            SELECT run_id, source_id, title, body, archive_search_fts.rank AS relevance_rank
            FROM archive_search_fts
            WHERE archive_search_fts MATCH ?
              AND repo_full_name = ?
              AND source_type = 'claim_gap'
            ORDER BY rank ASC, run_id DESC
            LIMIT ?
            """,
            (fts_query, full_name, limit),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "source_id": row["source_id"],
                "field": (row["title"] or "").removeprefix("Gap - "),
                "text": row["body"],
                "relevance": {"backend": "fts5", "score": round(max(0.0, -float(row["relevance_rank"] or 0.0)), 6)},
            }
            for row in rows
        ]

    dossier = query_archive_show(conn, full_name) or {}
    query_lower = query.lower()
    matches = []
    for item in dossier.get("claim_gap_report") or []:
        body = " ".join(
            str(value or "")
            for value in [
                item.get("field"),
                item.get("support_level"),
                item.get("support_label"),
                item.get("gap_reason"),
                item.get("recommendation"),
                " ".join(item.get("missing_layers") or []),
                " ".join(item.get("missing_layer_labels") or []),
            ]
        )
        if query_lower in body.lower():
            matches.append(
                {
                    "run_id": (dossier.get("repository") or {}).get("run_id"),
                    "source_id": item.get("claim_id") or item.get("field"),
                    "field": item.get("field"),
                    "text": body,
                    "relevance": {"backend": "like", "score": None},
                }
            )
    return matches[:limit]


def query_archive_evidence_matches(
    conn: sqlite3.Connection,
    full_name: str,
    query: str,
    limit: int = 3,
    backend: str = "like",
) -> list[dict]:
    if backend == "fts5":
        fts_query = fts_query_from_user(query)
        rows = conn.execute(
            """
            SELECT e.run_id, e.evidence_id, e.stable_id, e.kind, e.title, e.url, e.quote,
                   e.evidence_type, e.polarity, e.signal_tags_json,
                   archive_search_fts.rank AS relevance_rank
            FROM archive_search_fts
            JOIN evidence_items e
              ON e.run_id = archive_search_fts.run_id
             AND e.repo_full_name = archive_search_fts.repo_full_name
             AND COALESCE(e.stable_id, e.evidence_id) = archive_search_fts.source_id
            WHERE archive_search_fts MATCH ?
              AND archive_search_fts.repo_full_name = ?
              AND archive_search_fts.source_type = 'evidence'
            ORDER BY rank ASC, e.run_id DESC
            LIMIT ?
            """,
            (fts_query, full_name, limit),
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
                "evidence_type": row["evidence_type"] or "general",
                "polarity": row["polarity"] or "supporting",
                "signal_tags": safe_json_loads(row["signal_tags_json"], []),
                "relevance": {"backend": "fts5", "score": round(max(0.0, -float(row["relevance_rank"] or 0.0)), 6)},
            }
            for row in rows
        ]

    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT run_id, evidence_id, stable_id, kind, title, url, quote,
               evidence_type, polarity, signal_tags_json
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
            "evidence_type": row["evidence_type"] or "general",
            "polarity": row["polarity"] or "supporting",
            "signal_tags": safe_json_loads(row["signal_tags_json"], []),
            "relevance": {"backend": "like", "score": None},
        }
        for row in rows
    ]


def query_archive_binding_matches(
    conn: sqlite3.Connection,
    full_name: str,
    query: str,
    limit: int = 3,
    backend: str = "like",
) -> list[dict]:
    if backend == "fts5":
        fts_query = fts_query_from_user(query)
        rows = conn.execute(
            """
            SELECT b.run_id, b.evidence_id, b.evidence_stable_id, b.claim_id, b.field,
                   b.missing_layer, b.missing_layer_label, b.keywords_json, b.reason,
                   b.binding_confidence_score, b.binding_confidence_label, b.binding_calibration,
                   b.binding_confidence_signals_json, b.auto_confidence_score,
                   b.auto_confidence_label, b.auto_calibration,
                   b.auto_confidence_signals_json, b.auto_calibrated_at,
                   archive_search_fts.rank AS relevance_rank
            FROM archive_search_fts
            JOIN evidence_acquisition_bindings b
              ON b.run_id = archive_search_fts.run_id
             AND b.repo_full_name = archive_search_fts.repo_full_name
             AND b.evidence_id || '|' || b.field || '|' || b.missing_layer = archive_search_fts.source_id
            WHERE archive_search_fts MATCH ?
              AND archive_search_fts.repo_full_name = ?
              AND archive_search_fts.source_type = 'acquisition_binding'
            ORDER BY rank ASC, b.run_id DESC
            LIMIT ?
            """,
            (fts_query, full_name, limit),
        ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "evidence_id": row["evidence_id"],
                "evidence_stable_id": row["evidence_stable_id"],
                "claim_id": row["claim_id"],
                "field": row["field"],
                "missing_layer": row["missing_layer"],
                "missing_layer_label": row["missing_layer_label"] or SUPPORT_LAYER_LABELS.get(row["missing_layer"], row["missing_layer"]),
                "keywords": safe_json_loads(row["keywords_json"], []),
                "reason": row["reason"],
                "binding_confidence": binding_confidence_from_row(row),
                "relevance": {"backend": "fts5", "score": round(max(0.0, -float(row["relevance_rank"] or 0.0)), 6)},
            }
            for row in rows
        ]

    like = f"%{query.lower()}%"
    rows = conn.execute(
        """
        SELECT run_id, evidence_id, evidence_stable_id, claim_id, field,
               missing_layer, missing_layer_label, keywords_json, reason,
               binding_confidence_score, binding_confidence_label, binding_calibration,
               binding_confidence_signals_json, auto_confidence_score,
               auto_confidence_label, auto_calibration,
               auto_confidence_signals_json, auto_calibrated_at
        FROM evidence_acquisition_bindings
        WHERE repo_full_name = ?
        AND LOWER(
            COALESCE(field, '') || ' ' ||
            COALESCE(missing_layer, '') || ' ' ||
            COALESCE(missing_layer_label, '') || ' ' ||
            COALESCE(keywords_json, '') || ' ' ||
            COALESCE(reason, '') || ' ' ||
            COALESCE(binding_confidence_label, '') || ' ' ||
            COALESCE(binding_calibration, '') || ' ' ||
            COALESCE(binding_confidence_signals_json, '') || ' ' ||
            COALESCE(auto_confidence_label, '') || ' ' ||
            COALESCE(auto_calibration, '') || ' ' ||
            COALESCE(auto_confidence_signals_json, '') || ' ' ||
            COALESCE(auto_calibrated_at, '')
        ) LIKE ?
        ORDER BY run_id DESC, rowid
        LIMIT ?
        """,
        (full_name, like, limit),
    ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "evidence_id": row["evidence_id"],
            "evidence_stable_id": row["evidence_stable_id"],
            "claim_id": row["claim_id"],
            "field": row["field"],
            "missing_layer": row["missing_layer"],
            "missing_layer_label": row["missing_layer_label"] or SUPPORT_LAYER_LABELS.get(row["missing_layer"], row["missing_layer"]),
            "keywords": safe_json_loads(row["keywords_json"], []),
            "reason": row["reason"],
            "binding_confidence": binding_confidence_from_row(row),
            "relevance": {"backend": "like", "score": None},
        }
        for row in rows
    ]


def count_value(counts: dict[str, int], value: str | None) -> None:
    cleaned = str(value or "").strip()
    if cleaned:
        counts[cleaned] = counts.get(cleaned, 0) + 1


def top_count_items(counts: dict[str, int], limit: int = 8) -> list[dict]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def aggregate_pattern_count_items(patterns: list[dict], key: str, limit: int = 8) -> list[dict]:
    counts: dict[str, int] = {}
    for pattern in patterns:
        for item in pattern.get(key) or []:
            value = item.get("value")
            if value:
                counts[value] = counts.get(value, 0) + int(item.get("count") or 0)
    return top_count_items(counts, limit=limit)


def query_archive_pattern_bindings(
    conn: sqlite3.Connection,
    track: str | None = None,
    min_track_score: float = 0.0,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT b.run_id, b.repo_full_name, b.evidence_id, b.evidence_stable_id,
               b.claim_id, b.field, b.missing_layer, b.missing_layer_label,
               b.keywords_json, b.reason, b.binding_confidence_score,
               b.binding_confidence_label, b.binding_calibration,
               b.binding_confidence_signals_json, b.auto_confidence_score,
               b.auto_confidence_label, b.auto_calibration,
               b.auto_confidence_signals_json, b.auto_calibrated_at,
               r.created_at AS run_created_at,
               s.project_track, s.track_score,
               e.kind AS evidence_kind, e.title AS evidence_title,
               e.url AS evidence_url, e.quote AS evidence_quote,
               e.evidence_type, e.polarity, e.signal_tags_json
        FROM evidence_acquisition_bindings b
        JOIN runs r ON r.id = b.run_id
        JOIN repository_snapshots s
          ON s.run_id = b.run_id AND s.full_name = b.repo_full_name
        LEFT JOIN evidence_items e
          ON e.run_id = b.run_id
         AND e.repo_full_name = b.repo_full_name
         AND e.evidence_id = b.evidence_id
        WHERE r.mode = 'deep'
          AND b.run_id = (
              SELECT s2.run_id
              FROM repository_snapshots s2
              JOIN runs r2 ON r2.id = s2.run_id
              WHERE s2.full_name = b.repo_full_name
                AND r2.mode = 'deep'
              ORDER BY r2.created_at DESC, s2.run_id DESC
              LIMIT 1
          )
          AND (? IS NULL OR s.project_track = ?)
          AND (? <= 0 OR COALESCE(s.track_score, 0) >= ?)
        ORDER BY b.field, b.missing_layer, COALESCE(s.track_score, 0) DESC, b.repo_full_name, b.evidence_id
        """,
        (track, track, min_track_score, min_track_score),
    ).fetchall()
    return [
        {
            "run_id": row["run_id"],
            "run_created_at": row["run_created_at"],
            "repo_full_name": row["repo_full_name"],
            "track": row["project_track"] or "unknown",
            "track_score": row["track_score"],
            "claim_id": row["claim_id"],
            "field": row["field"],
            "missing_layer": row["missing_layer"],
            "missing_layer_label": row["missing_layer_label"] or SUPPORT_LAYER_LABELS.get(row["missing_layer"], row["missing_layer"]),
            "keywords": safe_json_loads(row["keywords_json"], []),
            "reason": row["reason"],
            "binding_confidence": binding_confidence_from_row(row),
            "evidence_id": row["evidence_id"],
            "evidence_stable_id": row["evidence_stable_id"],
            "evidence_kind": row["evidence_kind"],
            "evidence_title": row["evidence_title"],
            "evidence_url": row["evidence_url"],
            "evidence_quote": row["evidence_quote"],
            "evidence_type": row["evidence_type"] or "general",
            "polarity": row["polarity"] or "supporting",
            "signal_tags": safe_json_loads(row["signal_tags_json"], []),
        }
        for row in rows
    ]


def filter_archive_pattern_rows_by_signal_group(rows: list[dict], signal_group: str | None) -> list[dict]:
    if not signal_group:
        return rows
    return [
        row
        for row in rows
        if signal_group in confidence_signal_group_names(row.get("binding_confidence") or {})
    ]


def mean_number(values: list[int | float], digits: int = 1) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), digits)


def archive_pattern_context(rows: list[dict]) -> dict[tuple[str, str], dict]:
    context: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.get("field") or "未知 claim", row.get("missing_layer") or "unknown")
        item = context.setdefault(key, {"repositories": set(), "binding_count": 0})
        item["repositories"].add(row.get("repo_full_name") or "")
        item["binding_count"] += 1
    return {
        key: {
            "repository_count": len({repo for repo in value["repositories"] if repo}),
            "binding_count": value["binding_count"],
        }
        for key, value in context.items()
    }


def archive_binding_history_context(conn: sqlite3.Connection) -> dict[tuple[str, str, str], dict]:
    rows = conn.execute(
        """
        SELECT b.repo_full_name, b.field, b.missing_layer, b.evidence_id, b.evidence_stable_id,
               b.binding_confidence_score, r.id AS run_id, r.created_at
        FROM evidence_acquisition_bindings b
        JOIN runs r ON r.id = b.run_id
        WHERE r.mode = 'deep'
        ORDER BY b.repo_full_name, b.field, b.missing_layer, r.created_at, r.id
        """
    ).fetchall()
    grouped: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (row["repo_full_name"], row["field"] or "未知 claim", row["missing_layer"] or "unknown")
        grouped.setdefault(key, []).append(row)

    context: dict[tuple[str, str, str], dict] = {}
    for key, group in grouped.items():
        run_ids = {row["run_id"] for row in group}
        stable_refs = {
            row["evidence_stable_id"] or row["evidence_id"]
            for row in group
            if row["evidence_stable_id"] or row["evidence_id"]
        }
        created_values = [row["created_at"] for row in group if row["created_at"]]
        parsed_dates = []
        for value in created_values:
            try:
                parsed_dates.append(parse_iso_datetime(value))
            except ValueError:
                continue
        history_days = 0.0
        if len(parsed_dates) >= 2:
            history_days = max((max(parsed_dates) - min(parsed_dates)).total_seconds() / 86400, 0.0)
        scores = []
        for row in group:
            try:
                scores.append(int(float(row["binding_confidence_score"])))
            except (TypeError, ValueError):
                continue
        context[key] = {
            "run_count": len(run_ids),
            "binding_count": len(group),
            "evidence_ref_count": len(stable_refs),
            "history_days": round(history_days, 1),
            "first_seen_at": min(created_values) if created_values else None,
            "last_seen_at": max(created_values) if created_values else None,
            "score_range": (max(scores) - min(scores)) if scores else None,
        }
    return context


def archive_health_activity_score(health: dict) -> float:
    return (
        float(health.get("merged_prs_180d") or 0)
        + float(health.get("closed_issues_180d") or 0) * 0.6
        + float(health.get("open_prs") or 0) * 0.2
        + float(health.get("release_count_365d_sample") or 0) * 15
    )


def archive_repository_time_series_context(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT s.full_name, s.stars, s.track_score, r.id AS run_id, r.created_at, h.health_json
        FROM repository_snapshots s
        JOIN runs r ON r.id = s.run_id
        LEFT JOIN repository_health_snapshots h
          ON h.run_id = s.run_id AND h.full_name = s.full_name
        WHERE r.mode = 'deep'
        ORDER BY s.full_name, r.created_at, r.id
        """
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["full_name"], []).append(row)

    context: dict[str, dict] = {}
    for full_name, group in grouped.items():
        created_values = [row["created_at"] for row in group if row["created_at"]]
        parsed_dates = []
        for value in created_values:
            try:
                parsed_dates.append(parse_iso_datetime(value))
            except ValueError:
                continue
        history_days = 0.0
        if len(parsed_dates) >= 2:
            history_days = max((max(parsed_dates) - min(parsed_dates)).total_seconds() / 86400, 0.0)

        latest = group[-1]
        previous = group[-2] if len(group) >= 2 else None
        latest_health = safe_json_loads(latest["health_json"], {}) if latest["health_json"] else {}
        previous_health = safe_json_loads(previous["health_json"], {}) if previous and previous["health_json"] else {}
        latest_activity = archive_health_activity_score(latest_health)
        previous_activity = archive_health_activity_score(previous_health) if previous_health else None
        activity_trend = "single_snapshot"
        if previous_activity is not None:
            if latest_activity >= previous_activity * 1.1:
                activity_trend = "rising_or_sustained"
            elif latest_activity <= previous_activity * 0.55 and previous_activity >= 20:
                activity_trend = "declining"
            else:
                activity_trend = "stable"

        latest_releases = latest_health.get("release_count_365d_sample")
        previous_releases = previous_health.get("release_count_365d_sample") if previous_health else None
        release_trend = "unknown"
        if isinstance(latest_releases, int):
            if latest_releases > 0 and (previous_releases is None or latest_releases >= previous_releases):
                release_trend = "stable_or_rising"
            elif latest_releases == 0:
                release_trend = "missing"
            else:
                release_trend = "declining"

        context[full_name] = {
            "snapshot_count": len(group),
            "history_days": round(history_days, 1),
            "first_seen_at": min(created_values) if created_values else None,
            "last_seen_at": max(created_values) if created_values else None,
            "latest_activity_score": round(latest_activity, 1),
            "previous_activity_score": round(previous_activity, 1) if previous_activity is not None else None,
            "activity_trend": activity_trend,
            "latest_merged_prs_180d": latest_health.get("merged_prs_180d"),
            "latest_closed_issues_180d": latest_health.get("closed_issues_180d"),
            "latest_release_count_365d_sample": latest_releases,
            "previous_release_count_365d_sample": previous_releases,
            "release_trend": release_trend,
            "track_score_delta": (
                round(float(latest["track_score"] or 0) - float(previous["track_score"] or 0), 1)
                if previous
                else None
            ),
            "star_delta": (
                int((latest["stars"] or 0) - (previous["stars"] or 0))
                if previous
                else None
            ),
        }
    return context


def auto_confidence_repetition_score(repo_count: int, binding_count: int) -> float:
    return min(
        repo_count * AUTO_CONFIDENCE_SCORING["repeat_repo_weight"]
        + binding_count * AUTO_CONFIDENCE_SCORING["repeat_binding_weight"],
        AUTO_CONFIDENCE_SCORING["repeat_max"],
    )


def auto_confidence_heuristic_component(heuristic_score: int | float) -> float:
    return min(
        max(
            (float(heuristic_score) - AUTO_CONFIDENCE_SCORING["heuristic_floor"])
            * AUTO_CONFIDENCE_SCORING["heuristic_scale"],
            0,
        ),
        AUTO_CONFIDENCE_SCORING["heuristic_max"],
    )


def auto_confidence_score_parts(row: dict, context: dict, heuristic_score: int, heuristic: dict) -> tuple[int, list[str], dict]:
    signals: list[str] = [AUTO_CONFIDENCE_CALIBRATION]
    repo_count = context.get("repository_count", 0)
    binding_count = context.get("binding_count", 0)
    components = {
        "base": float(AUTO_CONFIDENCE_SCORING["base"]),
        "heuristic_component": round(auto_confidence_heuristic_component(heuristic_score), 2),
        "repetition_component": round(auto_confidence_repetition_score(repo_count, binding_count), 2),
        "time_series_component": 0.0,
        "evidence_quality_component": 0.0,
        "penalty_component": 0.0,
    }

    repo_thresholds = AUTO_CONFIDENCE_REPEAT_THRESHOLDS["cross_project_repositories"]
    binding_thresholds = AUTO_CONFIDENCE_REPEAT_THRESHOLDS["repeated_bindings"]

    if repo_count >= repo_thresholds[0]:
        signals.append(f"cross_project_repeated:{repo_count}")
    elif repo_count >= repo_thresholds[1]:
        signals.append(f"cross_project_repeated:{repo_count}")
    elif repo_count >= repo_thresholds[2]:
        signals.append(f"cross_project_repeated:{repo_count}")

    if binding_count >= binding_thresholds[0]:
        signals.append(f"repeated_binding:{binding_count}")
    elif binding_count >= binding_thresholds[1]:
        signals.append(f"repeated_binding:{binding_count}")

    binding_history = context.get("binding_history") or {}
    history_run_count = binding_history.get("run_count") or 0
    if history_run_count >= 3:
        components["time_series_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["cross_version_binding_3plus"]
        signals.append(f"cross_version_binding_stable:{history_run_count}")
    elif history_run_count >= 2:
        components["time_series_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["cross_version_binding_2plus"]
        signals.append(f"cross_version_binding_stable:{history_run_count}")
    evidence_ref_count = binding_history.get("evidence_ref_count") or 0
    if history_run_count >= 2 and evidence_ref_count > 1:
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["cross_version_evidence_drift"]
        signals.append(f"cross_version_evidence_drift:{evidence_ref_count}")

    repo_time_series = context.get("repository_time_series") or {}
    snapshot_count = repo_time_series.get("snapshot_count") or 0
    if snapshot_count >= 3 and (repo_time_series.get("history_days") or 0) >= 7:
        components["time_series_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["repo_history_3plus"]
        signals.append(f"repo_history:{snapshot_count}")
    activity_trend = repo_time_series.get("activity_trend")
    if activity_trend in {"rising_or_sustained", "stable"} and (repo_time_series.get("latest_activity_score") or 0) >= 20:
        components["time_series_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["repo_activity_sustained"]
        signals.append(f"repo_activity:{activity_trend}")
    elif activity_trend == "declining":
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["repo_activity_declining"]
        signals.append("repo_activity:declining")
    release_trend = repo_time_series.get("release_trend")
    if release_trend == "stable_or_rising":
        components["time_series_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["release_cadence_stable"]
        signals.append("release_cadence:stable_or_rising")
    elif release_trend == "missing" and snapshot_count >= 2:
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["release_cadence_missing"]
        signals.append("release_cadence:missing")

    evidence_type = row.get("evidence_type") or "general"
    if evidence_type in {"source_entrypoint", "test_surface", "benchmark"}:
        components["evidence_quality_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["source_or_validation_evidence"]
        signals.append(f"source_or_validation_evidence:{evidence_type}")
    elif evidence_type in {"configuration", "release_delta", "implementation_change"}:
        components["evidence_quality_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["configuration_or_release_evidence"]
        signals.append(f"engineering_trace_evidence:{evidence_type}")
    elif evidence_type == "general":
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["generic_evidence"]
        signals.append("generic_evidence")

    polarity = row.get("polarity") or "supporting"
    if polarity in {"negative", "boundary"}:
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["negative_or_boundary_polarity"]
        signals.append(f"boundary_polarity:{polarity}")

    if row.get("evidence_url"):
        components["evidence_quality_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["stable_artifact_url"]
        signals.append("stable_artifact_url")

    normalized_signals = {
        normalized_binding_signal(str(signal))
        for signal in heuristic.get("signals") or []
        if str(signal) != "heuristic_v1"
    }
    if "keyword_hits" not in normalized_signals:
        components["penalty_component"] += AUTO_CONFIDENCE_ARCHIVE_WEIGHTS["keyword_sparse"]
        signals.append("keyword_sparse")

    raw_score = sum(components.values())
    components = {key: round(value, 2) for key, value in components.items()}
    components["raw_score"] = round(raw_score, 2)
    score = int(clamp(round(raw_score), 0, 100))
    components["score"] = score
    return score, signals, components


def auto_confidence_for_row(row: dict, context: dict) -> dict:
    current = row.get("binding_confidence") or {}
    heuristic = current.get("heuristic") or current
    heuristic_signals = heuristic.get("signals") or []
    if not heuristic.get("signal_breakdown"):
        heuristic = {
            **heuristic,
            "signal_breakdown": confidence_signal_breakdown(heuristic_signals),
        }
    heuristic_score = heuristic.get("score")
    if not isinstance(heuristic_score, (int, float)):
        heuristic_score = 50
    score, signals, score_components = auto_confidence_score_parts(row, context, int(heuristic_score), heuristic)
    return {
        "score": score,
        "label": auto_confidence_label(score),
        "calibration": AUTO_CONFIDENCE_CALIBRATION,
        "signals": signals,
        "signal_breakdown": confidence_signal_breakdown(signals),
        "source": "auto",
        "heuristic": heuristic,
        "score_delta": score - int(heuristic_score),
        "score_components": score_components,
        "pattern_context": {
            "repository_count": context.get("repository_count", 0),
            "binding_count": context.get("binding_count", 0),
        },
        "binding_history_context": context.get("binding_history") or {},
        "repository_time_series_context": context.get("repository_time_series") or {},
    }


def apply_archive_auto_calibration(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    rows = query_archive_pattern_bindings(
        conn,
        track=args.archive_track,
        min_track_score=args.min_track_score,
    )
    context_by_key = archive_pattern_context(rows)
    binding_history_by_key = archive_binding_history_context(conn)
    repository_time_series_by_name = archive_repository_time_series_context(conn)
    updated: list[dict] = []
    now = utc_now().isoformat()
    for row in rows:
        key = (row.get("field") or "未知 claim", row.get("missing_layer") or "unknown")
        history_key = (row.get("repo_full_name") or "", row.get("field") or "未知 claim", row.get("missing_layer") or "unknown")
        combined_context = {
            **context_by_key.get(key, {}),
            "binding_history": binding_history_by_key.get(history_key, {}),
            "repository_time_series": repository_time_series_by_name.get(row.get("repo_full_name") or "", {}),
        }
        auto_confidence = auto_confidence_for_row(row, combined_context)
        cursor = conn.execute(
            """
            UPDATE evidence_acquisition_bindings
            SET auto_confidence_score = ?,
                auto_confidence_label = ?,
                auto_calibration = ?,
                auto_confidence_signals_json = ?,
                auto_calibrated_at = ?
            WHERE run_id = ? AND repo_full_name = ? AND evidence_id = ? AND field = ? AND missing_layer = ?
            """,
            (
                auto_confidence["score"],
                auto_confidence["label"],
                auto_confidence["calibration"],
                json.dumps(auto_confidence["signals"], ensure_ascii=False),
                now,
                row["run_id"],
                row["repo_full_name"],
                row["evidence_id"],
                row["field"],
                row["missing_layer"],
            ),
        )
        if cursor.rowcount:
            updated.append(
                {
                    "repo_full_name": row.get("repo_full_name"),
                    "run_id": row.get("run_id"),
                    "field": row.get("field"),
                    "missing_layer": row.get("missing_layer"),
                    "missing_layer_label": row.get("missing_layer_label"),
                    "evidence_id": row.get("evidence_id"),
                    "evidence_stable_id": row.get("evidence_stable_id"),
                    "heuristic_score": (auto_confidence.get("heuristic") or {}).get("score"),
                    "auto_score": auto_confidence.get("score"),
                    "auto_label": auto_confidence.get("label"),
                    "score_delta": auto_confidence.get("score_delta"),
                    "score_components": auto_confidence.get("score_components") or {},
                    "signals": auto_confidence.get("signals") or [],
                    "pattern_context": auto_confidence.get("pattern_context") or {},
                    "binding_history_context": auto_confidence.get("binding_history_context") or {},
                    "repository_time_series_context": auto_confidence.get("repository_time_series_context") or {},
                }
            )

    conn.execute("DELETE FROM archive_search_meta WHERE id = 1")
    index_status = rebuild_archive_search_index(conn)
    scores = [item["auto_score"] for item in updated if isinstance(item.get("auto_score"), (int, float))]
    deltas = [item["score_delta"] for item in updated if isinstance(item.get("score_delta"), (int, float))]
    source_counts = {"auto": len(updated)} if updated else {}
    label_counts: dict[str, int] = {}
    for item in updated:
        count_value(label_counts, item.get("auto_label"))
    return {
        "schema_version": 1,
        "mode": "archive_auto_calibrate",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "filters": archive_filters_payload(args),
        "scope": "latest_deep_dossiers",
        "weights": {
            "heuristic_v1": binding_confidence_weight_snapshot(),
            AUTO_CONFIDENCE_CALIBRATION: auto_confidence_scoring_snapshot(),
        },
        "statistics": {
            "candidate_bindings": len(rows),
            "updated_bindings": len(updated),
            "repositories": len({item.get("repo_full_name") for item in updated if item.get("repo_full_name")}),
            "mean_auto_confidence": mean_number(scores),
            "mean_score_delta": mean_number(deltas),
            "minimum_auto_confidence": min(scores) if scores else None,
            "maximum_auto_confidence": max(scores) if scores else None,
            "auto_confidence_labels": top_count_items(label_counts),
            "confidence_sources": top_count_items(source_counts),
            "cross_version_stable_bindings": sum(
                1 for item in updated if any(str(signal).startswith("cross_version_binding_stable:") for signal in item.get("signals") or [])
            ),
            "time_series_context_repositories": len(
                {item.get("repo_full_name") for item in updated if (item.get("repository_time_series_context") or {}).get("snapshot_count", 0) >= 2}
            ),
        },
        "updated": sorted(updated, key=lambda item: (-(abs(item.get("score_delta") or 0)), item.get("repo_full_name") or ""))[: max(args.limit, 1)],
        "search_index": index_status,
    }


def build_archive_acquisition_patterns(rows: list[dict], limit: int) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    for row in rows:
        field = row.get("field") or "未知 claim"
        layer = row.get("missing_layer") or "unknown"
        key = (field, layer)
        pattern = groups.setdefault(
            key,
            {
                "pattern_id": stable_id("pattern", field, layer),
                "field": field,
                "missing_layer": layer,
                "missing_layer_label": row.get("missing_layer_label") or SUPPORT_LAYER_LABELS.get(layer, layer),
                "binding_count": 0,
                "_repositories": set(),
                "_track_counts": {},
                "_evidence_type_counts": {},
                "_evidence_kind_counts": {},
                "_keyword_counts": {},
                "_reason_counts": {},
                "_confidence_scores": [],
                "_confidence_label_counts": {},
                "_confidence_source_counts": {},
                "_signal_group_counts": {},
                "_signal_label_counts": {},
                "_signal_group_scores": [],
                "examples": [],
            },
        )
        pattern["binding_count"] += 1
        pattern["_repositories"].add(row.get("repo_full_name") or "")
        count_value(pattern["_track_counts"], row.get("track"))
        count_value(pattern["_evidence_type_counts"], row.get("evidence_type"))
        count_value(pattern["_evidence_kind_counts"], row.get("evidence_kind"))
        count_value(pattern["_reason_counts"], row.get("reason"))
        confidence = row.get("binding_confidence") or {}
        if isinstance(confidence.get("score"), (int, float)):
            pattern["_confidence_scores"].append(confidence["score"])
        count_value(pattern["_confidence_label_counts"], confidence.get("label"))
        count_value(pattern["_confidence_source_counts"], confidence.get("source") or "heuristic")
        pattern["_signal_group_scores"].append(confidence_signal_group_score(confidence))
        for group in confidence_signal_group_names(confidence):
            count_value(pattern["_signal_group_counts"], group)
        for label in confidence_signal_labels(confidence):
            count_value(pattern["_signal_label_counts"], label)
        for keyword in row.get("keywords") or []:
            count_value(pattern["_keyword_counts"], keyword)

        if len(pattern["examples"]) < 6:
            pattern["examples"].append(
                {
                    "repo_full_name": row.get("repo_full_name"),
                    "run_id": row.get("run_id"),
                    "run_created_at": row.get("run_created_at"),
                    "track": row.get("track"),
                    "track_score": row.get("track_score"),
                    "claim_id": row.get("claim_id"),
                    "evidence_id": row.get("evidence_id"),
                    "evidence_stable_id": row.get("evidence_stable_id"),
                    "evidence_kind": row.get("evidence_kind"),
                    "evidence_title": row.get("evidence_title"),
                    "evidence_url": row.get("evidence_url"),
                    "evidence_type": row.get("evidence_type"),
                    "polarity": row.get("polarity"),
                    "keywords": row.get("keywords") or [],
                    "reason": row.get("reason"),
                    "binding_confidence": row.get("binding_confidence") or {},
                    "quote": excerpt(row.get("evidence_quote") or "", 220),
                }
            )

    patterns = []
    for pattern in groups.values():
        repositories = sorted(repo for repo in pattern.pop("_repositories") if repo)
        confidence_scores = pattern.pop("_confidence_scores")
        average_confidence = (
            round(sum(confidence_scores) / len(confidence_scores), 1)
            if confidence_scores
            else None
        )
        repo_count = len(repositories)
        binding_count = pattern["binding_count"]
        signal_group_scores = pattern.pop("_signal_group_scores")
        signal_group_score = mean_number(signal_group_scores) or 0
        repeat_score = min(48, repo_count * 14 + binding_count * 4)
        confidence_score = min(22, round((average_confidence or 0) * 0.22))
        pattern.update(
            {
                "repository_count": repo_count,
                "repositories": repositories[:12],
                "repeat_status": "cross_project" if repo_count >= 2 else "single_project",
                "repeat_score": repeat_score,
                "confidence_score": confidence_score,
                "signal_group_score": signal_group_score,
                "pattern_score": min(100, int(round(repeat_score + confidence_score + signal_group_score))),
                "average_binding_confidence": average_confidence,
                "minimum_binding_confidence": min(confidence_scores) if confidence_scores else None,
                "reliability_status": binding_confidence_label(average_confidence or 0),
                "confidence_labels": top_count_items(pattern.pop("_confidence_label_counts")),
                "confidence_sources": top_count_items(pattern.pop("_confidence_source_counts")),
                "signal_groups": top_count_items(pattern.pop("_signal_group_counts")),
                "signal_labels": top_count_items(pattern.pop("_signal_label_counts"), limit=10),
                "tracks": top_count_items(pattern.pop("_track_counts")),
                "evidence_types": top_count_items(pattern.pop("_evidence_type_counts")),
                "evidence_kinds": top_count_items(pattern.pop("_evidence_kind_counts")),
                "keywords": top_count_items(pattern.pop("_keyword_counts"), limit=10),
                "reasons": top_count_items(pattern.pop("_reason_counts"), limit=3),
            }
        )
        patterns.append(pattern)

    patterns.sort(
        key=lambda item: (
            -item["pattern_score"],
            -(item.get("signal_group_score") or 0),
            -(item.get("average_binding_confidence") or 0),
            -item["repository_count"],
            -item["binding_count"],
            item["field"],
            item["missing_layer"],
        )
    )
    return patterns[: max(limit, 1)]


def cognition_field_profile(field: str | None) -> dict:
    return COGNITION_FIELD_PROFILES.get(field or "", DEFAULT_COGNITION_FIELD_PROFILE)


def cognition_summary_score(patterns: list[dict], repo_count: int, binding_count: int) -> int:
    pattern_scores = [
        item.get("pattern_score")
        for item in patterns
        if isinstance(item.get("pattern_score"), (int, float))
    ]
    confidence_scores = [
        item.get("average_binding_confidence")
        for item in patterns
        if isinstance(item.get("average_binding_confidence"), (int, float))
    ]
    signal_scores = [
        item.get("signal_group_score")
        for item in patterns
        if isinstance(item.get("signal_group_score"), (int, float))
    ]
    pattern_part = (mean_number(pattern_scores) or 0) * 0.36
    confidence_part = (mean_number(confidence_scores) or 0) * 0.20
    signal_part = (mean_number(signal_scores) or 0) * 0.85
    repeat_part = min(repo_count * 4 + binding_count * 1.0, 22)
    return int(clamp(round(pattern_part + confidence_part + signal_part + repeat_part), 0, 100))


def cognition_summary_confidence(score: int, repo_count: int) -> str:
    if score >= 78 and repo_count >= 3:
        return "high"
    if score >= 58 and repo_count >= 2:
        return "medium"
    return "low"


def build_archive_cognition_summaries(patterns: list[dict], limit: int) -> list[dict]:
    groups: dict[str, dict] = {}
    for pattern in patterns:
        profile = cognition_field_profile(pattern.get("field"))
        category = profile["category"]
        group = groups.setdefault(
            category,
            {
                "summary_id": stable_id("cognition", category),
                "category": category,
                "label": profile["label"],
                "move": profile["move"],
                "transfer_rule": profile["transfer_rule"],
                "_patterns": [],
                "_repositories": set(),
                "_layer_counts": {},
                "_layer_action_counts": {},
                "_signal_group_counts": {},
                "_signal_label_counts": {},
                "_confidence_scores": [],
                "_pattern_scores": [],
                "_signal_scores": [],
                "_binding_count": 0,
            },
        )
        group["_patterns"].append(pattern)
        group["_binding_count"] += int(pattern.get("binding_count") or 0)
        for repo in pattern.get("repositories") or []:
            group["_repositories"].add(repo)
        missing_layer = pattern.get("missing_layer")
        missing_layer_label = (
            pattern.get("missing_layer_label")
            or SUPPORT_LAYER_LABELS.get(missing_layer, missing_layer)
        )
        count_value(
            group["_layer_counts"],
            missing_layer_label,
        )
        count_value(
            group["_layer_action_counts"],
            COGNITION_LAYER_ACTIONS.get(missing_layer, missing_layer_label),
        )
        for item in pattern.get("signal_groups") or []:
            value = item.get("value")
            if value:
                group["_signal_group_counts"][value] = group["_signal_group_counts"].get(value, 0) + int(item.get("count") or 0)
        for item in pattern.get("signal_labels") or []:
            value = item.get("value")
            if value:
                group["_signal_label_counts"][value] = group["_signal_label_counts"].get(value, 0) + int(item.get("count") or 0)
        if isinstance(pattern.get("average_binding_confidence"), (int, float)):
            group["_confidence_scores"].append(pattern["average_binding_confidence"])
        if isinstance(pattern.get("pattern_score"), (int, float)):
            group["_pattern_scores"].append(pattern["pattern_score"])
        if isinstance(pattern.get("signal_group_score"), (int, float)):
            group["_signal_scores"].append(pattern["signal_group_score"])

    summaries = []
    for group in groups.values():
        patterns_for_group = sorted(
            group.pop("_patterns"),
            key=lambda item: (
                -(item.get("pattern_score") or 0),
                -(item.get("signal_group_score") or 0),
                -(item.get("repository_count") or 0),
                item.get("field") or "",
                item.get("missing_layer") or "",
            ),
        )
        repositories = sorted(repo for repo in group.pop("_repositories") if repo)
        layer_counts = top_count_items(group.pop("_layer_counts"), limit=5)
        layer_actions = top_count_items(group.pop("_layer_action_counts"), limit=5)
        signal_groups = top_count_items(group.pop("_signal_group_counts"), limit=6)
        signal_labels = top_count_items(group.pop("_signal_label_counts"), limit=8)
        confidence_scores = group.pop("_confidence_scores")
        pattern_scores = group.pop("_pattern_scores")
        signal_scores = group.pop("_signal_scores")
        binding_count = group.pop("_binding_count")
        score = cognition_summary_score(patterns_for_group, len(repositories), binding_count)
        top_layers = "、".join(item["value"] for item in layer_counts[:3]) or "归档证据"
        top_actions = "；".join(item["value"] for item in layer_actions[:3]) or "用 archive evidence 复核高层判断"
        top_signals = "、".join(item["value"] for item in signal_groups[:3]) or "archive signals"
        top_fields = unique_ordered([item.get("field") or "" for item in patterns_for_group if item.get("field")])[:4]
        field_text = "、".join(top_fields) or group["label"]
        summaries.append(
            {
                **group,
                "score": score,
                "confidence": cognition_summary_confidence(score, len(repositories)),
                "repository_count": len(repositories),
                "repositories": repositories[:12],
                "pattern_count": len(patterns_for_group),
                "binding_count": binding_count,
                "average_pattern_score": mean_number(pattern_scores),
                "average_binding_confidence": mean_number(confidence_scores),
                "average_signal_group_score": mean_number(signal_scores),
                "layer_counts": layer_counts,
                "layer_actions": layer_actions,
                "signal_groups": signal_groups,
                "signal_labels": signal_labels,
                "summary": (
                    f"{field_text} 在 {len(repositories)} 个仓库中反复需要 {top_layers} 证据补强；"
                    f"可观察工程动作是：{group['move']}；复核路径是：{top_actions}。"
                ),
                "evidence_basis": (
                    f"{len(patterns_for_group)} 个 patterns、{binding_count} 条 bindings、"
                    f"平均 pattern score {mean_number(pattern_scores) if pattern_scores else 'unknown'}、"
                    f"平均 binding confidence {mean_number(confidence_scores) if confidence_scores else 'unknown'}、"
                    f"主要自动信号 {top_signals}。"
                ),
                "supporting_patterns": [
                    {
                        "pattern_id": item.get("pattern_id"),
                        "field": item.get("field"),
                        "missing_layer": item.get("missing_layer"),
                        "missing_layer_label": item.get("missing_layer_label"),
                        "pattern_score": item.get("pattern_score"),
                        "signal_group_score": item.get("signal_group_score"),
                        "average_binding_confidence": item.get("average_binding_confidence"),
                        "repository_count": item.get("repository_count"),
                        "binding_count": item.get("binding_count"),
                        "repositories": item.get("repositories") or [],
                        "signal_groups": item.get("signal_groups") or [],
                        "missing_layer_action": COGNITION_LAYER_ACTIONS.get(item.get("missing_layer")),
                    }
                    for item in patterns_for_group[:5]
                ],
            }
        )

    summaries.sort(
        key=lambda item: (
            -item["score"],
            -item["repository_count"],
            -item["binding_count"],
            item["category"],
        )
    )
    return summaries[: max(limit, 1)]


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
        "signal_group": getattr(args, "archive_signal_group", None),
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
    index_status = rebuild_archive_search_index(conn)
    return {
        "schema_version": 1,
        "mode": "archive_search",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "query": query,
        "filters": archive_filters_payload(args),
        "search_index": index_status,
        "matches": query_archive_search(
            conn,
            query,
            args.limit,
            track=args.archive_track,
            min_track_score=args.min_track_score,
            index_status=index_status,
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


def archive_patterns_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    signal_group = getattr(args, "archive_signal_group", None)
    rows = query_archive_pattern_bindings(
        conn,
        track=args.archive_track,
        min_track_score=args.min_track_score,
    )
    rows = filter_archive_pattern_rows_by_signal_group(rows, signal_group)
    patterns = build_archive_acquisition_patterns(rows, args.limit)
    cognition_summaries = build_archive_cognition_summaries(patterns, args.limit)
    repositories = sorted({row.get("repo_full_name") for row in rows if row.get("repo_full_name")})
    pattern_confidences = [
        item.get("average_binding_confidence")
        for item in patterns
        if isinstance(item.get("average_binding_confidence"), (int, float))
    ]
    return {
        "schema_version": 1,
        "mode": "archive_patterns",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "filters": archive_filters_payload(args),
        "scope": "latest_deep_dossiers",
        "statistics": {
            "bindings": len(rows),
            "patterns": len(patterns),
            "cognition_summaries": len(cognition_summaries),
            "high_confidence_cognition_summaries": sum(1 for item in cognition_summaries if item.get("confidence") == "high"),
            "repositories": len(repositories),
            "cross_project_patterns": sum(1 for item in patterns if item.get("repository_count", 0) >= 2),
            "average_pattern_confidence": round(sum(pattern_confidences) / len(pattern_confidences), 1) if pattern_confidences else None,
            "average_pattern_signal_score": mean_number(
                [item.get("signal_group_score") for item in patterns if isinstance(item.get("signal_group_score"), (int, float))]
            ),
            "signal_groups": aggregate_pattern_count_items(patterns, "signal_groups"),
        },
        "cognition_summaries": cognition_summaries,
        "patterns": patterns,
    }


def archive_dashboard_payload(conn: sqlite3.Connection, args: argparse.Namespace) -> dict:
    signal_group = getattr(args, "archive_signal_group", None)
    index_status = rebuild_archive_search_index(conn)
    pattern_rows = query_archive_pattern_bindings(
        conn,
        track=args.archive_track,
        min_track_score=args.min_track_score,
    )
    pattern_rows = filter_archive_pattern_rows_by_signal_group(pattern_rows, signal_group)
    signal_group_repositories = {row.get("repo_full_name") for row in pattern_rows if row.get("repo_full_name")}
    repositories = query_latest_archive_snapshots(
        conn,
        args.limit,
        track=args.archive_track,
        min_track_score=args.min_track_score,
    )
    if signal_group:
        repositories = [summary for summary in repositories if summary.get("full_name") in signal_group_repositories]
    dossiers = {}
    for summary in repositories:
        dossier = query_archive_show(conn, summary["full_name"]) or {}
        dossiers[summary["full_name"]] = {
            "claims": dossier.get("claims") or [],
            "claim_gap_report": dossier.get("claim_gap_report") or [],
            "evidence_acquisition": dossier.get("evidence_acquisition") or {},
            "evidence": dossier.get("evidence") or [],
            "dossier_run_id": ((dossier.get("repository") or {}).get("run_id")),
            "dossier_run_created_at": ((dossier.get("repository") or {}).get("run_created_at")),
            "dossier_run_mode": ((dossier.get("repository") or {}).get("run_mode")),
        }

    patterns = build_archive_acquisition_patterns(pattern_rows, args.limit)
    cognition_summaries = build_archive_cognition_summaries(patterns, args.limit)
    scores = [
        (summary.get("track_score") or {}).get("score")
        for summary in repositories
        if isinstance((summary.get("track_score") or {}).get("score"), (int, float))
    ]
    pattern_confidences = [
        item.get("average_binding_confidence")
        for item in patterns
        if isinstance(item.get("average_binding_confidence"), (int, float))
    ]
    tracks: dict[str, int] = {}
    for summary in repositories:
        track = (summary.get("track_score") or {}).get("track") or "unknown"
        tracks[track] = tracks.get(track, 0) + 1
    confidence_sources: dict[str, int] = {}
    for row in pattern_rows:
        confidence = row.get("binding_confidence") or {}
        count_value(confidence_sources, confidence.get("source") or "heuristic")

    return {
        "schema_version": 1,
        "mode": "archive_dashboard",
        "generated_at": utc_now().isoformat(),
        "db": args.db,
        "filters": archive_filters_payload(args),
        "search_index": index_status,
        "statistics": {
            "repositories": len(repositories),
            "deep_dossiers": sum(1 for item in dossiers.values() if item["claims"] or item["evidence"]),
            "claims": sum(len(item["claims"]) for item in dossiers.values()),
            "claim_gaps": sum(len(item["claim_gap_report"]) for item in dossiers.values()),
            "acquisition_bindings": sum((item.get("evidence_acquisition") or {}).get("binding_count", 0) for item in dossiers.values()),
            "evidence": sum(len(item["evidence"]) for item in dossiers.values()),
            "acquisition_patterns": len(patterns),
            "cognition_summaries": len(cognition_summaries),
            "high_confidence_cognition_summaries": sum(1 for item in cognition_summaries if item.get("confidence") == "high"),
            "cross_project_patterns": sum(1 for item in patterns if item.get("repository_count", 0) >= 2),
            "average_pattern_confidence": round(sum(pattern_confidences) / len(pattern_confidences), 1) if pattern_confidences else None,
            "average_pattern_signal_score": mean_number(
                [item.get("signal_group_score") for item in patterns if isinstance(item.get("signal_group_score"), (int, float))]
            ),
            "signal_groups": aggregate_pattern_count_items(patterns, "signal_groups"),
            "average_track_score": round(sum(scores) / len(scores), 1) if scores else None,
            "confidence_sources": top_count_items(confidence_sources),
            "tracks": tracks,
        },
        "repositories": repositories,
        "dossiers": dossiers,
        "cognition_summaries": cognition_summaries,
        "patterns": patterns,
    }


def render_archive_dashboard(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSS Cognition Radar</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #151a1f;
      --muted: #65717f;
      --line: #d8dee6;
      --teal: #006b5b;
      --teal-soft: #dcefeb;
      --blue: #3451b2;
      --amber: #b66a00;
      --red: #b42318;
      --green: #1d6f42;
      --shadow: 0 1px 2px rgba(16, 24, 40, .08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    a { color: var(--blue); text-decoration: none; }
    a:hover { text-decoration: underline; }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto auto 1fr;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 24px 12px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }

    h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      font-weight: 700;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
      overflow-wrap: anywhere;
    }

    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) 150px 160px 170px 220px 92px;
      gap: 10px;
      padding: 12px 24px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }

    input, select, button {
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }

    input, select { padding: 0 10px; min-width: 0; }

    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-weight: 600;
    }

    button:hover { border-color: var(--teal); color: var(--teal); }

    .range {
      display: grid;
      grid-template-columns: 1fr 44px;
      align-items: center;
      gap: 8px;
      height: 36px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }

    .range input {
      height: auto;
      padding: 0;
      border: 0;
      accent-color: var(--teal);
    }

    .range output {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 10px;
      padding: 14px 24px 0;
    }

    .stat {
      min-height: 70px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .stat-label {
      color: var(--muted);
      font-size: 12px;
    }

    .stat-value {
      margin-top: 4px;
      font-size: 24px;
      font-weight: 700;
    }

    .patterns-panel {
      padding: 14px 24px 0;
    }

    .patterns-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }

    .patterns-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .pattern-card {
      min-height: 138px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      box-shadow: var(--shadow);
    }

    .pattern-card h2 {
      margin: 0 0 8px;
      font-size: 14px;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }

    .pattern-card p {
      margin: 8px 0;
      color: #2d3640;
      overflow-wrap: anywhere;
    }

    main {
      display: grid;
      grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
      gap: 14px;
      padding: 14px 24px 24px;
      min-height: 0;
    }

    .list, .detail {
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .list-head, .detail-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 48px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }

    .section-title {
      font-size: 14px;
      font-weight: 700;
    }

    .count {
      color: var(--muted);
      font-size: 12px;
    }

    .repo-list {
      max-height: calc(100vh - 250px);
      overflow: auto;
    }

    .repo-row {
      width: 100%;
      height: auto;
      min-height: 104px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      padding: 12px 14px;
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      background: #fff;
      text-align: left;
    }

    .repo-row:hover, .repo-row.active { background: var(--teal-soft); color: var(--ink); }

    .repo-name {
      font-weight: 700;
      overflow-wrap: anywhere;
    }

    .repo-desc {
      min-height: 20px;
      color: var(--muted);
      overflow: hidden;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }

    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      min-height: 22px;
      padding: 2px 7px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }

    .chip.track { color: var(--teal); border-color: #98ccc2; }
    .chip.support { color: var(--teal); border-color: #98ccc2; background: #f3fbf8; }
    .chip.risk-high { color: var(--red); border-color: #f2b8b5; }
    .chip.risk-mid { color: var(--amber); border-color: #e7bd78; }

    .score-line {
      display: grid;
      grid-template-columns: 58px 1fr 42px;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .bar {
      height: 7px;
      border-radius: 999px;
      background: #edf0f3;
      overflow: hidden;
    }

    .bar > span {
      display: block;
      height: 100%;
      width: 0;
      background: linear-gradient(90deg, var(--teal), var(--green));
    }

    .detail-body {
      max-height: calc(100vh - 250px);
      overflow: auto;
      padding: 16px;
    }

    .detail-title {
      margin: 0 0 6px;
      font-size: 22px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }

    .detail-desc {
      margin: 0 0 14px;
      color: var(--muted);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }

    .metric {
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
    }

    .metric b {
      display: block;
      margin-top: 2px;
      font-size: 16px;
    }

    .claims, .gaps, .acquisition, .evidence {
      display: grid;
      gap: 10px;
      margin-top: 16px;
    }

    .item {
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }

    .item h3 {
      margin: 0 0 8px;
      font-size: 14px;
      line-height: 1.3;
    }

    .item p {
      margin: 0;
      color: #2d3640;
      overflow-wrap: anywhere;
    }

    .subtle {
      color: var(--muted);
      font-size: 12px;
    }

    .empty {
      padding: 24px;
      color: var(--muted);
      text-align: center;
    }

    @media (max-width: 980px) {
      .toolbar { grid-template-columns: 1fr 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .patterns-grid { grid-template-columns: 1fr; }
      main { grid-template-columns: 1fr; }
      .repo-list, .detail-body { max-height: none; }
    }

    @media (max-width: 620px) {
      header { align-items: flex-start; flex-direction: column; padding: 14px; }
      .meta { text-align: left; }
      .toolbar { grid-template-columns: 1fr; padding: 10px 14px; }
      .stats { grid-template-columns: 1fr; padding: 10px 14px 0; }
      main { padding: 10px 14px 18px; }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <h1>OSS Cognition Radar</h1>
      <div class="meta">
        <div id="dbMeta"></div>
        <div id="timeMeta"></div>
      </div>
    </header>

    <section class="toolbar" aria-label="Archive filters">
      <input id="searchInput" type="search" placeholder="Search repositories, patterns, claims, gaps, bindings, evidence" autocomplete="off">
      <select id="trackSelect" aria-label="Track"></select>
      <select id="confidenceSourceSelect" aria-label="Confidence source"></select>
      <select id="signalGroupSelect" aria-label="Signal group"></select>
      <label class="range" for="scoreRange">
        <input id="scoreRange" type="range" min="0" max="100" step="1" value="0">
        <output id="scoreOutput">0</output>
      </label>
      <button id="resetButton" type="button">Reset</button>
    </section>

    <section class="stats" id="stats"></section>
    <section class="patterns-panel" id="patternsPanel"></section>

    <main>
      <section class="list">
        <div class="list-head">
          <div class="section-title">Repositories</div>
          <div class="count" id="resultCount"></div>
        </div>
        <div class="repo-list" id="repoList"></div>
      </section>

      <section class="detail">
        <div class="detail-head">
          <div class="section-title">Dossier</div>
          <a id="githubLink" href="#" target="_blank" rel="noreferrer">GitHub</a>
        </div>
        <div class="detail-body" id="detailBody"></div>
      </section>
    </main>
  </div>

  <script>
    const DATA = __DATA__;
    const state = { query: "", track: "all", confidenceSource: "all", signalGroup: DATA.filters?.signal_group || "all", minScore: 0, selected: null };
    const repos = DATA.repositories || [];
    const dossiers = DATA.dossiers || {};
    const cognitionSummaries = DATA.cognition_summaries || [];
    const patterns = DATA.patterns || [];

    const searchInput = document.getElementById("searchInput");
    const trackSelect = document.getElementById("trackSelect");
    const confidenceSourceSelect = document.getElementById("confidenceSourceSelect");
    const signalGroupSelect = document.getElementById("signalGroupSelect");
    const scoreRange = document.getElementById("scoreRange");
    const scoreOutput = document.getElementById("scoreOutput");
    const resetButton = document.getElementById("resetButton");
    const repoList = document.getElementById("repoList");
    const detailBody = document.getElementById("detailBody");
    const resultCount = document.getElementById("resultCount");
    const stats = document.getElementById("stats");
    const patternsPanel = document.getElementById("patternsPanel");
    const githubLink = document.getElementById("githubLink");

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function compact(value, limit = 220) {
      const text = String(value ?? "").replace(/\\s+/g, " ").trim();
      if (text.length <= limit) return text;
      return text.slice(0, Math.max(0, limit - 3)).trimEnd() + "...";
    }

    function trackOf(repo) {
      return repo.track_score?.track || "unknown";
    }

    function scoreOf(repo) {
      const score = repo.track_score?.score;
      return Number.isFinite(score) ? score : 0;
    }

    function confidenceText(confidence) {
      if (!confidence) return "confidence unknown";
      const score = Number.isFinite(Number(confidence.score)) ? confidence.score : "unknown";
      return `${confidence.label || "unknown"} ${score}`;
    }

    function confidenceSource(confidence) {
      return confidence?.source || "heuristic";
    }

    function confidenceSourceText(confidence) {
      const source = confidenceSource(confidence);
      if (source === "auto") return "auto";
      return "heuristic";
    }

    function confidenceClass(confidence) {
      const label = confidence?.label || "";
      if (label === "high") return "support";
      if (label === "low") return "risk-mid";
      return "";
    }

    function confidenceSignalBreakdown(confidence) {
      const breakdown = confidence?.signal_breakdown || [];
      if (breakdown.length) return breakdown;
      const signals = confidence?.signals || [];
      return signals.length
        ? [{ group: "signals", label: "Signals", signals: signals.map((signal) => ({ raw: signal, label: signal })) }]
        : [];
    }

    function confidenceSignalText(confidence, maxGroups = 4, maxSignals = 2) {
      return confidenceSignalBreakdown(confidence).slice(0, maxGroups).map((group) => {
        const signals = group.signals || [];
        const labels = signals.slice(0, maxSignals).map((signal) => signal.label || signal.raw).filter(Boolean);
        if (signals.length > maxSignals) labels.push("+" + (signals.length - maxSignals));
        return labels.length ? `${group.group || "other"}: ${labels.join(", ")}` : "";
      }).filter(Boolean).join(" | ");
    }

    function confidenceSignalChips(confidence, maxGroups = 3, maxSignals = 2) {
      return confidenceSignalBreakdown(confidence).slice(0, maxGroups).map((group) => {
        const signals = group.signals || [];
        const labels = signals.slice(0, maxSignals).map((signal) => signal.label || signal.raw).filter(Boolean);
        if (signals.length > maxSignals) labels.push("+" + (signals.length - maxSignals));
        if (!labels.length) return "";
        return `<span class="chip">${escapeHtml(group.group || "other")}: ${escapeHtml(labels.join(", "))}</span>`;
      }).filter(Boolean).join("");
    }

    function confidenceCorpus(confidence) {
      return [
        confidence?.label,
        confidence?.score,
        confidence?.calibration,
        confidence?.source,
        (confidence?.signals || []).join(" "),
        ...confidenceSignalBreakdown(confidence).flatMap((group) => [
          group.group,
          group.label,
          ...(group.signals || []).flatMap((signal) => [signal.raw, signal.label]),
        ]),
      ].filter(Boolean).join(" ");
    }

    function confidenceHasSignalGroup(confidence, group) {
      if (group === "all") return true;
      return confidenceSignalBreakdown(confidence).some((item) => item.group === group);
    }

    function dossierOf(repo) {
      return dossiers[repo.full_name] || { claims: [], claim_gap_report: [], evidence_acquisition: {}, evidence: [] };
    }

    function bindingMatchesConfidenceSource(binding) {
      return state.confidenceSource === "all" || confidenceSource(binding?.binding_confidence) === state.confidenceSource;
    }

    function bindingMatchesSignalGroup(binding) {
      return confidenceHasSignalGroup(binding?.binding_confidence, state.signalGroup);
    }

    function repoMatchesConfidenceSource(repo) {
      if (state.confidenceSource === "all") return true;
      const dossier = dossierOf(repo);
      const acquisitionBindings = (dossier.evidence_acquisition || {}).bindings || [];
      const evidenceBindings = (dossier.evidence || []).flatMap((item) => item.acquisition_bindings || []);
      return [...acquisitionBindings, ...evidenceBindings].some(bindingMatchesConfidenceSource);
    }

    function repoMatchesSignalGroup(repo) {
      if (state.signalGroup === "all") return true;
      const dossier = dossierOf(repo);
      const acquisitionBindings = (dossier.evidence_acquisition || {}).bindings || [];
      const evidenceBindings = (dossier.evidence || []).flatMap((item) => item.acquisition_bindings || []);
      return [...acquisitionBindings, ...evidenceBindings].some(bindingMatchesSignalGroup);
    }

    function patternMatchesConfidenceSource(pattern) {
      if (state.confidenceSource === "all") return true;
      return (pattern.confidence_sources || []).some((item) => item.value === state.confidenceSource);
    }

    function patternMatchesSignalGroup(pattern) {
      if (state.signalGroup === "all") return true;
      return (pattern.signal_groups || []).some((item) => item.value === state.signalGroup);
    }

    function cognitionSummaryMatchesSignalGroup(summary) {
      if (state.signalGroup === "all") return true;
      return (summary.signal_groups || []).some((item) => item.value === state.signalGroup);
    }

    function cognitionSummaryCorpus(summary) {
      const parts = [
        summary.category,
        summary.label,
        summary.move,
        summary.summary,
        summary.evidence_basis,
        summary.transfer_rule,
        summary.confidence,
        summary.score,
        (summary.repositories || []).join(" "),
        ...(summary.layer_counts || []).map((item) => item.value),
        ...(summary.layer_actions || []).map((item) => item.value),
        ...(summary.signal_groups || []).map((item) => item.value),
        ...(summary.signal_labels || []).map((item) => item.value),
        ...(summary.supporting_patterns || []).flatMap((pattern) => [
          pattern.field,
          pattern.missing_layer,
          pattern.missing_layer_label,
          pattern.pattern_id,
          pattern.pattern_score,
          (pattern.repositories || []).join(" "),
          ...(pattern.signal_groups || []).map((item) => item.value),
        ]),
      ];
      return parts.filter(Boolean).join(" ").toLowerCase();
    }

    function patternCorpus(pattern) {
      const parts = [
        pattern.field,
        pattern.missing_layer,
        pattern.missing_layer_label,
        pattern.repeat_status,
        pattern.reliability_status,
        pattern.pattern_score,
        pattern.signal_group_score,
        pattern.repeat_score,
        pattern.confidence_score,
        (pattern.repositories || []).join(" "),
        ...(pattern.keywords || []).map((item) => item.value),
        ...(pattern.evidence_types || []).map((item) => item.value),
        ...(pattern.evidence_kinds || []).map((item) => item.value),
        ...(pattern.confidence_labels || []).map((item) => item.value),
        ...(pattern.confidence_sources || []).map((item) => item.value),
        ...(pattern.signal_groups || []).map((item) => item.value),
        ...(pattern.signal_labels || []).map((item) => item.value),
        ...(pattern.examples || []).flatMap((item) => [
          item.repo_full_name,
          item.evidence_title,
          item.evidence_type,
          item.reason,
          item.binding_confidence?.label,
          item.binding_confidence?.score,
          item.binding_confidence?.calibration,
          item.binding_confidence?.source,
          (item.binding_confidence?.signals || []).join(" "),
          confidenceCorpus(item.binding_confidence),
        ]),
      ];
      return parts.filter(Boolean).join(" ").toLowerCase();
    }

    function corpusOf(repo) {
      const dossier = dossierOf(repo);
      const parts = [
        repo.full_name,
        repo.description,
        repo.language,
        (repo.topics || []).join(" "),
        ...(dossier.claims || []).flatMap((item) => [
          item.field,
          item.text,
          item.template,
          item.rationale,
          item.support_coverage?.level,
          item.support_coverage?.label,
          item.support_coverage?.summary,
          (item.support_coverage?.layers || []).join(" "),
          (item.support_coverage?.layer_labels || []).join(" "),
        ]),
        ...(dossier.claim_gap_report || []).flatMap((item) => [
          "claim_gap",
          item.field,
          item.support_level,
          item.support_label,
          item.gap_reason,
          item.recommendation,
          (item.missing_layers || []).join(" "),
          (item.missing_layer_labels || []).join(" "),
        ]),
        ...((dossier.evidence_acquisition || {}).bindings || []).flatMap((item) => [
          "acquisition_binding",
          item.field,
          item.claim_id,
          item.evidence_id,
          item.evidence_stable_id,
          item.missing_layer,
          item.missing_layer_label,
          item.binding_confidence?.label,
          item.binding_confidence?.score,
          item.binding_confidence?.calibration,
          item.binding_confidence?.source,
          (item.binding_confidence?.signals || []).join(" "),
          confidenceCorpus(item.binding_confidence),
          (item.keywords || []).join(" "),
          item.reason,
        ]),
        ...(dossier.evidence || []).flatMap((item) => [
          item.kind,
          item.title,
          item.quote,
          item.evidence_type,
          item.polarity,
          (item.signal_tags || []).join(" "),
          ...(item.acquisition_bindings || []).flatMap((binding) => [
            binding.field,
            binding.missing_layer,
            binding.missing_layer_label,
            binding.binding_confidence?.label,
            binding.binding_confidence?.score,
            binding.binding_confidence?.calibration,
            binding.binding_confidence?.source,
            (binding.binding_confidence?.signals || []).join(" "),
            confidenceCorpus(binding.binding_confidence),
            (binding.keywords || []).join(" "),
            binding.reason,
          ]),
        ]),
      ];
      return parts.filter(Boolean).join(" ").toLowerCase();
    }

    function relevanceOf(repo, query) {
      const terms = query.trim().toLowerCase().split(/\\s+/).filter(Boolean);
      if (!terms.length) return 0;
      const dossier = dossierOf(repo);
      const sources = [
        { weight: 8, text: repo.full_name },
        { weight: 5, text: repo.description },
        { weight: 3, text: (repo.topics || []).join(" ") },
        {
          weight: 3,
          text: (dossier.claims || []).map((item) => {
            const support = item.support_coverage || {};
            return `${item.field} ${item.text} ${item.template || ""} ${item.rationale || ""} ${support.level || ""} ${support.label || ""} ${support.summary || ""} ${(support.layers || []).join(" ")} ${(support.layer_labels || []).join(" ")}`;
          }).join(" "),
        },
        {
          weight: 4,
          text: (dossier.claim_gap_report || []).map((item) =>
            `claim_gap ${item.field} ${item.support_level || ""} ${item.support_label || ""} ${item.gap_reason || ""} ${item.recommendation || ""} ${(item.missing_layers || []).join(" ")} ${(item.missing_layer_labels || []).join(" ")}`
          ).join(" "),
        },
        {
          weight: 4,
          text: ((dossier.evidence_acquisition || {}).bindings || []).map((item) =>
            `acquisition_binding ${item.field || ""} ${item.claim_id || ""} ${item.evidence_id || ""} ${item.evidence_stable_id || ""} ${item.missing_layer || ""} ${item.missing_layer_label || ""} ${confidenceCorpus(item.binding_confidence)} ${(item.keywords || []).join(" ")} ${item.reason || ""}`
          ).join(" "),
        },
        {
          weight: 2,
          text: (dossier.evidence || []).map((item) =>
            `${item.kind} ${item.title} ${item.quote} ${item.evidence_type || ""} ${item.polarity || ""} ${(item.signal_tags || []).join(" ")} ${(item.acquisition_bindings || []).map((binding) => `${binding.field || ""} ${binding.missing_layer || ""} ${binding.missing_layer_label || ""} ${confidenceCorpus(binding.binding_confidence)} ${(binding.keywords || []).join(" ")} ${binding.reason || ""}`).join(" ")}`
          ).join(" "),
        },
      ];
      return sources.reduce((score, source) => {
        const text = String(source.text || "").toLowerCase();
        return score + terms.reduce((inner, term) => inner + (text.includes(term) ? source.weight : 0), 0);
      }, 0);
    }

    function filteredRepos() {
      const query = state.query.trim().toLowerCase();
      const items = repos.filter((repo) => {
        if (state.track !== "all" && trackOf(repo) !== state.track) return false;
        if (!repoMatchesConfidenceSource(repo)) return false;
        if (!repoMatchesSignalGroup(repo)) return false;
        if (scoreOf(repo) < state.minScore) return false;
        if (query && !corpusOf(repo).includes(query)) return false;
        return true;
      });
      if (query) {
        return items
          .map((repo) => ({ repo, relevance: relevanceOf(repo, query) }))
          .sort((a, b) => b.relevance - a.relevance || scoreOf(b.repo) - scoreOf(a.repo))
          .map((item) => ({ ...item.repo, client_relevance: item.relevance }));
      }
      return items;
    }

    function renderTrackOptions() {
      const tracks = Array.from(new Set(repos.map(trackOf))).sort();
      trackSelect.innerHTML = [
        '<option value="all">All tracks</option>',
        ...tracks.map((track) => `<option value="${escapeHtml(track)}">${escapeHtml(track)}</option>`),
      ].join("");
    }

    function renderConfidenceSourceOptions() {
      const sources = Array.from(new Set([
        ...(DATA.statistics?.confidence_sources || []).map((item) => item.value),
        ...patterns.flatMap((pattern) => (pattern.confidence_sources || []).map((item) => item.value)),
        ...repos.flatMap((repo) => {
          const dossier = dossierOf(repo);
          return [
            ...(((dossier.evidence_acquisition || {}).bindings || []).map((binding) => confidenceSource(binding.binding_confidence))),
            ...((dossier.evidence || []).flatMap((item) => (item.acquisition_bindings || []).map((binding) => confidenceSource(binding.binding_confidence)))),
          ];
        }),
      ].filter(Boolean))).sort();
      confidenceSourceSelect.innerHTML = [
        '<option value="all">All confidence</option>',
        ...sources.map((source) => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`),
      ].join("");
    }

    function renderSignalGroupOptions() {
      const groups = Array.from(new Set([
        ...(DATA.statistics?.signal_groups || []).map((item) => item.value),
        ...cognitionSummaries.flatMap((summary) => (summary.signal_groups || []).map((item) => item.value)),
        ...patterns.flatMap((pattern) => (pattern.signal_groups || []).map((item) => item.value)),
        ...repos.flatMap((repo) => {
          const dossier = dossierOf(repo);
          const bindings = [
            ...((dossier.evidence_acquisition || {}).bindings || []),
            ...((dossier.evidence || []).flatMap((item) => item.acquisition_bindings || [])),
          ];
          return bindings.flatMap((binding) =>
            confidenceSignalBreakdown(binding.binding_confidence).map((item) => item.group)
          );
        }),
      ].filter(Boolean))).sort();
      signalGroupSelect.innerHTML = [
        '<option value="all">All signal groups</option>',
        ...groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`),
      ].join("");
      signalGroupSelect.value = groups.includes(state.signalGroup) ? state.signalGroup : "all";
      state.signalGroup = signalGroupSelect.value;
    }

    function renderStats(items) {
      const deepCount = items.filter((repo) => {
        const dossier = dossierOf(repo);
        return (dossier.claims || []).length || (dossier.evidence || []).length;
      }).length;
      const claimCount = items.reduce((sum, repo) => sum + (dossierOf(repo).claims || []).length, 0);
      const gapCount = items.reduce((sum, repo) => sum + (dossierOf(repo).claim_gap_report || []).length, 0);
      const bindingCount = items.reduce((sum, repo) => sum + ((dossierOf(repo).evidence_acquisition || {}).binding_count || 0), 0);
      const patternCount = filteredPatterns().length;
      const evidenceCount = items.reduce((sum, repo) => sum + (dossierOf(repo).evidence || []).length, 0);
      const average = items.length
        ? items.reduce((sum, repo) => sum + scoreOf(repo), 0) / items.length
        : 0;
      const topTrack = Object.entries(
        items.reduce((acc, repo) => {
          const track = trackOf(repo);
          acc[track] = (acc[track] || 0) + 1;
          return acc;
        }, {})
      ).sort((a, b) => b[1] - a[1])[0];

      const blocks = [
        ["Repositories", items.length],
        ["Deep dossiers", deepCount],
        ["Claims", claimCount],
        ["Claim gaps", gapCount],
        ["Bindings", bindingCount],
        ["Patterns", patternCount],
        ["Evidence", evidenceCount],
        ["Avg score", average ? average.toFixed(1) : "0.0"],
      ];
      stats.innerHTML = blocks.map(([label, value]) => `
        <div class="stat">
          <div class="stat-label">${escapeHtml(label)}</div>
          <div class="stat-value">${escapeHtml(value)}</div>
          <div class="subtle">${
            label === "Repositories" && topTrack
              ? escapeHtml(topTrack[0] + ": " + topTrack[1])
              : label === "Patterns"
                ? escapeHtml((DATA.statistics?.cross_project_patterns ?? 0) + " cross-project")
                : "&nbsp;"
          }</div>
        </div>
      `).join("");
    }

    function filteredPatterns() {
      const query = state.query.trim().toLowerCase();
      return patterns.filter((pattern) => {
        if (!patternMatchesConfidenceSource(pattern)) return false;
        if (!patternMatchesSignalGroup(pattern)) return false;
        if (query && !patternCorpus(pattern).includes(query)) return false;
        return true;
      });
    }

    function filteredCognitionSummaries() {
      const query = state.query.trim().toLowerCase();
      return cognitionSummaries.filter((summary) => {
        if (!cognitionSummaryMatchesSignalGroup(summary)) return false;
        if (query && !cognitionSummaryCorpus(summary).includes(query)) return false;
        return true;
      });
    }

    function renderPatterns() {
      const items = filteredPatterns().slice(0, 6);
      const summaries = filteredCognitionSummaries().slice(0, 4);
      if (!patterns.length && !cognitionSummaries.length) {
        patternsPanel.innerHTML = "";
        return;
      }
      const averageConfidence = DATA.statistics?.average_pattern_confidence;
      const averageSignal = DATA.statistics?.average_pattern_signal_score;
      const summaryCards = summaries.map((summary) => {
        const topLayers = (summary.layer_counts || []).slice(0, 3);
        const topActions = (summary.layer_actions || []).slice(0, 2);
        const topSignals = (summary.signal_groups || []).slice(0, 4);
        return `
          <article class="pattern-card">
            <h2>${escapeHtml(summary.label || summary.category || "Cognition summary")}</h2>
            <div class="chips">
              <span class="chip ${summary.confidence === "high" ? "support" : ""}">${escapeHtml(summary.confidence || "unknown")} ${escapeHtml(summary.score ?? 0)}</span>
              <span class="chip">Repos ${escapeHtml(summary.repository_count || 0)}</span>
              <span class="chip">Patterns ${escapeHtml(summary.pattern_count || 0)}</span>
              <span class="chip">Bindings ${escapeHtml(summary.binding_count || 0)}</span>
            </div>
            <p>${escapeHtml(compact(summary.summary || "", 180))}</p>
            <p class="subtle">${escapeHtml(compact(summary.transfer_rule || "", 160))}</p>
            <div class="chips">
              ${topLayers.map((item) => `<span class="chip">${escapeHtml(item.value)} ${escapeHtml(item.count)}</span>`).join("")}
              ${topActions.map((item) => `<span class="chip">${escapeHtml(item.value)} ${escapeHtml(item.count)}</span>`).join("")}
              ${topSignals.map((item) => `<span class="chip">${escapeHtml(item.value)} ${escapeHtml(item.count)}</span>`).join("")}
            </div>
          </article>
        `;
      }).join("");
      const cards = items.map((pattern) => {
        const topKeyword = (pattern.keywords || [])[0]?.value;
        const topEvidenceType = (pattern.evidence_types || [])[0]?.value;
        const topSignalGroups = (pattern.signal_groups || []).slice(0, 6);
        const confidence = {
          label: pattern.reliability_status,
          score: pattern.average_binding_confidence,
        };
        return `
          <article class="pattern-card">
            <h2>${escapeHtml(pattern.field || "Unknown claim")} -> ${escapeHtml(pattern.missing_layer_label || pattern.missing_layer || "gap")}</h2>
            <div class="chips">
              <span class="chip ${pattern.repeat_status === "cross_project" ? "support" : ""}">${escapeHtml(pattern.repeat_status || "single_project")}</span>
              <span class="chip">Repos ${escapeHtml(pattern.repository_count || 0)}</span>
              <span class="chip">Bindings ${escapeHtml(pattern.binding_count || 0)}</span>
              <span class="chip ${confidenceClass(confidence)}">Confidence ${escapeHtml(confidenceText(confidence))}</span>
              <span class="chip">Signal score ${escapeHtml(pattern.signal_group_score ?? 0)}</span>
              ${(pattern.confidence_sources || []).slice(0, 2).map((item) => `<span class="chip">${escapeHtml(item.value)} ${escapeHtml(item.count)}</span>`).join("")}
            </div>
            <p class="subtle">${escapeHtml(compact((pattern.repositories || []).join(", "), 120))}</p>
            <div class="chips">
              ${topSignalGroups.map((item) => `<span class="chip">${escapeHtml(item.value)} ${escapeHtml(item.count)}</span>`).join("")}
              ${topEvidenceType ? `<span class="chip">${escapeHtml(topEvidenceType)}</span>` : ""}
              ${topKeyword ? `<span class="chip">${escapeHtml(topKeyword)}</span>` : ""}
              <span class="chip">Score ${escapeHtml(pattern.pattern_score ?? 0)}</span>
            </div>
          </article>
        `;
      }).join("");
      patternsPanel.innerHTML = `
        ${cognitionSummaries.length ? `
          <div class="patterns-head">
            <div class="section-title">Cognition Summaries</div>
            <div class="count">${escapeHtml(summaries.length)} / ${escapeHtml(cognitionSummaries.length)}</div>
          </div>
          <div class="patterns-grid">${summaryCards || '<div class="empty">No matching cognition summaries.</div>'}</div>
        ` : ""}
        <div class="patterns-head">
          <div class="section-title">Cross-project Patterns</div>
          <div class="count">${escapeHtml(items.length)} / ${escapeHtml(patterns.length)}${averageConfidence ? " · avg confidence " + escapeHtml(averageConfidence) : ""}${averageSignal ? " · avg signal " + escapeHtml(averageSignal) : ""}</div>
        </div>
        <div class="patterns-grid">${cards || '<div class="empty">No matching patterns.</div>'}</div>
      `;
    }

    function riskClass(repo) {
      const risk = repo.fake_star_risk || "";
      if (risk.startsWith("高")) return "risk-high";
      if (risk.startsWith("中")) return "risk-mid";
      return "";
    }

    function renderList(items) {
      resultCount.textContent = `${items.length} / ${repos.length}`;
      if (!items.length) {
        repoList.innerHTML = '<div class="empty">No matching repositories.</div>';
        githubLink.removeAttribute("href");
        detailBody.innerHTML = '<div class="empty">No dossier selected.</div>';
        return;
      }
      if (!state.selected || !items.some((repo) => repo.full_name === state.selected)) {
        state.selected = items[0].full_name;
      }
      repoList.innerHTML = items.map((repo) => {
        const active = repo.full_name === state.selected ? " active" : "";
        const score = scoreOf(repo);
        return `
          <button class="repo-row${active}" type="button" data-repo="${escapeHtml(repo.full_name)}">
            <div class="repo-name">${escapeHtml(repo.full_name)}</div>
            <div class="repo-desc">${escapeHtml(repo.description || "No description.")}</div>
            <div class="chips">
              <span class="chip track">${escapeHtml(trackOf(repo))}</span>
              <span class="chip">${escapeHtml(repo.language || "Unknown")}</span>
              ${repo.client_relevance ? `<span class="chip">Relevance ${escapeHtml(repo.client_relevance)}</span>` : ""}
              <span class="chip ${riskClass(repo)}">${escapeHtml((repo.fake_star_risk || "unknown").split("：")[0])}</span>
            </div>
            <div class="score-line">
              <span>Score</span>
              <span class="bar"><span style="width: ${Math.max(0, Math.min(100, score))}%"></span></span>
              <span>${score.toFixed(1)}</span>
            </div>
          </button>
        `;
      }).join("");
      repoList.querySelectorAll(".repo-row").forEach((button) => {
        button.addEventListener("click", () => {
          state.selected = button.dataset.repo;
          render();
        });
      });
      renderDetail(items.find((repo) => repo.full_name === state.selected));
    }

    function metric(label, value) {
      return `<div class="metric"><span class="subtle">${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`;
    }

    function renderDetail(repo) {
      if (!repo) {
        githubLink.removeAttribute("href");
        detailBody.innerHTML = '<div class="empty">No dossier selected.</div>';
        return;
      }
      githubLink.href = repo.html_url || "#";
      const dossier = dossierOf(repo);
      const acquisition = dossier.evidence_acquisition || {};
      const bindings = acquisition.bindings || [];
      const displayedBindings = bindings.filter((binding) => bindingMatchesConfidenceSource(binding) && bindingMatchesSignalGroup(binding));
      const health = repo.health || {};
      const signals = repo.track_score?.signals || {};
      const signalChips = Object.entries(signals).map(([name, value]) =>
        `<span class="chip">${escapeHtml(name)} ${escapeHtml(value)}</span>`
      ).join("");
      const claims = (dossier.claims || []).map((claim) => {
        const support = claim.support_coverage || {};
        const supportLayers = (support.layer_labels || support.layers || []).slice(0, 4);
        return `
          <article class="item">
            <h3>${escapeHtml(claim.field)} <span class="subtle">${escapeHtml(claim.confidence || "")}</span></h3>
            <p>${escapeHtml(claim.text)}</p>
            <div class="chips">
              ${support.label ? `<span class="chip support">${escapeHtml(support.label)}</span>` : ""}
              ${Number.isFinite(Number(support.score)) ? `<span class="chip">Coverage ${escapeHtml(support.score)}</span>` : ""}
              ${supportLayers.map((layer) => `<span class="chip">${escapeHtml(layer)}</span>`).join("")}
              ${claim.template ? `<span class="chip">${escapeHtml(claim.template)}</span>` : ""}
              ${(claim.counter_evidence_ids || []).length ? `<span class="chip risk-mid">Boundary ${escapeHtml(claim.counter_evidence_ids.length)}</span>` : ""}
            </div>
            <div class="subtle">${escapeHtml(claim.claim_id || "")}</div>
          </article>
        `;
      }).join("");
      const gaps = (dossier.claim_gap_report || []).map((gap) => `
        <article class="item">
          <h3>${escapeHtml(gap.field)} <span class="subtle">${escapeHtml((gap.priority_score ?? 0) + "/100")}</span></h3>
          <p>${escapeHtml(gap.recommendation || "")}</p>
          <div class="chips">
            <span class="chip risk-mid">${escapeHtml(gap.support_label || "Weak support")}</span>
            <span class="chip">Support ${escapeHtml(gap.support_score ?? 0)}</span>
            ${(gap.missing_layer_labels || []).slice(0, 4).map((layer) => `<span class="chip">${escapeHtml(layer)}</span>`).join("")}
          </div>
          <div class="subtle">${escapeHtml(gap.gap_reason || "")}</div>
        </article>
      `).join("");
      const acquisitionCards = displayedBindings.slice(0, 8).map((binding) => `
        <article class="item">
          <h3>${escapeHtml(binding.field || "Unknown claim")} <span class="subtle">${escapeHtml(binding.missing_layer_label || binding.missing_layer || "")}</span></h3>
          <p>${escapeHtml(binding.reason || "No gap reason archived.")}</p>
          <div class="chips">
            <span class="chip support">${escapeHtml(binding.evidence_stable_id || binding.evidence_id || "")}</span>
            <span class="chip ${confidenceClass(binding.binding_confidence)}">Confidence ${escapeHtml(confidenceText(binding.binding_confidence))}</span>
            <span class="chip">${escapeHtml(confidenceSourceText(binding.binding_confidence))}</span>
            ${confidenceSignalChips(binding.binding_confidence, 4, 2)}
            ${(binding.keywords || []).slice(0, 4).map((keyword) => `<span class="chip">${escapeHtml(keyword)}</span>`).join("")}
          </div>
        </article>
      `).join("");
      const evidence = (dossier.evidence || [])
        .filter((item) => {
          if (state.confidenceSource === "all" && state.signalGroup === "all") return true;
          return (item.acquisition_bindings || []).some((binding) => bindingMatchesConfidenceSource(binding) && bindingMatchesSignalGroup(binding));
        })
        .slice(0, 12)
        .map((item) => {
        const itemBindings = (item.acquisition_bindings || []).filter((binding) => bindingMatchesConfidenceSource(binding) && bindingMatchesSignalGroup(binding));
        const bindingChips = itemBindings.slice(0, 3).map((binding) =>
          `<span class="chip support">补强 ${escapeHtml(binding.field || "claim")} / ${escapeHtml(binding.missing_layer_label || binding.missing_layer || "gap")}</span><span class="chip ${confidenceClass(binding.binding_confidence)}">${escapeHtml(confidenceText(binding.binding_confidence))}</span><span class="chip">${escapeHtml(confidenceSourceText(binding.binding_confidence))}</span>${confidenceSignalChips(binding.binding_confidence, 2, 1)}`
        ).join("");
        const bindingReason = itemBindings.length ? itemBindings.map((binding) =>
          `${binding.field || "claim"}: ${binding.reason || binding.missing_layer_label || binding.missing_layer || ""} (${confidenceText(binding.binding_confidence)}${confidenceSignalText(binding.binding_confidence, 2, 1) ? " / " + confidenceSignalText(binding.binding_confidence, 2, 1) : ""})`
        ).join(" | ") : "";
        return `
          <article class="item">
            <h3>${escapeHtml(item.kind)} - ${escapeHtml(item.title)}</h3>
            <p>${escapeHtml(compact(item.quote, 360))}</p>
            <div class="chips">
              <span class="chip">${escapeHtml(item.evidence_type || "general")}</span>
              <span class="chip ${item.polarity === "negative" || item.polarity === "boundary" ? "risk-mid" : ""}">${escapeHtml(item.polarity || "supporting")}</span>
              ${(item.signal_tags || []).slice(0, 3).map((tag) => `<span class="chip">${escapeHtml(tag)}</span>`).join("")}
              ${bindingChips}
            </div>
            <div class="subtle">${escapeHtml(item.stable_id || item.evidence_id || "")}${bindingReason ? " · " + escapeHtml(compact(bindingReason, 180)) : ""}</div>
          </article>
        `;
      }).join("");

      detailBody.innerHTML = `
        <h2 class="detail-title">${escapeHtml(repo.full_name)}</h2>
        <p class="detail-desc">${escapeHtml(repo.description || "No description.")}</p>
        <div class="chips">
          <span class="chip track">${escapeHtml(trackOf(repo))}</span>
          <span class="chip">${escapeHtml(repo.language || "Unknown")}</span>
          <span class="chip">${escapeHtml(repo.license || "No license")}</span>
          <span class="chip ${riskClass(repo)}">${escapeHtml(repo.fake_star_risk || "Risk unknown")}</span>
        </div>
        <div class="grid">
          ${metric("Stars", repo.stars ?? 0)}
          ${metric("Forks", repo.forks ?? 0)}
          ${metric("Open issues", repo.open_issues ?? 0)}
          ${metric("Track score", scoreOf(repo).toFixed(1))}
          ${metric("Merged PRs 180d", health.merged_prs_180d ?? "unknown")}
          ${metric("Closed issues 180d", health.closed_issues_180d ?? "unknown")}
          ${metric("Releases 365d", health.release_count_365d_sample ?? 0)}
          ${metric("Contributors", health.top_contributor_count_sample ?? 0)}
        </div>
        <div class="chips">${signalChips}</div>
        <section class="claims">
          <div class="section-title">Claims</div>
          ${claims || '<div class="empty">No deep claims archived.</div>'}
        </section>
        <section class="gaps">
          <div class="section-title">Claim Gaps</div>
          ${gaps || '<div class="empty">No high-priority claim gaps.</div>'}
        </section>
        <section class="acquisition">
          <div class="section-title">Evidence Acquisition</div>
          ${displayedBindings.length ? `
            <div class="chips">
              <span class="chip support">${escapeHtml(acquisition.strategy || "claim_gap_targeted")}</span>
              <span class="chip">Bindings ${escapeHtml(displayedBindings.length)} / ${escapeHtml(acquisition.binding_count || bindings.length)}</span>
              <span class="chip">Added ${escapeHtml(acquisition.added_total || 0)}</span>
              ${Number.isFinite(Number(acquisition.average_binding_confidence)) ? `<span class="chip">Avg confidence ${escapeHtml(acquisition.average_binding_confidence)}</span>` : ""}
              ${state.confidenceSource !== "all" ? `<span class="chip">${escapeHtml(state.confidenceSource)}</span>` : ""}
              ${state.signalGroup !== "all" ? `<span class="chip">${escapeHtml(state.signalGroup)}</span>` : ""}
            </div>
            ${acquisitionCards}
          ` : '<div class="empty">No acquisition bindings for these filters.</div>'}
        </section>
        <section class="evidence">
          <div class="section-title">Evidence</div>
          ${evidence || '<div class="empty">No evidence archived.</div>'}
        </section>
      `;
    }

    function render() {
      scoreOutput.value = state.minScore;
      const items = filteredRepos();
      renderStats(items);
      renderPatterns();
      renderList(items);
    }

    document.getElementById("dbMeta").textContent = DATA.db || "";
    document.getElementById("timeMeta").textContent = DATA.generated_at || "";
    renderTrackOptions();
    renderConfidenceSourceOptions();
    renderSignalGroupOptions();

    searchInput.addEventListener("input", () => {
      state.query = searchInput.value;
      render();
    });
    trackSelect.addEventListener("change", () => {
      state.track = trackSelect.value;
      render();
    });
    confidenceSourceSelect.addEventListener("change", () => {
      state.confidenceSource = confidenceSourceSelect.value;
      state.selected = null;
      render();
    });
    signalGroupSelect.addEventListener("change", () => {
      state.signalGroup = signalGroupSelect.value;
      state.selected = null;
      render();
    });
    scoreRange.addEventListener("input", () => {
      state.minScore = Number(scoreRange.value) || 0;
      render();
    });
    resetButton.addEventListener("click", () => {
      state.query = "";
      state.track = "all";
      state.confidenceSource = "all";
      state.signalGroup = "all";
      state.minScore = 0;
      state.selected = null;
      searchInput.value = "";
      trackSelect.value = "all";
      confidenceSourceSelect.value = "all";
      signalGroupSelect.value = "all";
      scoreRange.value = "0";
      render();
    });

    render();
  </script>
</body>
</html>
""".replace("__DATA__", data_json)


def write_dashboard(path: str, payload: dict) -> None:
    output = pathlib.Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_archive_dashboard(payload), encoding="utf-8")
    print(f"Wrote {output}.")


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
        f"- Search backend：{(payload.get('search_index') or {}).get('backend', 'unknown')}",
        f"- Indexed documents：{(payload.get('search_index') or {}).get('indexed_documents', 'unknown')}",
        f"- Track 过滤：{payload['filters'].get('track') or '无'}",
        f"- 最低 track score：{payload['filters'].get('min_track_score') or 0}",
        "",
    ]
    for index, entry in enumerate(payload["matches"], 1):
        summary = entry["repository"]
        relevance = entry.get("relevance") or {}
        source_types = ", ".join(relevance.get("source_types") or []) or "unknown"
        lines.extend([f"## {index}. {summary['full_name']}", ""])
        lines.extend(
            [
                f"- Relevance backend：{relevance.get('backend', 'unknown')}",
                f"- Relevance score：{relevance.get('score') if relevance.get('score') is not None else 'unranked'}",
                f"- Matched documents：{relevance.get('matched_documents') or 'unknown'}",
                f"- Matched source types：{source_types}",
                "",
            ]
        )
        lines.extend(render_archive_repo_brief(summary, payload["db"]))
        lines.append("")
        if entry["matched_claims"]:
            lines.extend(["### Matched claims", ""])
            for claim in entry["matched_claims"]:
                lines.extend(
                    [
                        f"- `{claim.get('claim_id') or 'no-claim-id'}` {claim['field']} ({claim['confidence']}): "
                        f"{one_line(claim['text'])} / {support_coverage_text(claim.get('support_coverage'))}",
                    ]
                )
            lines.append("")
        if entry.get("matched_gaps"):
            lines.extend(["### Matched claim gaps", ""])
            for gap in entry["matched_gaps"]:
                lines.extend(
                    [
                        f"- `{gap.get('source_id') or 'no-gap-id'}` {gap.get('field') or 'Gap'}: "
                        f"{one_line(gap.get('text'))}",
                    ]
                )
            lines.append("")
        if entry.get("matched_bindings"):
            lines.extend(["### Matched acquisition bindings", ""])
            for binding in entry["matched_bindings"]:
                stable_ref = binding.get("evidence_stable_id") or binding.get("evidence_id") or "no-evidence-id"
                confidence = binding.get("binding_confidence") or {}
                lines.extend(
                    [
                        f"- `{stable_ref}` -> {binding.get('field') or 'Claim'} / "
                        f"{binding.get('missing_layer_label') or binding.get('missing_layer') or 'gap'}: "
                        f"{one_line(binding.get('reason'))} "
                        f"(confidence {confidence.get('label') or 'unknown'} "
                        f"{confidence.get('score') if confidence.get('score') is not None else 'unknown'} / "
                        f"source {confidence.get('source') or 'heuristic'})",
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


def count_items_text(items: list[dict], limit: int = 6) -> str:
    text = "、".join(f"{item.get('value')}={item.get('count')}" for item in items[:limit] if item.get("value"))
    return text or "无"


def confidence_signal_breakdown_text(confidence: dict | None, group_limit: int = 5, signal_limit: int = 3) -> str:
    if not confidence:
        return "无"
    breakdown = confidence.get("signal_breakdown") or confidence_signal_breakdown(confidence.get("signals") or [])
    parts = []
    for group in breakdown[:group_limit]:
        signals = group.get("signals") or []
        labels = [item.get("label") or item.get("raw") for item in signals[:signal_limit]]
        if len(signals) > signal_limit:
            labels.append(f"+{len(signals) - signal_limit}")
        if labels:
            parts.append(f"{group.get('group') or 'other'}: {', '.join(labels)}")
    return "；".join(parts) or "无"


def render_archive_cognition_summaries(summaries: list[dict]) -> list[str]:
    if not summaries:
        return []
    lines = ["## Automatic Cognition Summaries", ""]
    for index, summary in enumerate(summaries, 1):
        lines.extend(
            [
                f"### {index}. {summary.get('label') or summary.get('category')}",
                "",
                f"- Summary ID：`{summary.get('summary_id')}`",
                f"- Confidence：{summary.get('confidence') or 'unknown'} / {summary.get('score', 0)}/100",
                f"- 仓库数 / pattern 数 / binding 数：{summary.get('repository_count', 0)} / {summary.get('pattern_count', 0)} / {summary.get('binding_count', 0)}",
                f"- 摘要：{summary.get('summary') or '无'}",
                f"- 证据依据：{summary.get('evidence_basis') or '无'}",
                f"- 可迁移规则：{summary.get('transfer_rule') or '无'}",
                f"- 证据层：{count_items_text(summary.get('layer_counts') or [])}",
                f"- 自动复核动作：{count_items_text(summary.get('layer_actions') or [])}",
                f"- Signal groups：{count_items_text(summary.get('signal_groups') or [])}",
                f"- Signal labels：{count_items_text(summary.get('signal_labels') or [], limit=8)}",
                "",
            ]
        )
        supporting = summary.get("supporting_patterns") or []
        if supporting:
            lines.extend(["支撑 patterns：", ""])
            for pattern in supporting[:4]:
                lines.append(
                    f"- `{pattern.get('pattern_id')}` {pattern.get('field')} -> "
                    f"{pattern.get('missing_layer_label') or pattern.get('missing_layer')}；"
                    f"score {pattern.get('pattern_score', 0)}；repos {pattern.get('repository_count', 0)}；"
                    f"bindings {pattern.get('binding_count', 0)}"
                )
            lines.append("")
    return lines


def render_archive_patterns(payload: dict) -> str:
    if payload.get("message"):
        return "\n".join(["# OSS Cognition Archive Patterns", "", payload["message"], ""])
    stats = payload.get("statistics") or {}
    lines = [
        "# OSS Cognition Archive Patterns",
        "",
        f"- 数据库：{payload['db']}",
        f"- 生成时间：{payload['generated_at']}",
        f"- 数据范围：{payload.get('scope') or 'latest_deep_dossiers'}",
        f"- Track 过滤：{payload['filters'].get('track') or '无'}",
        f"- 最低 track score：{payload['filters'].get('min_track_score') or 0}",
        f"- Signal group 过滤：{payload['filters'].get('signal_group') or '无'}",
        f"- 参与绑定数：{stats.get('bindings', 0)}",
        f"- 参与仓库数：{stats.get('repositories', 0)}",
        f"- 模式数：{stats.get('patterns', 0)}",
        f"- 自动认知摘要数：{stats.get('cognition_summaries', 0)}",
        f"- 高置信摘要数：{stats.get('high_confidence_cognition_summaries', 0)}",
        f"- 跨项目重复模式：{stats.get('cross_project_patterns', 0)}",
        f"- 平均模式可靠度：{stats.get('average_pattern_confidence') if stats.get('average_pattern_confidence') is not None else '未记录'}",
        f"- 平均信号结构分：{stats.get('average_pattern_signal_score') if stats.get('average_pattern_signal_score') is not None else '未记录'}",
        f"- Signal groups：{count_items_text(stats.get('signal_groups') or [])}",
        "",
    ]
    if not payload.get("patterns"):
        lines.extend(["当前 archive 中没有可聚合的 evidence acquisition bindings。", ""])
        return "\n".join(lines)

    lines.extend(render_archive_cognition_summaries(payload.get("cognition_summaries") or []))

    for index, pattern in enumerate(payload["patterns"], 1):
        lines.extend(
            [
                f"## {index}. {pattern.get('field')} -> {pattern.get('missing_layer_label') or pattern.get('missing_layer')}",
                "",
                f"- Pattern ID：`{pattern.get('pattern_id')}`",
                f"- 状态：{pattern.get('repeat_status')}",
                f"- 仓库数 / 绑定数：{pattern.get('repository_count', 0)} / {pattern.get('binding_count', 0)}",
                f"- Pattern score：{pattern.get('pattern_score', 0)}/100",
                f"- Repeat / confidence / signal score：{pattern.get('repeat_score', 0)} / {pattern.get('confidence_score', 0)} / {pattern.get('signal_group_score', 0)}",
                f"- 平均绑定可靠度：{pattern.get('average_binding_confidence') if pattern.get('average_binding_confidence') is not None else '未记录'}（{pattern.get('reliability_status') or 'unknown'}）",
                f"- 最低绑定可靠度：{pattern.get('minimum_binding_confidence') if pattern.get('minimum_binding_confidence') is not None else '未记录'}",
                f"- Confidence labels：{count_items_text(pattern.get('confidence_labels') or [])}",
                f"- Confidence sources：{count_items_text(pattern.get('confidence_sources') or [])}",
                f"- Signal groups：{count_items_text(pattern.get('signal_groups') or [])}",
                f"- Signal labels：{count_items_text(pattern.get('signal_labels') or [], limit=10)}",
                f"- Tracks：{count_items_text(pattern.get('tracks') or [])}",
                f"- Evidence types：{count_items_text(pattern.get('evidence_types') or [])}",
                f"- Evidence kinds：{count_items_text(pattern.get('evidence_kinds') or [])}",
                f"- Keywords：{count_items_text(pattern.get('keywords') or [], limit=10)}",
                f"- 常见缺口原因：{count_items_text(pattern.get('reasons') or [], limit=3)}",
                "",
            ]
        )
        if pattern.get("repositories"):
            lines.extend([f"- Repositories：{', '.join(pattern['repositories'])}", ""])
        if pattern.get("examples"):
            lines.extend(["### Examples", ""])
            for example in pattern["examples"]:
                stable_ref = example.get("evidence_stable_id") or example.get("evidence_id") or "no-evidence-id"
                confidence = example.get("binding_confidence") or {}
                title = " - ".join(
                    item for item in [example.get("evidence_kind"), example.get("evidence_title")] if item
                )
                keywords = "、".join(example.get("keywords") or []) or "无"
                lines.extend(
                    [
                        f"- `{stable_ref}` {example.get('repo_full_name')} ({example.get('track') or 'unknown'} / "
                        f"{example.get('track_score') if example.get('track_score') is not None else 'unknown'}): "
                        f"{title or 'Evidence'}；可靠度：{confidence.get('label') or 'unknown'} "
                        f"{confidence.get('score') if confidence.get('score') is not None else 'unknown'}；"
                        f"信号：{confidence_signal_breakdown_text(confidence, group_limit=3, signal_limit=2)}；"
                        f"关键词：{keywords}；原因：{one_line(example.get('reason'))}",
                    ]
                )
                if example.get("quote"):
                    lines.append(f"  摘录：{one_line(example.get('quote'), 220)}")
            lines.append("")
    return "\n".join(lines)


def render_archive_auto_calibrate(payload: dict) -> str:
    stats = payload.get("statistics") or {}
    lines = [
        "# OSS Cognition Archive Auto Calibration",
        "",
        f"- 数据库：{payload['db']}",
        f"- 生成时间：{payload['generated_at']}",
        f"- 数据范围：{payload.get('scope') or 'latest_deep_dossiers'}",
        f"- 候选绑定数：{stats.get('candidate_bindings', 0)}",
        f"- 已自动校准绑定数：{stats.get('updated_bindings', 0)}",
        f"- 参与仓库数：{stats.get('repositories', 0)}",
        f"- 平均自动 confidence：{stats.get('mean_auto_confidence') if stats.get('mean_auto_confidence') is not None else '未记录'}",
        f"- 自动 confidence 范围：{stats.get('minimum_auto_confidence') if stats.get('minimum_auto_confidence') is not None else '未记录'} - {stats.get('maximum_auto_confidence') if stats.get('maximum_auto_confidence') is not None else '未记录'}",
        f"- 自动 confidence labels：{count_items_text(stats.get('auto_confidence_labels') or [])}",
        f"- 平均分数调整：{stats.get('mean_score_delta') if stats.get('mean_score_delta') is not None else '未记录'}",
        f"- 跨版本稳定绑定数：{stats.get('cross_version_stable_bindings', 0)}",
        f"- 带时间序列上下文仓库数：{stats.get('time_series_context_repositories', 0)}",
        f"- Search backend：{(payload.get('search_index') or {}).get('backend', 'unknown')}",
        "",
    ]
    if payload.get("updated"):
        lines.extend(["## Largest Adjustments", ""])
        for item in payload["updated"][:12]:
            stable_ref = item.get("evidence_stable_id") or item.get("evidence_id") or "no-evidence-id"
            context = item.get("pattern_context") or {}
            history = item.get("binding_history_context") or {}
            time_series = item.get("repository_time_series_context") or {}
            score_components = item.get("score_components") or {}
            lines.append(
                f"- `{item.get('repo_full_name')}` {item.get('field')} / {item.get('missing_layer_label') or item.get('missing_layer')} / "
                f"`{stable_ref}`：heuristic {item.get('heuristic_score')} -> auto {item.get('auto_score')} "
                f"({item.get('auto_label')}, delta {item.get('score_delta')}); "
                f"components base {score_components.get('base', 'unknown')}, heuristic {score_components.get('heuristic_component', 'unknown')}, "
                f"repeat {score_components.get('repetition_component', 'unknown')}, time {score_components.get('time_series_component', 'unknown')}, "
                f"evidence {score_components.get('evidence_quality_component', 'unknown')}, penalty {score_components.get('penalty_component', 'unknown')}; "
                f"repos {context.get('repository_count', 0)}, bindings {context.get('binding_count', 0)}, "
                f"versions {history.get('run_count', 0)}, activity {time_series.get('activity_trend', 'unknown')}, "
                f"release {time_series.get('release_trend', 'unknown')}"
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
        counter_refs = claim.get("counter_evidence_stable_ids") or []
        counter_text = (
            ", ".join(f"`{item}`" for item in counter_refs)
            if counter_refs
            else evidence_refs(claim.get("counter_evidence_ids") or [])
        )
        lines.extend(
            [
                f"### {claim['field']}",
                "",
                claim["text"],
                "",
                f"- Claim ID：`{claim.get('claim_id') or '无'}`",
                f"- 模板：{claim.get('template') or '无'}",
                f"- 推断依据：{claim.get('rationale') or '无'}",
                f"- 支撑覆盖：{support_coverage_text(claim.get('support_coverage'))}",
                f"- 证据：{refs}",
                f"- 边界/反向证据：{counter_text}",
                f"- 置信度：{claim['confidence']}",
                "",
            ]
        )

    lines.extend(render_claim_gap_report(payload.get("claim_gap_report") or []))
    lines.extend(render_evidence_acquisition_summary(payload.get("evidence_acquisition") or {}))
    lines.extend(["## Evidence", ""])
    if not payload.get("evidence"):
        lines.extend(["该归档快照没有证据链。", ""])
    for item in payload.get("evidence", []):
        binding_text = "无"
        if item.get("acquisition_bindings"):
            binding_text = "；".join(
                f"{binding.get('field') or '未知 claim'} / {binding.get('missing_layer_label') or binding.get('missing_layer') or '未知层'}"
                f" / confidence {(binding.get('binding_confidence') or {}).get('label') or 'unknown'} "
                f"{(binding.get('binding_confidence') or {}).get('score') if (binding.get('binding_confidence') or {}).get('score') is not None else 'unknown'}"
                f" / source {(binding.get('binding_confidence') or {}).get('source') or 'heuristic'}"
                f" / signals {confidence_signal_breakdown_text(binding.get('binding_confidence') or {}, group_limit=3, signal_limit=2)}"
                for binding in item.get("acquisition_bindings") or []
            )
        lines.extend(
            [
                f"### {item['evidence_id']}. {item['kind']} - {item['title']}",
                "",
                f"- Stable ID：`{item.get('stable_id') or '无'}`",
                f"- Gap 采集绑定：{binding_text}",
                f"- 类型 / 极性：{item.get('evidence_type') or 'general'} / {item.get('polarity') or 'supporting'}",
                f"- 信号标签：{', '.join(item.get('signal_tags') or []) or '无'}",
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
        bool(args.archive_patterns),
        bool(args.archive_auto_calibrate),
        args.archive_dashboard is not None,
    ]
    if sum(modes) != 1:
        raise SystemExit(
            "Choose exactly one archive mode: --archive-list, --archive-search, --archive-show, --archive-patterns, --archive-auto-calibrate, or --archive-dashboard."
        )
    if args.archive_search is not None and not args.archive_search.strip():
        raise SystemExit("--archive-search requires non-empty text.")
    signal_group = getattr(args, "archive_signal_group", None)
    if signal_group and not (args.archive_patterns or args.archive_dashboard is not None):
        raise SystemExit("--archive-signal-group is only supported with --archive-patterns or --archive-dashboard.")

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
            elif args.archive_show is not None:
                payload = archive_show_payload(conn, args)
                markdown = render_archive_show(payload)
            elif args.archive_patterns:
                payload = archive_patterns_payload(conn, args)
                markdown = render_archive_patterns(payload)
            elif args.archive_auto_calibrate:
                payload = apply_archive_auto_calibration(conn, args)
                markdown = render_archive_auto_calibrate(payload)
            else:
                payload = archive_dashboard_payload(conn, args)
                write_dashboard(args.archive_dashboard, payload)
                if args.json_output:
                    write_json(args.json_output, payload)
                return
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


def render_evidence_acquisition_summary(summary: dict | None) -> list[str]:
    lines = ["## Evidence Acquisition", ""]
    if not summary:
        return lines + ["未记录额外证据采集。", ""]
    requested = "、".join(summary.get("requested_layer_labels") or []) or "无"
    counts = summary.get("added_counts") or {}
    count_text = "、".join(
        f"{SUPPORT_LAYER_LABELS.get(layer, layer)}={count}"
        for layer, count in counts.items()
    ) or "无"
    ids = ", ".join(f"`{item}`" for item in summary.get("added_evidence_ids") or []) or "无"
    fields = "、".join(summary.get("target_claim_fields") or []) or "无"
    source_text = count_items_text(summary.get("confidence_sources") or [])
    lines.extend(
        [
            f"- 策略：{summary.get('strategy') or '未知'}",
            f"- 状态：{summary.get('status') or '未知'}",
            f"- Gap 请求层：{requested}",
            f"- 新增证据数：{summary.get('added_total', 0)}",
            f"- 绑定 claim 数：{summary.get('binding_count', 0)}",
            f"- 平均绑定可靠度：{summary.get('average_binding_confidence') if summary.get('average_binding_confidence') is not None else '未记录'}",
            f"- 最低绑定可靠度：{summary.get('minimum_binding_confidence') if summary.get('minimum_binding_confidence') is not None else '未记录'}",
            f"- Confidence sources：{source_text}",
            f"- 目标 claim：{fields}",
            f"- 新增证据分布：{count_text}",
            f"- 新增证据 ID：{ids}",
            "",
        ]
    )
    bindings = summary.get("bindings") or []
    if bindings:
        lines.extend(["### Evidence-to-claim bindings", ""])
        for binding in bindings[:12]:
            stable_ref = binding.get("evidence_stable_id") or binding.get("evidence_id") or "无"
            keywords = "、".join(binding.get("keywords") or []) or "无"
            confidence = binding.get("binding_confidence") or {}
            lines.extend(
                [
                    f"- `{stable_ref}` -> {binding.get('field') or '未知 claim'} / "
                    f"{binding.get('missing_layer_label') or binding.get('missing_layer') or '未知层'}；"
                    f"可靠度：{confidence.get('label') or 'unknown'} {confidence.get('score') if confidence.get('score') is not None else 'unknown'}；"
                    f"来源：{confidence.get('source') or 'heuristic'}；"
                    f"信号：{confidence_signal_breakdown_text(confidence, group_limit=4, signal_limit=2)}；"
                    f"关键词：{keywords}；原因：{binding.get('reason') or '无'}",
                ]
            )
        if len(bindings) > 12:
            lines.append(f"- 其余 {len(bindings) - 12} 条绑定已省略。")
        lines.append("")
    return lines


def render_claim_gap_report(gaps: list[dict]) -> list[str]:
    lines = ["## Claim Gap Report", ""]
    if not gaps:
        return lines + ["当前未发现高优先级 claim 支撑缺口。", ""]
    for index, item in enumerate(gaps, 1):
        missing = "、".join(item.get("missing_layer_labels") or []) or "无"
        current = "、".join(item.get("current_layer_labels") or []) or "无"
        lines.extend(
            [
                f"### {index}. {item.get('field') or '未知 claim'}",
                "",
                f"- Claim ID：`{item.get('claim_id') or '无'}`",
                f"- 优先级：{item.get('priority_score', 0)}/100",
                f"- 当前支撑：{item.get('support_label') or '未知'}（{current}，{item.get('support_score', 0)}/100）",
                f"- 缺口层：{missing}",
                f"- 原因：{item.get('gap_reason') or '该判断需要补充更强的工程证据。'}",
                f"- 下一步证据：{item.get('recommendation') or '无'}",
                "",
            ]
        )
    return lines


def build_claims(repo: dict, evidence: list[Evidence]) -> list[Claim]:
    text = corpus(evidence, repo)
    claims = [
        make_claim(
            "领域",
            infer_domain(repo, text),
            matching_evidence(evidence, ["agent", "cli", "local-first", "protocol"]),
            "medium",
            "主题/README/证据标签 -> 领域归类",
            "领域只作为阅读入口，不等于项目价值判断。",
            counter_evidence(evidence, ["deprecated", "no longer", "experimental"]),
        ),
        claim_problem_frame(evidence, repo, text),
        claim_key_abstractions(evidence, text),
        claim_boundaries(evidence, text),
        claim_complexity(evidence, text),
        claim_implementation_layer(evidence),
        claim_governance(evidence, text),
        make_claim(
            "可复用思想",
            "把公开工程工件拆成问题重定义、关键抽象、边界声明、复杂度藏处和治理方式，再把这些模式迁移到自己的设计评审中。",
            [item.evidence_id for item in evidence[:3]],
            "medium",
            "多类证据 -> 方法抽取 -> 迁移边界",
            "只迁移可观察的工程方法，不迁移项目热度、生态位或品牌势能。",
            counter_evidence(evidence, ["bug", "experimental", "deprecated", "no longer"]),
        ),
        make_claim(
            "不可复制条件",
            "热度、生态位、品牌、发布时间窗口和既有社区势能不可直接复制；可迁移的是方法，不是势能本身。",
            [item.evidence_id for item in evidence[:3]],
            "medium",
            "势能来源 -> 不可复制条件 -> 防止错误模仿",
            "把负面/边界证据显式列出，避免把热门项目包装成无条件最佳实践。",
            counter_evidence(evidence, ["bug", "confusing", "unsupported", "deprecated", "experimental"]),
        ),
    ]
    evidence_map = {item.evidence_id: item for item in evidence}
    for claim in claims:
        claim.claim_id = stable_id("claim", repo["full_name"], claim.field)
        claim.support_coverage = claim_support_coverage(claim, evidence_map)
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
                f"- 类型 / 极性：{item.evidence_type} / {item.polarity}",
                f"- 信号标签：{', '.join(item.signal_tags) or '无'}",
                f"- 证据层级：L{item.level}",
                f"- 链接：{item.url or '无'}",
                f"- 摘录：{textwrap.fill(item.quote or '无摘录。', width=88)}",
                "",
            ]
        )
    return lines


def render_deep_report(
    repo: dict,
    summary: dict,
    evidence: list[Evidence],
    claims: list[Claim],
    evidence_acquisition: dict | None = None,
) -> str:
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
                f"- 模板：{claim.template or '无'}",
                f"- 推断依据：{claim.rationale or '无'}",
                f"- 支撑覆盖：{support_coverage_text(claim.support_coverage)}",
                f"- 证据：{evidence_refs(claim.evidence_ids)}",
                f"- 边界/反向证据：{evidence_refs(claim.counter_evidence_ids)}",
                f"- 置信度：{claim.confidence}",
                "",
            ]
        )

    lines.extend(render_evidence_acquisition_summary(evidence_acquisition))
    lines.extend(render_claim_gap_report(build_claim_gap_report(claims)))
    lines.extend(
        [
            "## 风险与复核",
            "",
            f"- Fake-star 风险：{fake_star_risk(repo)}",
            "- 自动复核建议：优先继续采样 README 第一屏、examples、最近 release、高评论 issue、最近合并 PR 和实现层变更。",
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

    if (
        args.archive_list
        or args.archive_search is not None
        or args.archive_show is not None
        or args.archive_patterns
        or args.archive_auto_calibrate
        or args.archive_dashboard is not None
    ):
        handle_archive(args)
        return

    if args.repo:
        repo = fetch_repository(args.repo)
        evidence = build_evidence(repo)
        initial_claims = build_claims(repo, evidence)
        initial_gaps = build_claim_gap_report(initial_claims)
        targeted_evidence, acquisition_bindings = acquire_targeted_evidence(repo, evidence, initial_gaps)
        if targeted_evidence:
            evidence.extend(targeted_evidence)
            assign_evidence_ids(repo, evidence)
        claims = build_claims(repo, evidence)
        bind_acquired_evidence_to_claims(claims, evidence, acquisition_bindings)
        evidence_acquisition = build_evidence_acquisition_summary(initial_gaps, targeted_evidence, acquisition_bindings)
        payload = build_deep_payload(repo, evidence, claims, run_at, evidence_acquisition)
        attach_star_growth([payload["repository"]], None if args.no_db else args.db, run_at)
        attach_track_scores(
            [payload["repository"]],
            evidence_counts={payload["repository"]["full_name"]: len(evidence)},
            claim_counts={payload["repository"]["full_name"]: len(claims)},
        )
        write_report(args.output, render_deep_report(repo, payload["repository"], evidence, claims, evidence_acquisition))
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
