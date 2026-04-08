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
- Added optional SQLite state storage alongside `state.json`.
- Added test coverage for SQLite-backed deduplication.
- Added Dockerized n8n deployment artifacts for running the CLI inside the n8n container.

Key outcomes:

- `primary` can now fetch a real channel and normalize the result into the project schema.
- The CLI returns exit codes aligned with the development plan:
  - `0` success with new posts
  - `10` success with no new posts
  - `20` failure
- Output is now suitable for downstream Telegram delivery in n8n without requiring heavy reformatting.

Known status:

- Phase 1 MVP is complete.
- Backup scraper integration, production deployment, and long-run operations are still future work.

## 2026-04-09

This repository was integrated into a Dockerized n8n environment and verified
against a real channel fetch path.

Completed work:

- Investigated the user's existing Docker-based n8n deployment notes and live
  container configuration.
- Confirmed the running `n8n` container did not initially include Python and
  could not execute the scraper directly.
- Added and iterated on `deploy/n8n/Dockerfile.n8n-python` so the image now
  includes:
  - Python 3.12 runtime
  - SQLite shared libraries
  - `/usr/bin/python3` compatibility symlink
  - `post-archiver-improved==0.4.0`
- Added and updated `deploy/n8n/update-n8n-webhook.sh.example` for Docker n8n
  deployments that need:
  - repo mount at `/workspace/youtube_post_repeater`
  - compatibility mount at `/home/roger/WorkSpace/youtube_post_repeater`
- Updated README and sample workflow to reflect Docker n8n execution details.
- Backed up and updated the live host files:
  - `/home/roger/n8n-stack/.env`
  - `/home/roger/n8n-stack/update-n8n-webhook.sh`
- Rebuilt the live `n8n` container multiple times to apply:
  - the `n8n-python:latest` image
  - repository mounts
  - `Execute Command` node visibility settings
- Enabled `Execute Command` visibility in the live n8n container by passing:
  - `NODES_EXCLUDE=[]`
  - `N8N_BLOCK_SVC_EXECUTION_FROM_COMMAND=false`
- Verified inside the running `n8n` container that:
  - `python3` is available
  - the repository is mounted correctly
  - SQLite-backed state storage works
  - fixture-based adapter execution works
- Identified and resolved the real-fetch execution issues in order:
  - missing Python runtime
  - missing SQLite shared library
  - broken virtualenv shebang path compatibility
  - missing `post_archiver_improved` package inside the container image
- Verified real fetching for `@yutinghaofinance` from inside the Docker n8n
  container using:
  - `YPR_PRIMARY_BIN=/usr/local/bin/post-archiver`
- Verified that the n8n `Execute Command` node can now successfully execute the
  CLI command from the UI.

Key outcomes:

- The project now runs inside the user's Dockerized n8n environment instead of
  only from the host shell.
- Real channel fetching for `@yutinghaofinance` was confirmed from inside the
  container.
- The required `Execute Command` node is visible and working in the user's n8n
  UI.
- The correct n8n command for real execution is now:
  - `sh -lc 'cd /workspace/youtube_post_repeater && YPR_PRIMARY_BIN=/usr/local/bin/post-archiver python3 app.py --source primary --channel @yutinghaofinance --limit 1 --json --state-file ./state-test.sqlite3 --state-backend sqlite --log-file ./logs/latest.jsonl; status=$?; if [ "$status" -eq 10 ]; then exit 0; fi; exit "$status"'`

Known status:

- Docker n8n integration is now operational.
- The minimal path `Manual Trigger -> Execute Command -> Code` is working.
- Telegram delivery nodes still need to be finalized in n8n.
- Backup scraper integration and longer-run production hardening are still
  future work.
