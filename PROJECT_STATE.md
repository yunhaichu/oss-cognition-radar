# Project State

## Current Goal

Build OSS Cognition Radar: a lightweight tool that studies popular open-source repositories as public engineering evidence, then extracts observable, reviewable, and transferable cognition/design/governance patterns.

## Current Phase

The project has pivoted from a simple GitHub hot-project radar to an evidence-backed project dossier generator. Discovery mode still finds candidate repositories; deep mode analyzes one repository through README, docs/examples files, releases, issues, PRs, and governance artifacts. Runs can now be persisted and compared across time.

## Implemented

- `radar.py`: supports discovery mode and `--repo owner/name` deep analysis mode.
- Deep reports include method boundaries, project dossier fields, fake-star risk, confidence labels, and a traceable evidence chain.
- `--json-output`: exports structured discovery results or deep project dossiers.
- SQLite snapshots: stores runs, repository snapshots, evidence items, and claims in `data/radar.sqlite` by default.
- Star growth: reports real 1d/7d/30d star deltas when enough historical SQLite snapshots exist.
- `README.md`: updated for the new OSS Cognition Radar positioning and usage.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- Evidence extraction is heuristic and limited to a small number of files, releases, issues, and PRs.
- No LLM analysis yet; claims are rule-based and should be treated as first-pass research prompts.
- No per-category scoring yet for agent, developer tools, local-first, and protocol projects.
- Star growth depends on repeated snapshots; fresh databases correctly show insufficient history.

## Release Policy

Every pushed commit must have a corresponding GitHub Release. Use a commit-addressed tag such as `rYYYYMMDD-<shortsha>` so each release maps unambiguously to one commit.

## Next Local Step

Add JSON-friendly dossier IDs and richer repository health fields so project cards can become a searchable archive.
