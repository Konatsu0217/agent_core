from abc import ABC, abstractmethod
from typing import Optional


class IQueryWrapper(ABC):
    """查询包装服务接口"""

    @abstractmethod
    def wrap_query(self, query: str, **kwargs) -> str:
        """包装用户查询"""
        pass

    @abstractmethod
    def set_template(self, template: str):
        """设置包装模板"""
        pass