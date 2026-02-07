"""
独立的配置管理模块，解决循环导入问题
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from src.infrastructure.config.config_schemas import CoreConfig
from src.infrastructure.logging.logger import get_logger


class ConfigManager:
    """配置管理器，避免循环导入"""
    _config: Dict[str, Any] = None
    _raw_config: Dict[str, Any] = None

    @classmethod
    def load_config(cls, config_path: Optional[str] = None):
        """加载配置文件"""
        try:
            project_root = Path(__file__).resolve().parents[3]
            # 允许通过环境变量指定配置文件路径
            env_path = os.getenv('CORE_CONFIG_FILE')
            candidates = []
            if config_path:
                candidates.append(Path(config_path))
            if env_path:
                candidates.append(Path(env_path))
            # 常见路径候选（相对/项目根）
            candidates.extend([
                Path('config/core.json'),
                project_root / 'config' / 'core.json',
                Path('core_config.json'),
                project_root / 'core_config.json',
            ])

            config_data = None
            for p in candidates:
                try:
                    if p.exists():
                        with open(p, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                            break
                except Exception:
                    continue
            if config_data is None:
                raise FileNotFoundError('core配置文件未找到')
            
            # 校验与标准化
            core = CoreConfig(**config_data)
            # 保存原始配置数据
            cls._raw_config = core.model_dump()
            
            # 扁平化配置，便于访问
            cls._config = {
                # 服务器配置
                'port': core.server.port,
                'workers': core.server.workers,
                'limit_concurrency': core.server.limit_concurrency,
                'backlog': core.server.backlog,
                'reload': core.server.reload,
                'timeout_keep_alive': core.server.timeout_keep_alive,
                
                # Backbone LLM配置
                'backbone_llm_openapi_url': core.backbone_llm_config.openapi_url,
                'backbone_llm_openapi_key': core.backbone_llm_config.openapi_key or "",
                'backbone_llm_model_name': core.backbone_llm_config.model_name,

                # PE配置
                'pe_url': core.pe_config.url,
                
                # RAG配置
                'rag_url': core.rag_config.url,
                
                # MCP Hub配置
                'mcphub_url': core.mcphub_config.url,
                'mcphub_port': core.mcphub_config.port,
            }

            # 环境变量优先，其次读取 config/api.key（若存在）
            if cls._config['backbone_llm_openapi_key'] == "":
                env_key = os.getenv('BACKBONE_LLM_API_KEY', '')
                if env_key:
                    cls._config['backbone_llm_openapi_key'] = env_key
                    cls._raw_config['backbone_llm_config']['openapi_key'] = env_key
                else:
                    for kp in [
                        Path('config/api.key'),
                        project_root / 'config' / 'api.key',
                        Path('api.key'),
                        project_root / 'api.key',
                    ]:
                        try:
                            if kp.exists():
                                with open(kp, 'r', encoding='utf-8') as kf:
                                    key = json.load(kf).get('openapi_key', '')
                                    if key:
                                        cls._config['backbone_llm_openapi_key'] = key
                                        cls._raw_config['backbone_llm_config']['openapi_key'] = key
                                        break
                        except Exception:
                            continue

            get_logger().info(f"配置加载成功: {cls._config}")
        except Exception as e:
            get_logger().error(f"配置文件加载失败: {str(e)}")
            # 使用默认配置作为后备（不包含敏感信息）
            cls._config = {
                # 服务器默认配置
                'port': 38888,
                'workers': 1,
                'limit_concurrency': 50,
                'backlog': 1024,
                'reload': False,
                'timeout_keep_alive': 5,
                
                # Backbone LLM默认配置
                'backbone_llm_openapi_url': "https://api.openai.com/v1",
                'backbone_llm_openapi_key': "",
                'backbone_llm_model_name': "tts-1",

                # 服务默认URL
                'pe_url': "http://127.0.0.1:25535",
                'rag_url': "http://127.0.0.1:25536",
                'mcphub_url': "http://127.0.0.1:25537",
            }
            # 同步原始结构，避免 None 访问错误
            cls._raw_config = {
                'server': {
                    'port': cls._config['port'],
                    'workers': cls._config['workers'],
                    'limit_concurrency': cls._config['limit_concurrency'],
                    'backlog': cls._config['backlog'],
                    'reload': cls._config['reload'],
                    'timeout_keep_alive': cls._config['timeout_keep_alive'],
                },
                'backbone_llm_config': {
                    'openapi_url': cls._config['backbone_llm_openapi_url'],
                    'openapi_key': cls._config['backbone_llm_openapi_key'],
                    'model_name': cls._config['backbone_llm_model_name'],
                    'temperature': 0.7,
                    'max_tokens': 1024,
                },
                'pe_config': {'url': cls._config['pe_url']},
                'rag_config': {'url': cls._config['rag_url']},
                'mcphub_config': {'url': cls._config['mcphub_url'], 'port': 9000},
            }
            get_logger().info(f"使用默认配置: {cls._config}")
            if cls._config['backbone_llm_openapi_key'] == "":
                env_key = os.getenv('BACKBONE_LLM_API_KEY', '')
                if env_key:
                    cls._config['backbone_llm_openapi_key'] = env_key
                    cls._raw_config['backbone_llm_config']['openapi_key'] = env_key
                else:
                    for kp in [
                        Path('config/api.key'),
                        project_root / 'config' / 'api.key',
                        Path('api.key'),
                        project_root / 'api.key',
                    ]:
                        try:
                            if kp.exists():
                                with open(kp, 'r', encoding='utf-8') as kf:
                                    key = json.load(kf).get('openapi_key', '')
                                    if key:
                                        cls._config['backbone_llm_openapi_key'] = key
                                        cls._raw_config['backbone_llm_config']['openapi_key'] = key
                                        break
                        except Exception:
                            continue

    @classmethod
    def get_config(cls):
        """获取配置"""
        if cls._config is None:
            cls.load_config()
        return cls._config
    
    @classmethod
    def get_raw_config(cls):
        """获取原始配置数据"""
        if cls._raw_config is None:
            cls.load_config()
        return cls._raw_config
    
    @classmethod
    def get_server_config(cls):
        """获取服务器配置"""
        raw_config = cls.get_raw_config()
        return raw_config.get('server', {})

    @classmethod
    def get_backbone_config(cls):
        """获取Backbone LLM配置"""
        raw_config = cls.get_raw_config()
        return raw_config.get('backbone_llm_config', {})
    
    @classmethod
    def get_service_config(cls, service_name: str):
        """获取指定服务的配置"""
        raw_config = cls.get_raw_config()
        config_mapping = {
            'pe': 'pe_config',
            'rag': 'rag_config',
            'mcphub': 'mcphub_config'
        }
        config_key = config_mapping.get(service_name.lower())
        if config_key:
            return raw_config.get(config_key, {})
        return {}
