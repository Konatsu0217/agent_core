import os
import sqlite3
import threading
from typing import Optional
from src.context.context import Context


class SQLiteStorage:
    def __init__(self, db_path: str = "data/context.sqlite3"):
        self._db_path = db_path
        dir_name = os.path.dirname(self._db_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        try:
            with self._conn:
                self._conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contexts (
                    key TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (key, version)
                )
                """
            )

    def save(self, key: str, context: Context):
        payload = context.to_json()
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO contexts(key, version, payload) VALUES (?, ?, ?)",
                    (key, context.version, payload),
                )

    def load(self, key: str, version: Optional[int] = None) -> Optional[Context]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                if version is None:
                    cur.execute(
                        "SELECT payload FROM contexts WHERE key=? ORDER BY version DESC LIMIT 1",
                        (key,),
                    )
                else:
                    cur.execute(
                        "SELECT payload FROM contexts WHERE key=? AND version=?",
                        (key, version),
                    )
                row = cur.fetchone()
                if not row:
                    return None
                return Context.from_json(row[0])
            finally:
                cur.close()

    def delete_by_key(self, key: str) -> int:
        with self._lock:
            with self._conn:
                cur = self._conn.execute(
                    "DELETE FROM contexts WHERE key=?",
                    (key,),
                )
                return cur.rowcount

    def delete_by_prefix(self, key_prefix: str) -> int:
        with self._lock:
            with self._conn:
                cur = self._conn.execute(
                    "DELETE FROM contexts WHERE key LIKE ?",
                    (f"{key_prefix}%",),
                )
                return cur.rowcount

    def delete_by_version_range(
        self,
        key: str,
        min_version: Optional[int] = None,
        max_version: Optional[int] = None,
    ) -> int:
        if min_version is None and max_version is None:
            return 0
        clauses = ["key=?"]
        params = [key]
        if min_version is not None:
            clauses.append("version>=?")
            params.append(min_version)
        if max_version is not None:
            clauses.append("version<=?")
            params.append(max_version)
        where_sql = " AND ".join(clauses)
        with self._lock:
            with self._conn:
                cur = self._conn.execute(
                    f"DELETE FROM contexts WHERE {where_sql}",
                    tuple(params),
                )
                return cur.rowcount

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
