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
- Implementation-layer evidence: deep mode now samples source entrypoints, tests, benchmarks, and configuration files from the Git tree, then emits an `实现层复核线索` claim so high-level judgments can be checked against code artifacts.
- Claim support coverage: each claim now records whether its direct evidence is narrative-only, collaboration/release backed, configuration backed, source backed, validation backed, or source-plus-validation backed; the field is exported to JSON, SQLite, archive search, Markdown, and the dashboard.
- Claim gap report: deep payloads, Markdown reports, archive show, and the dashboard now rank high-value claims with weak support coverage and recommend the next evidence layer to collect.
- Targeted evidence acquisition: deep mode now runs a second evidence pass based on the initial claim gap report, ranking source/test/benchmark/configuration/release/issue/PR candidates by claim field, missing layer, and claim keywords, then binding added evidence back to the target claim before rebuilding final support coverage.
- Acquisition binding archive: evidence-to-claim acquisition bindings are persisted to SQLite, included in archive search/show payloads, and displayed in the dashboard so each added evidence item can show which claim gap it was collected for.
- Cross-project pattern view: `--archive-patterns` groups persisted acquisition bindings from latest deep dossiers by claim field and missing evidence layer, surfacing repeated claim-gap repair moves with example repositories and evidence.
- Binding confidence: acquisition bindings now carry a heuristic `binding_confidence` score/label/calibration/signals field, persisted in SQLite and surfaced in archive show/search, patterns, and dashboard views.
- Automatic confidence calibration: `--archive-auto-calibrate` recalculates binding confidence from archive-only signals such as cross-project repetition, same-repository cross-version stability/drift, release/issue/PR activity trends, evidence type, polarity, stable URLs, and keyword sparsity, while preserving the original heuristic score.
- Saturation-aware confidence scoring: `archive_auto_v1` now uses separate heuristic, repetition, time-series, evidence-quality, and penalty components plus stricter automatic label thresholds, so popular real projects can produce high/medium/low confidence separation instead of all-high saturation.
- Confidence signal breakdowns: binding confidence now carries a derived `signal_breakdown` grouped into time-series, cross-version drift, archive pattern, evidence quality, and calibration buckets; archive show and dashboard detail views surface those buckets directly from archive signals.
- Signal-ranked archive patterns: `--archive-patterns` now scores and sorts patterns from repetition, average binding confidence, and automatic signal group structure; `--archive-signal-group` and dashboard Signal group filtering can isolate time-series, drift, pattern, or evidence-backed repair moves.
- Semantic pattern normalization: archive patterns now use `semantic_v1` keys that normalize claim fields into cognition categories and evidence layers into evidence families such as implementation/validation, configuration/process, and evolution/collaboration while retaining raw field/layer counts.
- Automatic cognition summaries: `--archive-patterns` and `--archive-dashboard` now derive `cognition_summaries` from signal-ranked archive patterns, including stable summary IDs, cognition move labels, evidence basis, transfer rules, automatic verification actions, confidence, and supporting patterns.
- Repository cognition profiles: `--archive-patterns`, `--archive-dashboard`, and `--archive-show` now derive repository cognition profiles from `semantic_v1` patterns, showing each archived repository's strongest cross-project design moves, evidence families, raw field/layer distribution, and supporting semantic patterns.
- Dashboard patterns: the static dashboard now includes a cross-project patterns band with repeated claim-gap repair moves and average binding confidence.
- Repository health: captures 180d merged PR / closed issue counts, open PRs, release sample cadence, and top contributor samples.
- Track scoring: classifies projects as agent, developer tools, local-first, protocol, or general, then applies track-specific weights across momentum, collaboration, release, governance, evidence, and ecosystem signals.
- Archive queries: `--archive-list`, `--archive-search TEXT`, and `--archive-show owner/name` query persisted SQLite snapshots locally, with track and minimum track score filters plus optional Markdown/JSON export.
- FTS archive search: `--archive-search TEXT` now maintains a derived SQLite FTS5 index over repository metadata, claims, and evidence; it returns relevance backend, score, matched document count, and matched source types, with a LIKE fallback if FTS5 is unavailable or misses Chinese substrings.
- Profile-aware archive search: CLI `--archive-search` now indexes and renders Repository Cognition Profile content, so design moves, evidence families, raw fields/layers, and supporting semantic pattern terms can directly retrieve related repositories through FTS5 or LIKE fallback.
- Profile explanation paths: Repository Cognition Profile evidence examples now carry claim gap fields, acquisition reasons, confidence signals, and evidence references; CLI `--archive-search` renders explanation paths from matched profiles to concrete claim gaps and evidence stable IDs.
- Dashboard profile paths: dashboard repository detail now renders Profile Explanation Paths inside Repository Cognition Profile, linking design moves to claim gap layers, acquisition reasons, confidence signals, and evidence stable IDs.
- Profile path statistics: repository profiles and archive pattern/dashboard payloads now include path-level aggregate statistics grouped by design move, claim gap layer, evidence type, evidence kind, confidence label, and signal group.
- Profile path comparisons: `--archive-patterns` and `--archive-dashboard` now include cross-repository comparison views for profile explanation paths, grouping the same design move by evidence route across claim gap layer and evidence type.
- Profile path comparison drilldown: the dashboard now has dedicated filters for comparison design move, evidence route, and repository, while still honoring search, confidence source, and signal group filters.
- Archive dashboard: `--archive-dashboard [PATH]` exports a static HTML dashboard with search, track filtering, confidence source filtering, minimum score filtering, summary metrics, repository details, claims, and evidence excerpts.
- `README.md`: updated for the new OSS Cognition Radar positioning and usage.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- Evidence extraction is heuristic and limited to a small number of files, releases, issues, and PRs.
- No LLM analysis yet; claims are rule-based and should be treated as first-pass research prompts.
- Evidence type/polarity classification is rule-based and can still misclassify domain-specific wording.
- Implementation-layer file selection is heuristic and may miss the true core module in unusual repository layouts.
- Support coverage reflects evidence linked to each claim; targeted bindings can now add missing-layer evidence, but those bindings are still heuristic and can over-associate broad artifacts.
- Binding confidence calibration is fully automatic and rule-based; `archive_auto_v1` now has saturation-aware component scoring, but its weights are still deterministic first-pass heuristics.
- Cross-project pattern and cognition summary grouping now has first-pass deterministic semantic normalization, but equivalent moves can still be split if the field wording or evidence layer falls outside the current rule set.
- Star growth depends on repeated snapshots; fresh databases correctly show insufficient history.
- Repository health release/contributor fields are first-pass API samples, not complete longitudinal analytics.
- Track classification is heuristic and should be refined with stronger automatic repository behavior signals.
- Dashboard search is currently client-side weighted matching over exported JSON and now includes profile path comparison cards; CLI archive search uses SQLite FTS5 ranking plus profile-aware LIKE fallback.

## Release Policy

Every pushed commit must have a corresponding GitHub Release. Use a commit-addressed tag such as `rYYYYMMDD-<shortsha>` so each release maps unambiguously to one commit.

## Next Local Step

Add a route detail panel or export for profile path comparison drilldown results so one evidence route can expand into full repository examples and evidence stable IDs.
