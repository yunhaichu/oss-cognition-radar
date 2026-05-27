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
- Route detail drilldown: dashboard profile path comparisons now retain full route examples and expose a detail panel with repository examples, confidence signals, route IDs, path/pattern IDs, and evidence stable IDs for the selected design move/route/repository scope.
- Route detail export: dashboard route detail drilldown can export the current scope as `route_detail_drilldown_v1` JSON or Markdown, preserving filters, evidence routes, repository examples, path/pattern IDs, confidence signals, and evidence stable IDs.
- Dashboard permalink state: dashboard route detail drilldown filters are serialized into URL hash state and restored on load, covering search, track, confidence source, signal group, score, design move, evidence route, and repository scope.
- CLI route detail export: `--archive-route-detail` exports the same `route_detail_drilldown_v1` research payload in Markdown and JSON, with filters for design move, evidence route, repository, confidence source, signal group, track, and track score.
- CLI route selector listing: `--archive-route-selectors` exports `route_detail_selectors_v1`, listing valid design move, evidence route, and repository selector values for route detail batch exports.
- Dashboard route selector export: `--archive-dashboard` JSON now embeds the same `route_detail_selectors_v1` structure and selector statistics so browser and CLI route detail selector payloads stay aligned.
- Dashboard selector-driven drilldown: dashboard design move, evidence route, and repository option lists now prefer `route_detail_selectors_v1`, and dashboard search includes selector values such as move keys, route IDs, route labels, and repository options.
- Route detail selector presets: `--archive-route-selectors` JSON now includes `route_detail_selector_preset_bundle_v1`, and `--archive-route-detail --profile-path-preset PATH` can batch-run saved selector presets with optional preset ID selection.
- Dashboard route detail preset bundle: dashboard route detail JSON exports now embed `route_detail_selector_preset_bundle_v1`, so browser-exported drilldowns can be reused by CLI `--profile-path-preset`.
- Route detail preset validation: preset batch exports now include `route_detail_preset_validation_v1`, summarizing ready/unmatched presets, duplicate preset IDs, and expected route/example counts before exports are rendered.
- Route detail preset validation fixtures: `--archive-route-selectors` JSON now includes `route_detail_preset_validation_fixtures_v1`, and `--archive-route-detail --profile-path-preset-fixture ID` can run built-in missing move, missing route, missing repo, and duplicate ID coverage paths.
- Dashboard route detail validation fixtures: browser route detail JSON and Markdown exports now embed `route_detail_preset_validation_fixtures_v1`, so dashboard exports can feed `--profile-path-preset-fixture` without a separate selector export.
- Dashboard fixture bundle downloads: route detail drilldown now has a validation fixture selector plus JSON/Markdown controls for downloading a single fixture's `route_detail_selector_preset_bundle_v1` with fixture metadata preserved for CLI roundtrips.
- Dashboard fixture validation preview: selecting a route detail validation fixture now renders an inline `route_detail_preset_validation_v1` summary with status, ready/unmatched counts, duplicate IDs, and expected route/example counts before export.
- Dashboard fixture validation metadata: route detail JSON exports now persist each fixture's validation summary, actual status, expected-status match flag, status distribution, and matching-expected counts.
- Dashboard fixture status filtering: route detail drilldown now has a fixture validation status filter that narrows exported validation fixtures, fixture selectors, previews, JSON/Markdown exports, and permalink state.
- CLI fixture status parity: `--archive-route-detail --profile-path-preset-fixture` now preserves dashboard-exported fixture status filters, validation status, expected-status match flags, and status counts in preset export payloads.
- Selector fixture status metadata: direct `--archive-route-selectors` outputs now annotate validation fixtures with validation summaries, actual status, expected-status match flags, matching-expected counts, and status distributions.
- Selector fixture status filtering: `--archive-route-selectors --validation-fixture-status STATUS` filters validation fixtures by actual status while preserving unfiltered status counts and matching-expected totals.
- Selector fixture roundtrip provenance: downstream `--archive-route-detail --profile-path-preset-fixture` exports now preserve selector fixture filters, filtered/unfiltered fixture counts, matching-expected counts, and status distributions from filtered selector sources.
- Dashboard fixture bundle provenance: dashboard single fixture bundle JSON/Markdown now preserves source selector filters, filtered/unfiltered fixture counts, matching-expected counts, and status distributions for CLI roundtrips.
- Dashboard fixture provenance rendering: route detail Markdown exports and inline fixture previews now surface fixture status filters, filtered/unfiltered counts, matching-expected counts, and status distributions.
- Selector fixture provenance rendering: CLI `--archive-route-selectors` Markdown now surfaces fixture source, status filters, filtered/unfiltered counts, matching-expected counts, and filtered/all status distributions.
- Route selector provenance regression coverage: `tests/test_route_selector_provenance.py` verifies filtered fixture Markdown provenance for blocked, duplicate ID, and empty ready scopes without requiring a SQLite archive.
- Route detail preset fixture provenance regression coverage: `tests/test_route_detail_preset_provenance.py` verifies selector fixture and dashboard single-fixture bundle roundtrips preserve source filters, filtered/unfiltered counts, matching-expected counts, validation status, and status distributions.
- Preset fixture error-path regression coverage: `tests/test_route_detail_preset_provenance.py` verifies missing fixture IDs report available fixtures, missing preset IDs report unknown IDs, and preset ID selection returns only requested presets.
- Fixture-driven preset batch regression coverage: `tests/test_route_detail_preset_provenance.py` verifies fixture-selected preset batches preserve provenance through `archive_route_detail_preset_exports_payload`, run each preset with its selectors, aggregate route/example/repository/evidence summaries, and render provenance in Markdown.
- Preset-ID scoped fixture batch regression coverage: `tests/test_route_detail_preset_provenance.py` verifies `--profile-path-preset-id` narrows fixture-driven preset batches to requested presets while preserving source fixture provenance, validation summary, aggregate export counts, and Markdown output.
- Multi-preset Markdown regression coverage: `tests/test_route_detail_preset_provenance.py` verifies multiple selected preset IDs render both selected preset sections in route detail preset export Markdown while excluding unselected fixture presets.
- Source-filtered preset args: fixture-driven preset exports now carry selector/dashboard source filters such as confidence source, signal group, track, and minimum score into each route detail preset run before applying the preset-specific move/route/repository selectors.
- Source-filter precedence regression coverage: `tests/test_route_detail_preset_provenance.py` verifies preset move/route/repository selectors override conflicting source path filters while still inheriting non-path source filters.
- Dashboard single-fixture preset arg regression coverage: `tests/test_route_detail_preset_provenance.py` verifies dashboard-downloaded single fixture bundles carry source selector filters into route detail preset args without requiring selector fixture extraction.
- Dashboard single-fixture source path precedence regression coverage: `tests/test_route_detail_preset_provenance.py` verifies dashboard-downloaded fixture path filters cannot override preset move/route/repository selectors while non-path filters still carry into route detail args.
- Preset export Markdown source filter rendering: route detail preset export Markdown now renders complete source selector filters as stable `key=value` provenance, with regression coverage for confidence source, signal group, track, score, and path selectors.
- Dashboard single-fixture preset export Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies dashboard-downloaded single fixture preset exports render complete source selector filter provenance in Markdown.
- Dashboard single-fixture conflicting path Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies dashboard-downloaded conflicting path filters remain visible in preset export Markdown provenance even when preset selectors override them for execution.
- Fixture-driven conflicting path Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies selector fixture source path filters remain visible in preset export Markdown provenance even when preset selectors override them for execution.
- Empty source selector filter Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown renders empty source selector filters and fixture filters as explicit empty provenance instead of dropping the fields.
- Source fixture status fallback Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown uses `source_fixture_status_filter` as the selector fixture filter fallback when source selector filters are empty.
- Missing source fixture count Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown renders missing fixture counts and matching-expected counts as explicit unknown provenance.
- Empty fixture status count Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown renders empty fixture status count maps as explicit empty provenance.
- Fixture status count ordering Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown renders populated fixture status count maps in stable sorted order.
- Requested preset IDs Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies preset export Markdown renders requested preset ID scopes, including empty and populated requested preset IDs.
- Selected preset count consistency Markdown coverage: route detail preset export Markdown now renders whether validation selected preset count matches summary preset count, with regression coverage for matching and mismatched counts.
- Expected route/example count consistency Markdown coverage: route detail preset export Markdown now renders whether validation expected route/example counts match summary route/example counts, with regression coverage for matching and mismatched counts.
- Repository/evidence count consistency Markdown coverage: route detail preset export Markdown now derives repository and evidence counts from exported routes and renders whether they match summary repository/evidence counts, with regression coverage for matching and mismatched counts.
- Per-export route/example count consistency Markdown coverage: each route detail preset export section now derives route/example counts from its own routes and renders whether they match that export's summary counts, with regression coverage for matching and mismatched counts.
- Per-export repository/evidence count consistency Markdown coverage: each route detail preset export section now derives repository/evidence counts from its own routes and renders whether they match that export's summary counts, with regression coverage for matching and mismatched counts.
- Per-route evidence/example count consistency Markdown coverage: each route entry inside preset export Markdown now derives example and unique evidence counts from route examples and renders whether they match route-level counts, with regression coverage for matching and mismatched counts.
- Per-route repository count consistency Markdown coverage: each route entry inside preset export Markdown now derives unique repository counts from route repositories and renders whether they match route-level repository counts, with regression coverage for matching and mismatched counts.
- Missing route count fallback Markdown coverage: `tests/test_route_detail_preset_provenance.py` verifies route-level consistency rendering falls back to path count or derived repository/evidence counts when explicit route counts are missing.
- Missing export summary count fallback Markdown coverage: route detail preset export Markdown now falls back to per-export derived route/example/repository/evidence counts when export summary counts are missing, with regression coverage for fully and partially missing export summaries.
- Missing top-level summary count fallback Markdown coverage: route detail preset export Markdown now falls back to derived preset/route/example/repository/evidence counts when top-level summary counts are missing, with regression coverage for fully and partially missing top-level summaries.
- Explicit zero summary count Markdown coverage: route detail preset export Markdown now has regression coverage that preserves explicit zero top-level and per-export summary counts instead of treating them as missing values.
- Explicit zero route-level count Markdown coverage: route detail preset export Markdown now has regression coverage that preserves explicit zero route-level repository/example/evidence counts instead of falling back to path or derived counts.
- Missing validation count Markdown coverage: route detail preset export Markdown now has regression coverage that defaults missing validation count fields to zero and still compares them against derived summary counts.
- Explicit zero validation count Markdown coverage: route detail preset export Markdown now has regression coverage that preserves explicit zero validation count fields while still comparing them against derived summary counts.
- Missing validation preset status count Markdown coverage: route detail preset export Markdown now has regression coverage that defaults missing per-preset validation status move/route/repository/example counts to zero.
- Explicit zero validation preset status count Markdown coverage: route detail preset export Markdown now has regression coverage that preserves explicit zero per-preset validation status move/route/repository/example counts.
- Missing validation preset status identity Markdown coverage: route detail preset export Markdown now has regression coverage for missing per-preset validation status preset ID and status fields.
- Missing validation preset status message Markdown coverage: route detail preset export Markdown now has regression coverage that defaults missing per-preset validation status messages to an empty message suffix.
- Empty validation preset status message Markdown coverage: route detail preset export Markdown now has regression coverage that preserves explicitly empty per-preset validation status messages as an empty message suffix.
- Multi-message validation preset status Markdown coverage: route detail preset export Markdown now has regression coverage that joins multiple per-preset validation status messages with a stable semicolon separator.
- Validation preset status truncation Markdown coverage: route detail preset export Markdown now has regression coverage that limits rendered per-preset validation statuses to twelve entries and reports the remaining JSON-only count.
- Validation preset status truncation boundary Markdown coverage: route detail preset export Markdown now has regression coverage that exactly twelve validation preset statuses render without an overflow notice.
- Empty validation preset status list Markdown coverage: route detail preset export Markdown now has regression coverage that explicitly empty validation preset status lists render no status rows and no overflow notice.
- Missing validation preset status list Markdown coverage: route detail preset export Markdown now has regression coverage that missing validation preset status lists render no status rows and no overflow notice.
- Null validation preset status list Markdown coverage: route detail preset export Markdown now has regression coverage that null validation preset status lists render no status rows and no overflow notice.
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

Add preset export Markdown malformed validation preset status list coverage.
