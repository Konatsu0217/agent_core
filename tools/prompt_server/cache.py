class Cache:
    """内存级缓存实现
    
    用于按session_id缓存烘焙后的systemPrompt
    """
    
    def __init__(self):
        """初始化缓存"""
        self._cache = {}
    
    def get(self, session_id):
        """获取缓存的prompt
        
        Args:
            session_id: 会话ID
        
        Returns:
            缓存的systemPrompt，如果不存在则返回None
        """
        return self._cache.get(session_id)
    
    def set(self, session_id, prompt):
        """设置缓存的prompt
        
        Args:
            session_id: 会话ID
            prompt: 烘焙后的systemPrompt
        """
        self._cache[session_id] = prompt
    
    def delete(self, session_id):
        """删除指定session的缓存
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._cache:
            del self._cache[session_id]
    
    def clear(self):
        """清空所有缓存"""
        self._cache.clear()
    
    def size(self):
        """获取缓存大小
        
        Returns:
            缓存中的项目数量
        """
        return len(self._cache)
