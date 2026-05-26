# Project State

## Current Goal

Build a lightweight GitHub project radar that studies what developers are building, using popular repositories as signals for developer taste, priorities, and engineering ideas.

## Current Phase

MVP created. The project is a pure Python standard-library script that queries GitHub REST API and generates a Markdown report.

## Implemented

- `radar.py`: searches recently created GitHub repositories, scores them, fetches README excerpts, and writes a Markdown report.
- `README.md`: documents usage and current scoring logic.
- `.gitignore`: ignores generated reports and local files.

## Known Limits

- No historical database yet, so real star growth is approximated by `stars / age_days`.
- No Hacker News, GitHub Trending, YouTube, or newsletter resonance signals yet.
- No AI analysis yet; “developer thought” notes are heuristic.

## Next Local Step

Add SQLite snapshots so future reports can rank real 1-day, 7-day, and 30-day star growth instead of relying on creation-time approximation.
