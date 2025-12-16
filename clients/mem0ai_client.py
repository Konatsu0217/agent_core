import json
import os
from pathlib import Path
from typing import Dict, Any, List
import copy

from mem0 import Memory

class MemoryManager:
    """
    基于 mem0 的会话记忆管理器，支持按 session_id 隔离存储
    """

    def __init__(self, config_path: str | None = None):
        """
        初始化记忆管理器

        Args:
            config_path: 配置文件路径，不指定则自动查找
        """
        self._config = self._load_config(config_path)
        self._base_dir = self._config.get("vector_store", {}).get("config", {}).get("path", "./vector_memory_database")
        self._sessions: Dict[str, Memory] = {}
        Path(self._base_dir).mkdir(parents=True, exist_ok=True)

    def add(self, messages: List[Dict[str, str]], session_id: str, metadata: Dict[str, Any] | None = None) -> None:
        """
        为指定会话添加记忆

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
            session_id: 会话ID
            metadata: 可选的元数据
        """
        mem = self._get_session_memory(session_id)
        mem.add(messages, user_id=session_id, metadata=metadata)

    def search(self, query: str | List[Dict[str, str]], session_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        在指定会话中搜索相关记忆

        Args:
            query: 查询文本或消息列表
            session_id: 会话ID
            limit: 返回结果数量限制

        Returns:
            相关记忆列表
        """
        mem = self._get_session_memory(session_id)
        return mem.search(query=query, user_id=session_id, limit=limit)

    def _get_session_memory(self, session_id: str) -> Memory:
        """获取或创建指定会话的 Memory 实例"""
        sid = self._sanitize_session_id(session_id)

        if sid in self._sessions:
            return self._sessions[sid]

        # 为该会话创建独立的向量库路径
        session_path = str(Path(self._base_dir) / sid)
        Path(session_path).mkdir(parents=True, exist_ok=True)

        # 复制配置并设置会话专属路径
        session_config = copy.deepcopy(self._config)
        session_config["vector_store"]["config"]["path"] = session_path

        mem = Memory.from_config(session_config)
        self._sessions[sid] = mem
        return mem

    @staticmethod
    def _sanitize_session_id(session_id: str) -> str:
        """清理 session_id，防止路径穿越"""
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in session_id)

    def _load_config(self, config_path: str | None) -> Dict[str, Any]:
        """加载配置文件"""
        # 查找配置文件
        candidates = []
        if config_path:
            candidates.append(Path(config_path))
        if env_path := os.getenv("MEM0_CONFIG_FILE"):
            candidates.append(Path(env_path))
        candidates.extend([
            Path("config/mem0.json"),
            Path(__file__).resolve().parents[1] / "config" / "mem0.json",
        ])

        for path in candidates:
            try:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    return self._normalize_config(config_data)
            except Exception:
                continue

        raise FileNotFoundError(
            "未找到 mem0 配置文件，请在 config/mem0.json 中配置，"
            "或设置 MEM0_CONFIG_FILE 环境变量"
        )

    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """标准化配置格式"""
        # 如果已经是标准格式，直接返回
        if all(k in config for k in ("embedder", "llm", "vector_store")):
            return config

        # 转换旧格式配置
        ms = config.get("memory_settings", {})

        # 读取 API Key
        api_key = self._load_api_key()

        return {
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": ms.get("embedding_model", ""),
                    "api_key": api_key,
                    "openai_base_url": ms.get("embedding_model_url", ""),
                    "embedding_dims": ms.get("embedding_model_dims", 1024),
                },
            },
            "llm": {
                "provider": "deepseek",
                "config": {
                    "model": ms.get("intent_recognition_model", ""),
                    "api_key": api_key,
                    "deepseek_base_url": ms.get("intent_recognition_url", ""),
                },
            },
            "vector_store": {
                "provider": ms.get("vector_base_provider", "faiss"),
                "config": {
                    "collection_name": ms.get("collection_name", "mem0_collection"),
                    "path": str(
                        os.curdir + "/" + "vector_memory_database"),
                    "distance_strategy": ms.get("distance_strategy", "euclidean"),
                    "embedding_model_dims": ms.get("embedding_model_dims", 1024),
                },
            },
        }

    @staticmethod
    def _load_api_key() -> str:
        """从环境变量或文件加载 API Key"""
        if env_key := os.getenv("MEM0_API_KEY"):
            return env_key

        key_paths = [
            Path("config/api.key"),
            Path(__file__).resolve().parents[1] / "config" / "api.key",
            Path("api.key"),
            Path(__file__).resolve().parents[1] / "api.key",
        ]

        for path in key_paths:
            try:
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for key_name in ("api-key", "api_key", "openapi_key"):
                        if key := data.get(key_name):
                            return key
            except Exception:
                continue

        return ""


# 使用示例
if __name__ == '__main__':
    import time

    # 初始化管理器
    manager = MemoryManager()

    # 添加记忆
    print("=== 添加记忆 ===")
    messages = [
        {"role": "user", "content": "Thinking of making a sandwich. What do you recommend?"},
        {"role": "assistant", "content": "How about adding some cheese for extra flavor?"},
        {"role": "user", "content": "Actually, I don't like cheese."},
        {"role": "assistant", "content": "I'll remember that you don't like cheese for future recommendations."}
    ]

    start = time.time()
    manager.add(messages, session_id="john", metadata={"category": "food"})
    print(f"添加耗时: {time.time() - start:.3f}s")

    # 搜索记忆
    print("\n=== 搜索记忆 ===")
    query = "What are my food preferences?"

    start = time.time()
    results = manager.search(query, session_id="john", limit=3)
    print(f"搜索耗时: {time.time() - start:.3f}s")

    print("\n搜索结果:")
    print(json.dumps(results, ensure_ascii=False, indent=2))