import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MigrationTest(unittest.TestCase):
    def test_alembic_upgrade_head_creates_fresh_database(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "opsdash.db"
            env = os.environ.copy()
            env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

            result = _run_alembic(env, "head")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with sqlite3.connect(db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("work_items", tables)
            self.assertIn("work_item_evidence", tables)
            self.assertIn("ai_reviews", tables)

    def test_requester_token_migration_backfills_existing_work_items(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = Path(tmpdir) / "opsdash.db"
            env = os.environ.copy()
            env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

            result = _run_alembic(env, "0002")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with sqlite3.connect(db_path) as conn:
                conn.execute("INSERT INTO work_items (title) VALUES (?)", ("Legacy item",))
                conn.commit()

            result = _run_alembic(env, "head")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            with sqlite3.connect(db_path) as conn:
                token = conn.execute("SELECT requester_token FROM work_items WHERE title = ?", ("Legacy item",)).fetchone()[0]

            self.assertTrue(token)


def _run_alembic(env: dict[str, str], revision: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


if __name__ == "__main__":
    unittest.main()
