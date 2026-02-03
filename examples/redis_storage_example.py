from src.context.storage.redis_client import RedisClientWithWriter
from src.context.storage.redis import RedisStorage
from src.context.manager import ContextManager


def main():
    client = RedisClientWithWriter(host="127.0.0.1", port=6379, db=0, decode_responses=False)
    storage = RedisStorage(client)
    cm = ContextManager(storage_backend=storage)
    ctx = cm.create_context(session_id="s1", agent_id="a1", user_query="hello")
    cm.snapshot(ctx, note="init")
    latest = storage.load(f"{ctx.session_id}:{ctx.agent_id}")
    print(latest)


if __name__ == "__main__":
    main()
