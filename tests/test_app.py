from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "app.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures"


class AppCliTests(unittest.TestCase):
    def run_app(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(APP_PATH), *args]
        return subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, check=False)

    def run_app_with_env(self, *args: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(APP_PATH), *args]
        env = os.environ.copy()
        env.update(env_overrides)
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_primary_fixture_returns_new_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            result = self.run_app(
                "--source",
                "primary",
                "--channel",
                "https://www.youtube.com/@example/community",
                "--limit",
                "3",
                "--json",
                "--fixture-file",
                str(FIXTURES / "primary_raw.json"),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["posts"]), 2)
            self.assertEqual(payload["posts"][0]["post_id"], "abc123")
            self.assertEqual(payload["posts"][0]["delivery_type"], "photo")
            self.assertIn("Tonight at 8 PM", payload["posts"][0]["caption"])
            self.assertFalse(payload["posts"][0]["caption_was_truncated"])
            self.assertEqual(payload["posts"][1]["delivery_type"], "media_group")
            self.assertEqual(len(payload["posts"][1]["media"]), 2)

    def test_primary_archiver_fixture_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            result = self.run_app(
                "--source",
                "primary",
                "--channel",
                "@yutinghaofinance",
                "--limit",
                "1",
                "--json",
                "--fixture-file",
                str(FIXTURES / "post_archiver_raw.json"),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["channel"], "@yutinghaofinance")
            self.assertEqual(len(payload["posts"]), 1)
            self.assertEqual(
                payload["posts"][0]["post_url"],
                "https://www.youtube.com/post/Ugkxz4v7dtISqSnRtP22tXb7UrRXGZkru8Iw",
            )
            self.assertEqual(payload["posts"][0]["text"], "First archived post")
            self.assertEqual(payload["posts"][0]["images"], ["https://example.com/archiver-1.jpg"])
            self.assertEqual(payload["posts"][0]["published_text"], "1 hour ago")
            self.assertEqual(payload["posts"][0]["delivery_type"], "photo")
            self.assertIn("https://www.youtube.com/post/", payload["posts"][0]["caption"])
            self.assertEqual(payload["posts"][0]["followup_message_chunks"], [])

    def test_second_run_dedupes_to_exit_10(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            args = (
                "--source",
                "primary",
                "--channel",
                "https://www.youtube.com/@example/community",
                "--limit",
                "3",
                "--json",
                "--fixture-file",
                str(FIXTURES / "primary_raw.json"),
                "--state-file",
                str(state_file),
            )
            first = self.run_app(*args)
            second = self.run_app(*args)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 10, second.stderr)
            payload = json.loads(second.stdout)
            self.assertEqual(payload["posts"], [])

    def test_sqlite_state_backend_dedupes_to_exit_10(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.sqlite3"
            args = (
                "--source",
                "primary",
                "--channel",
                "https://www.youtube.com/@example/community",
                "--limit",
                "3",
                "--json",
                "--fixture-file",
                str(FIXTURES / "primary_raw.json"),
                "--state-file",
                str(state_file),
                "--state-backend",
                "sqlite",
            )
            first = self.run_app(*args)
            second = self.run_app(*args)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 10, second.stderr)
            payload = json.loads(second.stdout)
            self.assertEqual(payload["posts"], [])

    def test_backup_fixture_normalizes_fallback_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            result = self.run_app(
                "--source",
                "backup",
                "--channel",
                "@example",
                "--limit",
                "1",
                "--json",
                "--fixture-file",
                str(FIXTURES / "backup_raw.json"),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["channel"], "@example")
            self.assertEqual(len(payload["posts"]), 1)
            self.assertEqual(payload["posts"][0]["post_url"], "https://www.youtube.com/post/ghi789")
            self.assertTrue(payload["posts"][0]["post_id"])
            self.assertEqual(payload["posts"][0]["delivery_type"], "photo")

    def test_long_caption_is_truncated_and_followup_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            fixture_file = Path(tmpdir) / "long.json"
            fixture_file.write_text(
                json.dumps(
                    {
                        "channel": "Example Channel",
                        "posts": [
                            {
                                "post_id": "long1",
                                "post_url": "https://www.youtube.com/post/long1",
                                "text": "A" * 1500,
                                "images": ["https://example.com/long.jpg"]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_app(
                "--source",
                "primary",
                "--channel",
                "https://www.youtube.com/@example/community",
                "--limit",
                "1",
                "--json",
                "--fixture-file",
                str(fixture_file),
                "--state-file",
                str(state_file),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            post = payload["posts"][0]
            self.assertEqual(post["delivery_type"], "photo")
            self.assertTrue(post["caption_was_truncated"])
            self.assertLessEqual(len(post["caption"]), 1024)
            self.assertTrue(post["followup_message_text"])
            self.assertTrue(post["full_text"].startswith("A"))

    def test_missing_adapter_configuration_returns_exit_20(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            result = self.run_app(
                "--source",
                "backup",
                "--channel",
                "@example",
                "--json",
                "--state-file",
                str(state_file),
            )
            self.assertEqual(result.returncode, 20)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("not wired", payload["error"])

    def test_primary_command_supports_arguments_in_env_var(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            command = (
                f'{sys.executable} -c '
                '"import json,sys; '
                'print(json.dumps({'
                '\'channel\': sys.argv[1], '
                '\'posts\': [{'
                '\'post_id\': \'cmd123\', '
                '\'text\': \'From command\', '
                '\'images\': [], '
                '\'published_text\': \'now\''
                '}]}))"'
            )
            result = self.run_app_with_env(
                "--source",
                "primary",
                "--channel",
                "@command-example",
                "--limit",
                "1",
                "--json",
                "--state-file",
                str(state_file),
                env_overrides={"YPR_PRIMARY_COMMAND": command},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["channel"], "@command-example")
            self.assertEqual(payload["posts"][0]["post_id"], "cmd123")
            self.assertEqual(payload["posts"][0]["delivery_type"], "message")


if __name__ == "__main__":
    unittest.main()
