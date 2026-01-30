from .prompt_baker import PromptBaker
from .cache import Cache

__all__ = ['PromptBaker', 'Cache']

# 提供便捷的API函数
def bake_system_prompt(session_id, agent_profile):
    """烘焙systemPrompt
    
    Args:
        session_id: 会话ID
        agent_profile: Agent配置文件
    
    Returns:
        烘焙后的systemPrompt
    """
    baker = PromptBaker()
    return baker.bake_system_prompt(session_id, agent_profile)

def get_cached_prompt(session_id):
    """获取缓存的prompt
    
    Args:
        session_id: 会话ID
    
    Returns:
        缓存的systemPrompt，如果不存在则返回None
    """
    baker = PromptBaker()
    return baker.get_cached_prompt(session_id)

def clear_cache(session_id):
    """清理指定session的缓存
    
    Args:
        session_id: 会话ID
    """
    baker = PromptBaker()
    baker.clear_cache(session_id)
