from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchRequest:
    channel: str
    limit: int
    fixture_file: Path | None = None


class BaseAdapter:
    command_env: str
    source_name: str

    def fetch(self, request: FetchRequest) -> dict[str, Any]:
        if request.fixture_file is not None:
            return self._load_fixture(request.fixture_file)
        command = os.environ.get(self.command_env)
        if command:
            return self._run_command(command, request)
        raise AdapterError(
            f"{self.source_name} adapter is not wired. "
            f"Provide --fixture-file or set {self.command_env}."
        )

    def _load_fixture(self, fixture_path: Path) -> dict[str, Any]:
        with fixture_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _run_command(self, command: str, request: FetchRequest) -> dict[str, Any]:
        completed = subprocess.run(
            [command, request.channel, str(request.limit)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AdapterError(
                f"{self.source_name} adapter command failed with code {completed.returncode}: "
                f"{completed.stderr.strip()}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{self.source_name} adapter returned invalid JSON") from exc


class PrimaryAdapter(BaseAdapter):
    command_env = "YPR_PRIMARY_COMMAND"
    source_name = "primary"

    def fetch(self, request: FetchRequest) -> dict[str, Any]:
        if request.fixture_file is not None:
            payload = self._load_fixture(request.fixture_file)
            if isinstance(payload, dict) and isinstance(payload.get("posts"), list) and "channel_id" in payload:
                return self._normalize_archive_payload(payload, request)
            return payload
        command = os.environ.get(self.command_env)
        if command:
            return self._run_command(command, request)
        return self._run_post_archiver(request)

    def _run_post_archiver(self, request: FetchRequest) -> dict[str, Any]:
        binary = self._resolve_post_archiver_binary()
        with tempfile.TemporaryDirectory(prefix="ypr-primary-") as tmpdir:
            output_dir = Path(tmpdir)
            completed = subprocess.run(
                [
                    str(binary),
                    request.channel,
                    "-n",
                    str(request.limit),
                    "-o",
                    str(output_dir),
                    "--no-summary",
                    "--compact",
                    "--log-file",
                    str(output_dir / "post-archiver.log"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise AdapterError(
                    "primary adapter post-archiver command failed with "
                    f"code {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
                )
            archive_path = self._find_archive_file(output_dir)
            with archive_path.open("r", encoding="utf-8") as fh:
                archive_payload = json.load(fh)
        return self._normalize_archive_payload(archive_payload, request)

    def _resolve_post_archiver_binary(self) -> Path:
        binary_override = os.environ.get("YPR_PRIMARY_BIN")
        if binary_override:
            return Path(binary_override)
        repo_root = Path(__file__).resolve().parents[1]
        local_binary = repo_root / ".venv" / "bin" / "post-archiver"
        if local_binary.exists():
            return local_binary
        return Path("post-archiver")

    def _find_archive_file(self, output_dir: Path) -> Path:
        matches = sorted(output_dir.glob("posts_*.json"))
        if not matches:
            raise AdapterError("primary adapter did not produce an archive JSON file")
        return matches[-1]

    def _normalize_archive_payload(
        self, archive_payload: dict[str, Any], request: FetchRequest
    ) -> dict[str, Any]:
        raw_posts = archive_payload.get("posts")
        if not isinstance(raw_posts, list):
            raise AdapterError("primary adapter archive JSON did not contain a posts list")
        trimmed_posts = raw_posts[: request.limit]
        return {
            "channel": request.channel,
            "posts": trimmed_posts,
        }


class BackupAdapter(BaseAdapter):
    command_env = "YPR_BACKUP_COMMAND"
    source_name = "backup"


def get_adapter(source: str) -> BaseAdapter:
    if source == "primary":
        return PrimaryAdapter()
    if source == "backup":
        return BackupAdapter()
    raise AdapterError(f"unsupported source: {source}")
