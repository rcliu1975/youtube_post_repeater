from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
TRUNCATION_MARKER = "\n\n...[truncated]"


@dataclass(frozen=True)
class NormalizedPost:
    post_id: str
    post_url: str
    text: str
    images: list[str]
    video_links: list[str]
    published_text: str
    is_members_only: bool

    def to_dict(self) -> dict[str, Any]:
        base = {
            "post_id": self.post_id,
            "post_url": self.post_url,
            "text": self.text,
            "images": list(self.images),
            "video_links": list(self.video_links),
            "published_text": self.published_text,
            "is_members_only": self.is_members_only,
        }
        base.update(build_delivery_fields(base))
        return base


def build_delivery_fields(post: dict[str, Any]) -> dict[str, Any]:
    images = list(post.get("images", []))
    text = _normalize_string(post.get("text"))
    post_url = _normalize_string(post.get("post_url"))

    lines = []
    if text:
        lines.append(text)
    if post_url:
        lines.extend(["", f"🔗 {post_url}"])
    rendered_text = "\n".join(lines).strip()
    message_chunks = split_for_telegram(rendered_text, TELEGRAM_MESSAGE_LIMIT)
    safe_message_text = message_chunks[0] if message_chunks else ""

    if len(images) == 0:
        delivery_type = "message"
    elif len(images) == 1:
        delivery_type = "photo"
    else:
        delivery_type = "media_group"

    safe_caption, caption_was_truncated = truncate_for_telegram(rendered_text, TELEGRAM_CAPTION_LIMIT)
    media = []
    if delivery_type == "media_group":
        for index, image_url in enumerate(images):
            item = {"type": "photo", "media": image_url}
            if index == 0 and safe_caption:
                item["caption"] = safe_caption
            media.append(item)

    caption = safe_caption if delivery_type in {"photo", "media_group"} else ""
    followup_message_chunks = message_chunks if delivery_type == "message" else []
    if delivery_type in {"photo", "media_group"} and rendered_text:
        followup_message_chunks = split_for_telegram(rendered_text, TELEGRAM_MESSAGE_LIMIT) if caption_was_truncated else []

    return {
        "delivery_type": delivery_type,
        "full_text": rendered_text,
        "message_text": safe_message_text,
        "caption": caption,
        "caption_was_truncated": caption_was_truncated,
        "message_chunks": message_chunks,
        "followup_message_text": followup_message_chunks[0] if followup_message_chunks else "",
        "followup_message_chunks": followup_message_chunks,
        "media": media,
    }


def truncate_for_telegram(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    usable = max(0, limit - len(TRUNCATION_MARKER))
    truncated = text[:usable].rstrip()
    return truncated + TRUNCATION_MARKER, True


def split_for_telegram(text: str, limit: int) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1 or split_at < limit // 2:
            split_at = limit
        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:limit]
            split_at = limit
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _normalize_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        normalized_items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                candidate = _normalize_string(
                    item.get("src") or item.get("url") or item.get("href") or item.get("link")
                )
            else:
                candidate = _normalize_string(item)
            if candidate:
                normalized_items.append(candidate)
        return normalized_items
    normalized = _normalize_string(value)
    return [normalized] if normalized else []


def fallback_post_id(*, post_url: str, text: str, published_text: str, first_image: str) -> str:
    digest = hashlib.sha256(
        "|".join([post_url, text, first_image, published_text]).encode("utf-8")
    ).hexdigest()
    return f"hash-{digest[:16]}"


def normalize_post(raw_post: dict[str, Any]) -> NormalizedPost:
    post_url = _normalize_string(
        raw_post.get("post_url") or raw_post.get("post_link") or raw_post.get("url")
    )
    text = _normalize_string(raw_post.get("text") or raw_post.get("text_content") or raw_post.get("content"))
    images = _normalize_string_list(raw_post.get("images") or raw_post.get("image_links"))
    video_links = _normalize_string_list(
        raw_post.get("video_links") or raw_post.get("video_link") or raw_post.get("links")
    )
    published_text = _normalize_string(
        raw_post.get("published_text") or raw_post.get("published") or raw_post.get("timestamp")
    )
    is_members_only = bool(raw_post.get("is_members_only", raw_post.get("members_only", False)))

    post_id = _normalize_string(raw_post.get("post_id"))
    if not post_id and post_url:
        post_id = post_url.rstrip("/").split("/")[-1]
    if not post_url and post_id:
        post_url = f"https://www.youtube.com/post/{post_id}"
    if not post_id:
        post_id = fallback_post_id(
            post_url=post_url,
            text=text,
            published_text=published_text,
            first_image=images[0] if images else "",
        )

    return NormalizedPost(
        post_id=post_id,
        post_url=post_url,
        text=text,
        images=images,
        video_links=video_links,
        published_text=published_text,
        is_members_only=is_members_only,
    )


def normalize_posts(raw_posts: list[dict[str, Any]]) -> list[NormalizedPost]:
    return [normalize_post(item) for item in raw_posts]
