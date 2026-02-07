import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, Optional


class SQLiteAgentProfileStorage:
    def __init__(self, db_path: str = "data/agent.sqlite3"):
        self._db_path = db_path
        dir_name = os.path.dirname(self._db_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        try:
            with self._conn:
                self._conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_profiles (
                    agent_id TEXT NOT NULL PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    avatar_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def exists(self, agent_id: str) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(
                    "SELECT 1 FROM agent_profiles WHERE agent_id=? LIMIT 1",
                    (agent_id,),
                )
                return cur.fetchone() is not None
            finally:
                cur.close()

    def create(self, agent_id: str, profile: Dict[str, Any], avatar_url: Optional[str] = None) -> None:
        if not agent_id:
            raise ValueError("missing_agent_id")
        avatar = avatar_url if avatar_url is not None else profile.get("avatar_url")
        now = datetime.now().isoformat()
        payload = json.dumps(profile, ensure_ascii=False)
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO agent_profiles(agent_id, profile_json, avatar_url, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(agent_id) DO UPDATE SET
                        profile_json=excluded.profile_json,
                        avatar_url=excluded.avatar_url,
                        updated_at=excluded.updated_at
                    """,
                    (agent_id, payload, avatar, now, now),
                )

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute(
                    "SELECT profile_json, avatar_url, created_at, updated_at FROM agent_profiles WHERE agent_id=?",
                    (agent_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                profile = json.loads(row[0])
                profile["agent_id"] = agent_id
                if row[1] is not None:
                    profile["avatar_url"] = row[1]
                profile["_meta"] = {
                    "created_at": row[2],
                    "updated_at": row[3],
                }
                return profile
            finally:
                cur.close()

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
