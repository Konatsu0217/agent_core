from typing import Dict, Any, Optional
import json
import os


class ServiceConfig:
    """服务配置"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config: Dict[str, Any] = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def load(self, config_file: str):
        """加载配置文件"""
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
    
    def save(self, config_file: str):
        """保存配置文件"""
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)


class AgentConfig:
    """Agent 配置"""
    
    def __init__(self, agent_name: str, config: Optional[Dict[str, Any]] = None):
        self.agent_name = agent_name
        self.config = config or {}
        
        # 默认配置
        self._set_defaults()
    
    def _set_defaults(self):
        """设置默认配置"""
        if "work_flow_type" not in self.config:
            self.config["work_flow_type"] = "TEST"
        
        if "use_tools" not in self.config:
            self.config["use_tools"] = True
        
        if "output_format" not in self.config:
            self.config["output_format"] = "json"
        
        if "services" not in self.config:
            self.config["services"] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """获取服务配置"""
        return self.config.get("services", {}).get(service_name, {})
    
    def set_service_config(self, service_name: str, service_config: Dict[str, Any]):
        """设置服务配置"""
        if "services" not in self.config:
            self.config["services"] = {}
        self.config["services"][service_name] = service_config


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        self.service_config = ServiceConfig(os.path.join(self.config_dir, "services.json"))
        self.agent_configs: Dict[str, AgentConfig] = {}
    
    def get_service_config(self) -> ServiceConfig:
        """获取服务配置"""
        return self.service_config
    
    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """获取 Agent 配置"""
        if agent_name not in self.agent_configs:
            config_file = os.path.join(self.config_dir, f"agent_{agent_name}.json")
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            self.agent_configs[agent_name] = AgentConfig(agent_name, config)
        return self.agent_configs[agent_name]
    
    def save_agent_config(self, agent_name: str):
        """保存 Agent 配置"""
        if agent_name in self.agent_configs:
            config_file = os.path.join(self.config_dir, f"agent_{agent_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.agent_configs[agent_name].config, f, indent=2, ensure_ascii=False)
    
    def save_service_config(self):
        """保存服务配置"""
        config_file = os.path.join(self.config_dir, "services.json")
        self.service_config.save(config_file)
