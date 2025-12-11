"""
独立的配置管理模块，解决循环导入问题
"""
import json
from typing import Dict, Any


class ConfigManager:
    """配置管理器，避免循环导入"""
    _config: Dict[str, Any] = None
    _raw_config: Dict[str, Any] = None

    @classmethod
    def load_config(cls, config_path='/Users/bytedance/Desktop/explore_tech/agent_repo/agent_core/core_config.json'):
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 保存原始配置数据
            cls._raw_config = config_data
            
            # 扁平化配置，便于访问
            cls._config = {
                # 服务器配置
                'port': config_data['server']['port'],
                'workers': config_data['server']['workers'],
                'limit_concurrency': config_data['server']['limit_concurrency'],
                'backlog': config_data['server']['backlog'],
                'reload': config_data['server']['reload'],
                'timeout_keep_alive': config_data['server']['timeout_keep_alive'],
                
                # Backbone LLM配置
                'backbone_llm_openapi_url': config_data['backbone_llm_config']['openapi_url'],
                'backbone_llm_openapi_key': config_data['backbone_llm_config']['openapi_key'],
                'backbone_llm_model_name': config_data['backbone_llm_config']['model_name'],

                # PE配置
                'pe_url': config_data['pe_config']['url'],
                
                # RAG配置
                'rag_url': config_data['rag_config']['url'],
                
                # MCP Hub配置
                'mcphub_url': config_data['mcphub_config']['url'],
                'mcphub_port': config_data['mcphub_config']['port'],
            }

            if cls._config['backbone_llm_openapi_key'] == "":
                cls._config['backbone_llm_openapi_key'] = json.load(open('/Users/bytedance/Desktop/explore_tech/agent_repo/agent_core/api.key', 'r'))['openapi_key']
                config_data['backbone_llm_config']['openapi_key'] = cls._config['backbone_llm_openapi_key']

            print(f"配置加载成功: {cls._config}")
        except Exception as e:
            print(f"配置文件加载失败: {str(e)}")
            # 使用默认配置作为后备
            cls._config = {
                # 服务器默认配置
                'port': 25535,
                'workers': 1,
                'limit_concurrency': 50,
                'backlog': 1024,
                'reload': False,
                'timeout_keep_alive': 5,
                
                # Backbone LLM默认配置
                'backbone_llm_openapi_url': "https://api.openai.com/v1",
                'backbone_llm_openapi_key': "8d205783-9ac2-49ca-948b-40cbb551b254",
                'backbone_llm_model_name': "tts-1",

                # 服务默认URL
                'pe_url': "http://127.0.0.1:25535",
                'rag_url': "http://127.0.0.1:25536",
                'mcphub_url': "http://127.0.0.1:25537",
            }
            print(f"使用默认配置: {cls._config}")

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