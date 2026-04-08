# Development History

## 2026-04-08

This repository moved from a plan-only state into a working Phase 1 MVP.

Completed work:

- Created the Python project skeleton and package layout.
- Added the CLI entrypoint in `app.py`.
- Implemented unified schema normalization for YouTube community posts.
- Added `state.json` based deduplication.
- Added structured JSON logging support.
- Added adapter abstraction for `primary` and `backup` scrapers.
- Wired the `primary` adapter to the real `post-archiver-improved` package.
- Verified the real fetch path against `@yutinghaofinance`.
- Added Telegram-ready routing fields:
  - `delivery_type`
  - `message_text`
  - `caption`
  - `media`
- Added Telegram safety handling:
  - caption truncation to safe length
  - message chunk splitting
  - follow-up message fields when captions are truncated
- Added fixture-driven tests and sample raw payloads.
- Added a sample n8n workflow JSON.
- Wrote README usage notes for CLI, n8n, and Telegram routing.

Key outcomes:

- `primary` can now fetch a real channel and normalize the result into the project schema.
- The CLI returns exit codes aligned with the development plan:
  - `0` success with new posts
  - `10` success with no new posts
  - `20` failure
- Output is now suitable for downstream Telegram delivery in n8n without requiring heavy reformatting.

Known status:

- Phase 1 MVP is complete.
- Backup scraper integration, SQLite state storage, production deployment, and long-run operations are still future work.
