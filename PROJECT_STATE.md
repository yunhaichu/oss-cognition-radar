# Project State

## Current Goal

Build OSS Cognition Radar: a lightweight tool that studies popular open-source repositories as public engineering evidence, then extracts observable, reviewable, and transferable cognition/design/governance patterns.

## Current Phase

The project has pivoted from a simple GitHub hot-project radar to an evidence-backed project dossier generator. Discovery mode still finds candidate repositories; deep mode analyzes one repository through README, docs/examples files, releases, issues, PRs, and governance artifacts. Runs can now be persisted, compared across time, linked through stable dossier/evidence/claim IDs, and scored by project track.

## Implemented

- `radar.py`: supports discovery mode and `--repo owner/name` deep analysis mode.
- Deep reports include method boundaries, project dossier fields, fake-star risk, confidence labels, and a traceable evidence chain.
- `--json-output`: exports structured discovery results or deep project dossiers.
- SQLite snapshots: stores runs, repository snapshots, evidence items, and claims in `data/radar.sqlite` by default.
- Star growth: reports real 1d/7d/30d star deltas when enough historical SQLite snapshots exist.
- Stable IDs: adds dossier IDs, claim IDs, evidence stable IDs, and claim-to-evidence stable references for JSON/search use.
- Repository health: captures 180d merged PR / closed issue counts, open PRs, release sample cadence, and top contributor samples.
- Track scoring: classifies projects as agent, developer tools, local-first, protocol, or general, then applies track-specific weights across momentum, collaboration, release, governance, evidence, and ecosystem signals.
- `README.md`: updated for the new OSS Cognition Radar positioning and usage.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- Evidence extraction is heuristic and limited to a small number of files, releases, issues, and PRs.
- No LLM analysis yet; claims are rule-based and should be treated as first-pass research prompts.
- Star growth depends on repeated snapshots; fresh databases correctly show insufficient history.
- Repository health release/contributor fields are first-pass API samples, not complete longitudinal analytics.
- Track classification is heuristic and should be refined with manually reviewed samples.

## Release Policy

Every pushed commit must have a corresponding GitHub Release. Use a commit-addressed tag such as `rYYYYMMDD-<shortsha>` so each release maps unambiguously to one commit.

## Next Local Step

Build the first searchable archive surface from JSON/SQLite dossiers, starting with simple CLI/list queries before a UI.
