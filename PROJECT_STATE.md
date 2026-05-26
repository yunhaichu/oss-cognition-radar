# Project State

## Current Goal

Build OSS Cognition Radar: a lightweight tool that studies popular open-source repositories as public engineering evidence, then extracts observable, reviewable, and transferable cognition/design/governance patterns.

## Current Phase

The project has pivoted from a simple GitHub hot-project radar to an evidence-backed project dossier generator. Discovery mode still finds candidate repositories; deep mode analyzes one repository through README, docs/examples files, releases, issues, PRs, and governance artifacts. Runs can now be persisted, compared across time, linked through stable dossier/evidence/claim IDs, and scored by project track.

The archive surface now exists in two forms: local SQLite CLI queries and a standalone HTML dashboard export. Together they move the project from one-off reports toward a searchable dossier archive and browser-based knowledge surface.

## Implemented

- `radar.py`: supports discovery mode and `--repo owner/name` deep analysis mode.
- Deep reports include method boundaries, project dossier fields, fake-star risk, confidence labels, and a traceable evidence chain.
- `--json-output`: exports structured discovery results or deep project dossiers.
- SQLite snapshots: stores runs, repository snapshots, evidence items, and claims in `data/radar.sqlite` by default.
- Star growth: reports real 1d/7d/30d star deltas when enough historical SQLite snapshots exist.
- Stable IDs: adds dossier IDs, claim IDs, evidence stable IDs, and claim-to-evidence stable references for JSON/search use.
- Evidence quality fields: deep evidence now carries `evidence_type`, `polarity`, and `signal_tags`; claims carry `template`, `rationale`, `counter_evidence_ids`, and counter-evidence stable references.
- Repository health: captures 180d merged PR / closed issue counts, open PRs, release sample cadence, and top contributor samples.
- Track scoring: classifies projects as agent, developer tools, local-first, protocol, or general, then applies track-specific weights across momentum, collaboration, release, governance, evidence, and ecosystem signals.
- Archive queries: `--archive-list`, `--archive-search TEXT`, and `--archive-show owner/name` query persisted SQLite snapshots locally, with track and minimum track score filters plus optional Markdown/JSON export.
- FTS archive search: `--archive-search TEXT` now maintains a derived SQLite FTS5 index over repository metadata, claims, and evidence; it returns relevance backend, score, matched document count, and matched source types, with a LIKE fallback if FTS5 is unavailable or misses Chinese substrings.
- Archive dashboard: `--archive-dashboard [PATH]` exports a static HTML dashboard with search, track filtering, minimum score filtering, summary metrics, repository details, claims, and evidence excerpts.
- `README.md`: updated for the new OSS Cognition Radar positioning and usage.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- Evidence extraction is heuristic and limited to a small number of files, releases, issues, and PRs.
- No LLM analysis yet; claims are rule-based and should be treated as first-pass research prompts.
- Evidence type/polarity classification is rule-based and can still misclassify domain-specific wording.
- Star growth depends on repeated snapshots; fresh databases correctly show insufficient history.
- Repository health release/contributor fields are first-pass API samples, not complete longitudinal analytics.
- Track classification is heuristic and should be refined with manually reviewed samples.
- Dashboard search is currently client-side weighted matching over exported JSON; CLI archive search uses SQLite FTS5 ranking.

## Release Policy

Every pushed commit must have a corresponding GitHub Release. Use a commit-addressed tag such as `rYYYYMMDD-<shortsha>` so each release maps unambiguously to one commit.

## Next Local Step

Expand evidence collection into implementation-layer artifacts such as core source entrypoints, tests, benchmarks, and configuration files so claims can be checked against code, not only docs/issues/releases.
