from typing import Dict, Any, List, Optional


class Context:
    """上下文模型类"""
    
    def __init__(self, 
                 session_id: str, 
                 user_query: str, 
                 messages: List[Dict[str, Any]] = None, 
                 tools: List[Dict[str, Any]] = None, 
                 memory: List[Any] = None, 
                 session: Optional[Dict[str, Any]] = None, 
                 system_prompt: Optional[str] = None,
                 **extra_context):
        """初始化上下文
        
        Args:
            session_id: 会话ID
            user_query: 用户查询
            messages: 消息列表
            tools: 工具列表
            memory: 记忆列表
            session: 会话信息
            system_prompt: 系统提示词
            **extra_context: 额外的上下文信息
        """
        self.session_id = session_id
        self.user_query = user_query
        self.messages = messages or []
        self.tools = tools or []
        self.memory = memory or []
        self.session = session
        self.system_prompt = system_prompt
        self.extra_context = extra_context
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文值
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            对应的值或默认值
        """
        if hasattr(self, key):
            return getattr(self, key)
        return self.extra_context.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """设置上下文值
        
        Args:
            key: 键名
            value: 值
        """
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.extra_context[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典
        
        Returns:
            上下文字典
        """
        result = {
            "session_id": self.session_id,
            "user_query": self.user_query,
            "messages": self.messages,
            "tools": self.tools,
            "memory": self.memory,
            "session": self.session,
            "system_prompt": self.system_prompt
        }
        result.update(self.extra_context)
        return result
    
    def update(self, **kwargs) -> None:
        """更新上下文
        
        Args:
            **kwargs: 要更新的键值对
        """
        for key, value in kwargs.items():
            self.set(key, value)
    
    def __getitem__(self, key: str) -> Any:
        """支持字典式访问
        
        Args:
            key: 键名
            
        Returns:
            对应的值
        """
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """支持字典式设置
        
        Args:
            key: 键名
            value: 值
        """
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """支持in操作符
        
        Args:
            key: 键名
            
        Returns:
            是否包含该键
        """
        return hasattr(self, key) or key in self.extra_context
