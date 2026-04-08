# youtube_post_repeater

Phase 1 MVP for fetching YouTube community posts, normalizing them into a
stable JSON schema, deduplicating against local state, and returning output
that n8n can consume directly for Telegram delivery.

## Current scope

This repository currently implements:

- A CLI entrypoint: `python app.py`
- A stable normalized JSON response
- Primary and backup source adapters behind one interface
- Deduplication using `state.json`
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
- `--fixture-file <path>` for local development and tests
- `--log-file <path>`

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

The command must print JSON to stdout. The repository includes normalization
logic to map that JSON into the unified schema.

## n8n integration

Recommended `Execute Command` step:

```bash
cd /path/to/youtube_post_repeater
python app.py \
  --source primary \
  --channel https://www.youtube.com/@CHANNEL/community \
  --limit 3 \
  --json \
  --state-file ./state.json \
  --log-file ./logs/latest.jsonl
```

Expected behavior:

- Exit code `0`: proceed to Telegram routing
- Exit code `10`: no new posts, stop quietly
- Exit code `20`: record error and alert if needed

Telegram routing suggestion:

- `delivery_type == "message"` -> Send Message using `message_chunks`
- `delivery_type == "photo"` -> Send Photo using `images[0]` and `caption`
- `delivery_type == "media_group"` -> Send Media Group using `media`
- if `followup_message_chunks` is non-empty, send those as one or more extra `Send Message` steps

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

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
