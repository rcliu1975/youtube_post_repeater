from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StateStore:
    path: Path

    def load_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data.get("last_seen_post_ids", []))

    def save_ids(self, ids: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_seen_post_ids": sorted(ids)}
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True, indent=2)
            fh.write("\n")


def filter_new_posts(posts: list[dict], seen_ids: set[str]) -> tuple[list[dict], set[str]]:
    new_posts = [post for post in posts if post["post_id"] not in seen_ids]
    updated_seen = set(seen_ids)
    for post in posts:
        updated_seen.add(post["post_id"])
    return new_posts, updated_seen
