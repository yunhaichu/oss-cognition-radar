# Project State

## Current Goal

Build a lightweight GitHub project radar that studies what developers are building, using popular repositories as evidence for developer taste, priorities, engineering ideas, and deeper design philosophy.

## Current Phase

MVP created. The project is a pure Python standard-library script that queries GitHub REST API and generates a Markdown report. The report is being shaped around "project philosophy analysis", not only popularity ranking.

## Implemented

- `radar.py`: searches recently created GitHub repositories, scores them, fetches README excerpts, infers design-thesis/tradeoff/mental-model notes, and writes a Markdown report.
- `README.md`: documents usage and current scoring logic.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- No historical database yet, so real star growth is approximated by `stars / age_days`.
- No Hacker News, GitHub Trending, YouTube, or newsletter resonance signals yet.
- No AI analysis yet; “philosophy” notes are heuristic and should be treated as prompts for deeper reading.

## Next Local Step

Add deeper evidence extraction from README, examples, recent PRs, and high-signal issues so philosophy inference is grounded in concrete design decisions.
