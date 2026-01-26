from typing import Optional, Any, Dict
from src.services.interfaces.query_wrapper import IQueryWrapper


class DefaultQueryWrapper(IQueryWrapper):
    """默认查询包装服务"""

    def __init__(self, template: Optional[str] = None):
        self.template = template or "用户查询: {query}, system: 你的回复必须为json格式{{\"response\": \"你的回复\",\"action\": \"简短、精准地表述你要做的肢体动作，使用英文\",\"expression\": \"从我为你提供的tool_type = resource中选择表情(可选，如果未提供则为空字符串)\"}} \n/no_think"

    def wrap_query(self, query: str, **kwargs) -> str:
        """包装用户查询"""
        try:
            return self.template.format(query=query, **kwargs)
        except Exception as e:
            return query

    def set_template(self, template: str):
        """设置包装模板"""
        self.template = template

    def parse_response(self, request: Any, response: Dict[str, Any]) -> Dict[str, Any]:
        """解析响应"""
        # 提取响应字段
        return {
            "query": getattr(request, "query", ""),
            "response": response.get("response", ""),
            "action": response.get("action", ""),
            "expression": response.get("expression", "")
        }