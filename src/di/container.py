from typing import Dict, Any, Optional, Type


class ServiceContainer:
    """服务容器"""
    
    def __init__(self):
        self.services: Dict[str, Any] = {}
        self.factories: Dict[str, callable] = {}
    
    def register(self, name: str, service: Any):
        """注册服务实例"""
        self.services[name] = service
    
    def register_factory(self, name: str, factory: callable):
        """注册服务工厂"""
        self.factories[name] = factory
    
    def get(self, name: str) -> Optional[Any]:
        """获取服务实例"""
        # 先从已注册的服务中获取
        if name in self.services:
            return self.services[name]
        
        # 如果有工厂，创建新实例
        if name in self.factories:
            service = self.factories[name]()
            self.services[name] = service
            return service
        
        return None
    
    def has(self, name: str) -> bool:
        """检查服务是否存在"""
        return name in self.services or name in self.factories
    
    def remove(self, name: str):
        """移除服务"""
        if name in self.services:
            del self.services[name]
        if name in self.factories:
            del self.factories[name]
    
    def clear(self):
        """清空所有服务"""
        self.services.clear()
        self.factories.clear()


class Injector:
    """依赖注入器"""
    
    def __init__(self, container: ServiceContainer):
        self.container = container
    
    def inject(self, obj: Any):
        """注入依赖到对象"""
        # 检查对象的属性，注入匹配的服务
        for attr_name in dir(obj):
            if not attr_name.startswith('_'):
                attr_value = getattr(obj, attr_name, None)
                if attr_value is None:
                    # 尝试从容器中获取服务
                    service = self.container.get(attr_name)
                    if service:
                        setattr(obj, attr_name, service)
    
    def inject_with_annotations(self, obj: Any):
        """根据类型注解注入依赖"""
        import inspect
        
        # 获取对象的 __init__ 方法签名
        if hasattr(obj, '__init__'):
            sig = inspect.signature(obj.__init__)
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # 检查参数类型注解
                if param.annotation != inspect.Parameter.empty:
                    # 尝试根据类型名称获取服务
                    service_name = param.annotation.__name__.lower()
                    service = self.container.get(service_name)
                    if service:
                        setattr(obj, param_name, service)
    
    def get_service(self, name: str) -> Optional[Any]:
        """获取服务"""
        return self.container.get(name)


# 全局服务容器实例
_global_container = ServiceContainer()


def get_service_container() -> ServiceContainer:
    """获取全局服务容器"""
    return _global_container


def get_injector() -> Injector:
    """获取全局依赖注入器"""
    return Injector(_global_container)
