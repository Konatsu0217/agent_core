"""
Built-in skill registry.

Manages registration, discovery, and dispatch of built-in skills that run
in-process (no external MCP server needed). Each skill exposes:
  - An async callable:   async def handler(arguments: dict) -> dict
  - A tool schema:       OpenAI function-calling compatible dict
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BuiltinSkill:
    """Descriptor for one built-in skill."""
    name: str
    description: str
    schema: Dict[str, Any]  # OpenAI function-calling tool schema
    handler: Callable[..., Coroutine[Any, Any, Dict[str, Any]]]


class SkillRegistry:
    """
    Singleton-style registry for built-in skills.

    Usage:
        registry = SkillRegistry()
        registry.auto_register()          # load all bundled skills
        tools = registry.list_schemas()   # for merging into tool list
        result = await registry.call("websearch", {"query": "hello"})
    """

    def __init__(self):
        self._skills: Dict[str, BuiltinSkill] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, skill: BuiltinSkill) -> None:
        """Register a single built-in skill."""
        if skill.name in self._skills:
            logger.warning("Overwriting existing built-in skill: %s", skill.name)
        self._skills[skill.name] = skill
        logger.info("Registered built-in skill: %s", skill.name)

    def auto_register(self) -> None:
        """
        Auto-discover and register all bundled skills.
        Add new skills here as they are created.
        """
        self._register_websearch()
        # Future skills:
        # self._register_calculator()
        # self._register_code_interpreter()

    def _register_websearch(self) -> None:
        try:
            # FIX: use correct package path (src.skills, not skills)
            from src.skills.websearch import websearch, TOOL_SCHEMA

            async def _handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
                return await websearch(**arguments)

            self.register(BuiltinSkill(
                name="websearch",
                description=TOOL_SCHEMA["function"]["description"],
                schema=TOOL_SCHEMA,
                handler=_handler,
            ))
        except ImportError as e:
            logger.warning("Failed to import websearch skill: %s", e)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------
    def list_names(self) -> List[str]:
        """Return names of all registered skills."""
        return list(self._skills.keys())

    def list_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas suitable for merging into LLM tool list."""
        return [s.schema for s in self._skills.values()]

    def get(self, name: str) -> Optional[BuiltinSkill]:
        """Retrieve skill by name."""
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        return name in self._skills

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    async def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a built-in skill by name.
        Raises KeyError if skill not found.
        """
        skill = self._skills.get(name)
        if not skill:
            raise KeyError(f"Built-in skill not found: {name}")
        try:
            return await skill.handler(arguments)
        except Exception as e:
            logger.error("Built-in skill '%s' execution error: %s", name, e, exc_info=True)
            return {"error": f"Skill execution error: {e}"}
