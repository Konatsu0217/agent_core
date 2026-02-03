from src.context.manager import ContextManager
from src.context.storage.sqlite_storage import SQLiteStorage


def main():
    storage = SQLiteStorage(".data/example_context.sqlite3")
    manager = ContextManager(storage_backend=storage)
    ctx = manager.create_context(session_id="s1", agent_id="a1", user_query="hello")
    manager.append_message(ctx, {"role": "user", "content": "hi"}, auto_snapshot=True)
    latest = storage.load("s1:a1")
    specified = storage.load("s1:a1", version=0)
    print("latest_version", latest.version if latest else None)
    print("specified_version", specified.version if specified else None)


if __name__ == "__main__":
    main()
