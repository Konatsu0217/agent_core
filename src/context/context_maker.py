import asyncio
from abc import ABC, abstractmethod
from pyexpat.errors import messages
from typing import List, Dict, Any, Optional

from src.context.context_model import Context


class IContextMaker(ABC):
    """上下文构建接口"""
    
    @abstractmethod
    async def build_context(self, session_id: str, user_query: str, **kwargs) -> Context:
        """构建上下文"""
        pass
    
    @abstractmethod
    async def augment_context(self, context: Context, **kwargs) -> Context:
        """增强上下文"""
        pass

    @staticmethod
    def build_custom_message_struct(components: List[Any], **kwargs) -> List[Dict[str, Any]]:
        """按传入顺序构建自定义上下文
        
        Args:
            components: 要拼接的组件列表
            **kwargs: 额外参数
            
        Returns:
            拼接后的消息列表
        """
        messages = []

        for component in components:
            if isinstance(component, str) and component:
                # 如果是字符串且非空，作为系统提示词
                messages.append({"role": "system", "content": component})
            elif isinstance(component, dict) and component:
                # 如果是字典且非空，直接添加
                messages.append(component)
            elif isinstance(component, list):
                # 如果是列表，直接添加整个列表
                messages.extend(component)

        return messages


class DefaultContextMaker(IContextMaker):
    """默认上下文构建器"""
    
    def __init__(self, memory_service=None, tool_manager=None, prompt_service=None, session_service=None):
        self.memory_service = memory_service
        self.tool_manager = tool_manager
        self.prompt_service = prompt_service
        self.session_service = session_service
        self.agent_profile = None
        self.augmenters = []
        self._augmenters_loaded = False
    
    def add_augmenter(self, augmenter):
        """添加上下文增强器"""
        self.augmenters.append(augmenter)
    
    def _load_augmenters_from_profile(self):
        if self._augmenters_loaded:
            return
        augmenters_cfg = {}
        try:
            augmenters_cfg = (self.agent_profile or {}).get("augmenters", [])
        except Exception:
            augmenters_cfg = []
        if isinstance(augmenters_cfg, list):
            try:
                from src.context.augmenters import create_augmenter
            except Exception:
                create_augmenter = None
            for item in augmenters_cfg:
                name = None
                params = None
                if isinstance(item, str):
                    name = item
                elif isinstance(item, dict):
                    name = item.get("name")
                    params = item.get("params") or item.get("args") or {}
                if not name or not create_augmenter:
                    continue
                aug = create_augmenter(name, params)
                if aug:
                    self.add_augmenter(aug)
        self._augmenters_loaded = True
    
    async def build_context(self, session_id: str, user_query: str, **kwargs) -> Context:
        """构建上下文"""
        context = Context(
            session_id=session_id,
            user_query=user_query,
            messages=[],
            tools=[],
            memory=[],
            session=None,
            **kwargs
        )
        
        # 构建prompt和tools
        await self._build_prompt_and_tools(context, **kwargs)
        
        # 增强上下文
        self._load_augmenters_from_profile()
        for augmenter in self.augmenters:
            context = await augmenter.augment(context, **kwargs)
        
        return context
    
    async def _build_prompt_and_tools(self, context: Context, **kwargs):
        """构建prompt和tools"""
        session_id = context.session_id
        user_query = context.user_query
        
        # 统一创建 Task 对象
        tasks = []

        # 构建提示词
        if self.prompt_service and self.agent_profile:
            pe_task = asyncio.create_task(self.prompt_service.build_prompt(
                session_id=session_id,
                agent_profile=self.agent_profile
            ))
            tasks.append(pe_task)
        else:
            async def empty_pe_task():
                return {"llm_request": {"messages": [{"role": "user", "content": user_query}]}}
            tasks.append(empty_pe_task())

        # 搜索记忆
        if self.memory_service:
            rag_task = asyncio.create_task(self.memory_service.search(
                query=user_query,
                user_id=session_id,
                limit=5
            ))
            tasks.append(rag_task)
        else:
            async def empty_rag_task():
                return []
            tasks.append(empty_rag_task())

        # 获取工具
        if self.tool_manager:
            tools_task = asyncio.create_task(self.tool_manager.get_tools())
            tasks.append(tools_task)
        else:
            async def empty_tools_task():
                return []
            tasks.append(empty_tools_task())

        # 获取会话
        if self.session_service:
            session_task = asyncio.create_task(self.session_service.get_session(
                session_id, "DefaultAgent"
            ))
            tasks.append(session_task)
        else:
            async def empty_session_task():
                return None
            tasks.append(empty_session_task())

        # 并行执行
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5
            )

            system_prompt, rag_results, tools, session_history = results

            # 处理异常
            if isinstance(system_prompt, Exception):
                print(f"❌ PE build_prompt failed: {system_prompt}")
                return

            if isinstance(tools, Exception):
                print(f"⚠️ ToolManager get_tools failed: {tools}")
                tools = []

            if isinstance(rag_results, Exception):
                print(f"⚠️ MemoryService search failed: {rag_results}")
                rag_results = []

            # 分离系统提示词和消息

            # 移除末尾多余的换行
            system_prompt = system_prompt.strip()

            # 更新上下文
            context.system_prompt = system_prompt
            context.messages = [{"role": "user", "content": user_query}]
            context.tools = tools
            context.memory = rag_results
            context.session = session_history

        except asyncio.TimeoutError:
            print("❌ Timeout: Service request took too long")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    async def augment_context(self, context: Context, **kwargs) -> Context:
        """增强上下文"""
        for augmenter in self.augmenters:
            context = await augmenter.augment(context, **kwargs)
        return context
