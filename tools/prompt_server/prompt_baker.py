import os
from jinja2 import Environment, FileSystemLoader
from .cache import Cache

class PromptBaker:
    """SystemPrompt烘焙器
    
    用于根据AgentProfile烘焙systemPrompt
    """
    
    def __init__(self, template_dir=None):
        """初始化PromptBaker
        
        Args:
            template_dir: 模板目录路径，如果为None则使用默认目录
        """
        # 初始化缓存
        self.cache = Cache()
        
        # 设置模板目录
        if template_dir is None:
            # 获取当前文件所在目录的templates子目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.template_dir = os.path.join(current_dir, 'templates')
        else:
            self.template_dir = template_dir
        
        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=False
        )
    
    async def bake_system_prompt(self, session_id, agent_profile):
        """烘焙systemPrompt
        
        Args:
            session_id: 会话ID
            agent_profile: Agent配置文件
        
        Returns:
            烘焙后的systemPrompt
        """
        # 首先检查缓存
        cached_prompt = self.cache.get(session_id)
        if cached_prompt:
            return cached_prompt
        
        # 提取prompt_config
        prompt_config = agent_profile.get('prompt_config', {})
        
        # 准备模板数据
        template_data = {
            'role': prompt_config.get('role', ''),
            'expertise': prompt_config.get('expertise', []),
            'personality': prompt_config.get('personality', ''),
            'guidelines': prompt_config.get('guidelines', {}),
            'language': prompt_config.get('language', 'zh-CN'),
            'examples': prompt_config.get('examples', []),
            'extra': prompt_config.get('extra', [])
        }
        
        # 加载并渲染模板
        template = self.env.get_template('default.j2')
        system_prompt = template.render(**template_data)
        
        # 缓存结果
        self.cache.set(session_id, system_prompt)
        
        return system_prompt
    
    def get_cached_prompt(self, session_id):
        """获取缓存的prompt
        
        Args:
            session_id: 会话ID
        
        Returns:
            缓存的systemPrompt，如果不存在则返回None
        """
        return self.cache.get(session_id)
    
    def clear_cache(self, session_id):
        """清理指定session的缓存
        
        Args:
            session_id: 会话ID
        """
        self.cache.delete(session_id)
    
    def clear_all_cache(self):
        """清空所有缓存"""
        self.cache.clear()
    
    def get_cache_size(self):
        """获取缓存大小
        
        Returns:
            缓存中的项目数量
        """
        return self.cache.size()
