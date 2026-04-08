from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StateStore:
    path: Path
    backend: str = "auto"

    def _resolved_backend(self) -> str:
        if self.backend in {"json", "sqlite"}:
            return self.backend
        if self.path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            return "sqlite"
        return "json"

    def load_ids(self) -> set[str]:
        backend = self._resolved_backend()
        if backend == "sqlite":
            return self._load_ids_sqlite()
        return self._load_ids_json()

    def save_ids(self, ids: set[str]) -> None:
        backend = self._resolved_backend()
        if backend == "sqlite":
            self._save_ids_sqlite(ids)
            return
        self._save_ids_json(ids)

    def _load_ids_json(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data.get("last_seen_post_ids", []))

    def _save_ids_json(self, ids: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_seen_post_ids": sorted(ids)}
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=True, indent=2)
            fh.write("\n")

    def _connect_sqlite(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id TEXT PRIMARY KEY
            )
            """
        )
        return connection

    def _load_ids_sqlite(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self._connect_sqlite() as connection:
            rows = connection.execute("SELECT post_id FROM seen_posts").fetchall()
        return {row[0] for row in rows}

    def _save_ids_sqlite(self, ids: set[str]) -> None:
        with self._connect_sqlite() as connection:
            connection.execute("DELETE FROM seen_posts")
            connection.executemany(
                "INSERT INTO seen_posts (post_id) VALUES (?)",
                [(post_id,) for post_id in sorted(ids)],
            )
            connection.commit()


def filter_new_posts(posts: list[dict], seen_ids: set[str]) -> tuple[list[dict], set[str]]:
    new_posts = [post for post in posts if post["post_id"] not in seen_ids]
    updated_seen = set(seen_ids)
    for post in posts:
        updated_seen.add(post["post_id"])
    return new_posts, updated_seen
