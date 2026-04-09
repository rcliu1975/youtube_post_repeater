# youtube_post_repeater

Phase 1 MVP for fetching YouTube community posts, normalizing them into a
stable JSON schema, deduplicating against local state, and returning output
that n8n can consume directly for Telegram delivery.

## Current scope

This repository currently implements:

- A CLI entrypoint: `python app.py`
- A stable normalized JSON response
- Primary and backup source adapters behind one interface
- Deduplication using JSON or SQLite state storage
- Structured JSON logging
- Exit codes compatible with scheduler / n8n workflows
- Telegram-ready routing fields per post
- Fixture-driven tests and sample input/output

The real scraper integrations are intentionally isolated behind adapter
classes, so the MVP can be tested and extended without rewriting the CLI or
the n8n flow.

## CLI

```bash
python app.py --source primary --channel https://www.youtube.com/@CHANNEL/community --limit 3 --json
```

Useful options:

- `--source primary|backup`
- `--channel <url-or-handle>`
- `--limit <n>`
- `--json`
- `--state-file <path>`
- `--state-backend auto|json|sqlite`
- `--fixture-file <path>` for local development and tests
- `--log-file <path>`

## State storage

State storage defaults to `auto` mode:

- `.json` paths use JSON storage
- `.db`, `.sqlite`, `.sqlite3` paths use SQLite storage

You can also force a backend explicitly:

```bash
python app.py --state-file ./state.sqlite3 --state-backend sqlite
```

## Exit codes

- `0`: success with at least one new post
- `10`: success but no new posts
- `20`: scraper or normalization failure

## JSON schema

```json
{
  "ok": true,
  "source": "primary",
  "channel": "channel-name",
  "fetched_at": "2026-04-08T10:40:00+00:00",
  "posts": [
    {
      "post_id": "abc123",
      "post_url": "https://www.youtube.com/post/abc123",
      "text": "Tonight at 8 PM",
      "images": [
        "https://example.com/image.jpg"
      ],
      "video_links": [],
      "published_text": "2 hours ago",
      "is_members_only": false,
      "delivery_type": "photo",
      "full_text": "Tonight at 8 PM\n\n🔗 https://www.youtube.com/post/abc123",
      "message_text": "Tonight at 8 PM\n\n🔗 https://www.youtube.com/post/abc123",
      "caption": "Tonight at 8 PM\n\n🔗 https://www.youtube.com/post/abc123",
      "caption_was_truncated": false,
      "message_chunks": [
        "Tonight at 8 PM\n\n🔗 https://www.youtube.com/post/abc123"
      ],
      "followup_message_text": "",
      "followup_message_chunks": [],
      "media": []
    }
  ]
}
```

## Adapter strategy

Two adapters exist:

- `primary`: intended for `sadadYes/post-archiver-improved`
- `backup`: intended for `NothingNaN/YoutubeCommunityScraper`

At the moment they support:

- Fixture-driven local development via `--fixture-file`
- Environment-variable based command delegation

You can wire a real scraper into the CLI without changing the output schema by
setting one of these environment variables:

- `YPR_PRIMARY_COMMAND`
- `YPR_BACKUP_COMMAND`

The command must print JSON to stdout. Command strings may include arguments,
for example:

```bash
export YPR_PRIMARY_COMMAND="python3 /opt/scrapers/fetch_posts.py --format json"
```

The CLI appends `<channel> <limit>` to the configured command. The repository
includes normalization logic to map that JSON into the unified schema.

## n8n integration

Recommended `Execute Command` step:

```bash
bash -lc 'cd /workspace/youtube_post_repeater && \
python3 app.py \
  --source primary \
  --channel https://www.youtube.com/@CHANNEL/community \
  --limit 3 \
  --json \
  --state-file ./state.sqlite3 \
  --state-backend sqlite \
  --log-file ./logs/latest.jsonl; \
status=$?; \
if [ "$status" -eq 10 ]; then exit 0; fi; \
exit "$status"'
```

If your n8n runs in Docker, the container must have:

- `python3` available
- this repository mounted into the container

This repository includes a minimal n8n image and rebuild script template:

- `deploy/n8n/Dockerfile.n8n-python`
- `deploy/n8n/n8n.env.example`
- `deploy/n8n/update-n8n-webhook.sh.example`

Example image build:

```bash
docker build -t n8n-python:latest -f deploy/n8n/Dockerfile.n8n-python .
```

The example webhook rebuild script mounts:

- `/home/roger/.n8n` -> `/home/node/.n8n`
- `/home/roger/WorkSpace/youtube_post_repeater` -> `/workspace/youtube_post_repeater`
- `/home/roger/WorkSpace/youtube_post_repeater` -> `/home/roger/WorkSpace/youtube_post_repeater`

The second repository mount preserves the original virtualenv shebang path used by `.venv/bin/post-archiver`.

Suggested environment variables for Docker n8n:

```bash
cp deploy/n8n/n8n.env.example /home/roger/n8n-stack/youtube-post-repeater.env
```

The example `update-n8n-webhook.sh.example` script will automatically load
that file via `YPR_ENV_FILE` before starting the container.

Populate at least:

- `TELEGRAM_CHAT_ID`
- `YPR_CHANNEL`

Optional overrides:

- `YPR_FETCH_LIMIT`
- `YPR_STATE_FILE`
- `YPR_STATE_BACKEND`
- `YPR_LOG_FILE`
- `YPR_PRIMARY_BIN`

Expected behavior:

- Exit code `0`: proceed to Telegram routing
- Exit code `10`: no new posts, but the wrapper command above converts it to `0` so n8n does not fail the workflow
- Exit code `20`: record error and alert if needed

Telegram routing suggestion:

- `delivery_type == "message"` -> Send Message using `message_chunks`
- `delivery_type == "photo"` -> Send Photo using `images[0]` and `caption`
- `delivery_type == "media_group"` -> Send Media Group using `media`
- if `followup_message_chunks` is non-empty, send those as one or more extra `Send Message` steps

Suggested import flow for `workflows/n8n-sample-workflow.json`:

1. Import the workflow JSON into n8n.
2. Attach your Telegram credentials to all Telegram nodes.
3. Set `TELEGRAM_CHAT_ID` and the `YPR_*` environment variables in the n8n
   container environment, or replace those expressions with fixed values.
4. Confirm the `Run CLI` node can read the configured environment variables.
5. Test from the `Manual Trigger` branch first, then enable the schedule once
   the Telegram output is correct.

The sample workflow now includes a failure-notification branch:

- CLI exit code `20`, or `ok: false` in the JSON payload, sends a Telegram
  alert using the same `TELEGRAM_CHAT_ID`
- CLI exit code `10` emits no post items and stops quietly without an alert

For production deployment, import `workflows/n8n-production-workflow.json`
after you have validated the same settings with the sample workflow.

Telegram safety behavior:

- `caption` is capped to 1024 chars
- `message_chunks` are split to 4096-char safe chunks
- `followup_message_chunks` is populated when a photo/media-group caption had to be truncated

## Sample output for n8n

See:

- `tests/fixtures/primary_raw.json`
- `tests/fixtures/backup_raw.json`
- `tests/fixtures/expected_primary_output.json`
- `workflows/n8n-sample-workflow.json`
- `workflows/n8n-production-workflow.json`

Workflow file roles:

- `workflows/n8n-sample-workflow.json`: includes `Manual Trigger` for editor-side testing
- `workflows/n8n-production-workflow.json`: schedule-only version intended for deployed use

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
