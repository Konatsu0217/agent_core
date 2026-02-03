import os
import shutil
import tempfile
import unittest

from src.context.context import Context
from src.context.manager import ContextManager
from src.context.storage.sqlite_storage import SQLiteStorage


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "context.sqlite3")
        self.storage = SQLiteStorage(self.db_path)
        self.manager = ContextManager(storage_backend=self.storage)

    def tearDown(self):
        try:
            self.storage.close()
        except Exception:
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_latest(self):
        ctx = self.manager.create_context(session_id="s1", agent_id="a1", user_query="u1")
        self.manager.append_message(ctx, {"role": "user", "content": "m1"}, auto_snapshot=True)
        latest = self.storage.load("s1:a1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.version, 1)
        self.assertEqual(latest.user_query, "u1")

    def test_load_specific_version(self):
        ctx = self.manager.create_context(session_id="s2", agent_id="a1", user_query="u2")
        self.manager.append_message(ctx, {"role": "user", "content": "m1"}, auto_snapshot=True)
        self.manager.append_message(ctx, {"role": "user", "content": "m2"}, auto_snapshot=True)
        v1 = self.storage.load("s2:a1", version=1)
        v2 = self.storage.load("s2:a1", version=2)
        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)

    def test_load_nonexistent(self):
        self.assertIsNone(self.storage.load("no:such"))
        ctx = self.manager.create_context(session_id="s3", agent_id="a1", user_query="u3")
        self.manager.append_message(ctx, {"role": "user", "content": "m1"}, auto_snapshot=True)
        self.assertIsNone(self.storage.load("s3:a1", version=999))


if __name__ == "__main__":
    unittest.main()
