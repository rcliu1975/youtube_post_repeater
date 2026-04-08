from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from youtube_post_repeater.adapters import AdapterError, FetchRequest, get_adapter
from youtube_post_repeater.logging_utils import JsonLogger, utc_now_iso
from youtube_post_repeater.schema import normalize_posts
from youtube_post_repeater.state import StateStore, filter_new_posts

EXIT_OK = 0
EXIT_NO_NEW_POSTS = 10
EXIT_FAILURE = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube community post repeater")
    parser.add_argument("--source", choices=["primary", "backup"], default="primary")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument("--state-file", default="state.json")
    parser.add_argument("--state-backend", choices=["auto", "json", "sqlite"], default="auto")
    parser.add_argument("--fixture-file")
    parser.add_argument("--log-file")
    return parser


def _extract_posts(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    posts = raw_payload.get("posts")
    if isinstance(posts, list):
        return [item for item in posts if isinstance(item, dict)]
    if isinstance(raw_payload, list):
        return [item for item in raw_payload if isinstance(item, dict)]
    raise AdapterError("adapter payload does not include a valid posts list")


def _extract_channel(raw_payload: dict[str, Any], fallback_channel: str) -> str:
    value = raw_payload.get("channel")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback_channel


def make_success_payload(
    *,
    source: str,
    channel: str,
    posts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": True,
        "source": source,
        "channel": channel,
        "fetched_at": utc_now_iso(),
        "posts": posts,
    }


def make_error_payload(*, source: str, channel: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": source,
        "channel": channel,
        "fetched_at": utc_now_iso(),
        "error": message,
        "posts": [],
    }


def emit_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = JsonLogger(Path(args.log_file) if args.log_file else None)
    state_store = StateStore(Path(args.state_file), backend=args.state_backend)
    request = FetchRequest(
        channel=args.channel,
        limit=args.limit,
        fixture_file=Path(args.fixture_file) if args.fixture_file else None,
    )

    try:
        adapter = get_adapter(args.source)
        logger.emit("info", "fetch_started", source=args.source, channel=args.channel, limit=args.limit)
        raw_payload = adapter.fetch(request)
        normalized = [post.to_dict() for post in normalize_posts(_extract_posts(raw_payload))]
        channel = _extract_channel(raw_payload, args.channel)
        seen_ids = state_store.load_ids()
        new_posts, updated_seen = filter_new_posts(normalized, seen_ids)
        state_store.save_ids(updated_seen)
        payload = make_success_payload(source=args.source, channel=channel, posts=new_posts)
        logger.emit(
            "info",
            "fetch_finished",
            source=args.source,
            channel=channel,
            total_posts=len(normalized),
            new_posts=len(new_posts),
        )
        emit_payload(payload, args.emit_json)
        return EXIT_OK if new_posts else EXIT_NO_NEW_POSTS
    except Exception as exc:  # broad by design for CLI error wrapping
        logger.emit(
            "error",
            "fetch_failed",
            source=args.source,
            channel=args.channel,
            error=str(exc),
        )
        payload = make_error_payload(source=args.source, channel=args.channel, message=str(exc))
        emit_payload(payload, args.emit_json)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
