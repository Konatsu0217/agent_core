import json
import uuid
from datetime import datetime, timedelta
# from utils.logger import get_logger


class SessionManager:
    """
        会话管理Manager

        后续可加上可持续化db实现话题中断恢复
    """

    def __init__(self):
        self.active_sessions: dict[str, dict[str, list[dict[str, str]]]] = {}
        self.update_time: dict[str, datetime] = {}

    async def get_session(self, session_id: str, agent_id: str, limit: int = 0) -> dict[str, list[dict[str, str]]]:
        """
        读取历史记录

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID
            limit: 获取的记录数量；默认为0，代表不限制数目，返回所有记录

        Returns:
            {"messages": [{"role": "user", "content": "..."}, ...]}
        """
        if session_id in self.active_sessions:
            agent_session = self.active_sessions[session_id]
            if agent_id in agent_session:
                await self._update_last_used(session_id, agent_id)
                if limit > 0:
                    count = min(limit, len(agent_session[agent_id]))
                    return {"messages": agent_session[agent_id][0:count]}
                else:
                    return {"messages": agent_session[agent_id]}
        return {}

    async def get_all_sessions(self) -> list[dict[str, any]]:
        """
        读取全量历史记录

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID
            limit: 获取的记录数量；默认为0，代表不限制数目，返回所有记录

        Returns:
            [
                {
                    "session_id": "{session_id}",
                    "agent_id": "{agent_id}",
                    "messages": [{"role": "user", "content": "..."}, ...]
                }，
                ...
            ]
        """
        result = []
        for session_id in self.active_sessions:
            agent_session = self.active_sessions[session_id]
            for agent_id in agent_session:
                messages = agent_session[agent_id]
                result.append({
                    "session_id": session_id,
                    "agent_id": agent_id,
                    # "messages": messages
                    "messages": json.dumps(messages)
                })
        return result

    async def add_session_value(self, session_id: str, agent_id: str, value: dict[str, str]):
        """
        添加历史记录

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID
            value: 历史记录
        """
        if session_id in self.active_sessions:
            agent_session = self.active_sessions[session_id]
            if agent_id in agent_session:
                agent_session[agent_id].append(value)
            else:
                agent_session[agent_id] = []
                agent_session[agent_id].append(value)
        else:
            self.active_sessions[session_id] = {}
            agent_session = self.active_sessions[session_id]
            agent_session[agent_id] = []
            agent_session[agent_id].append(value)
        await self._update_last_used(session_id, agent_id)

    async def modify_session_value(self, session_id: str, agent_id: str, value: list[dict[str, str]]):
        """
        全量修改历史记录

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID
            value: 历史记录
        """
        if session_id in self.active_sessions:
            agent_session = self.active_sessions[session_id]
            agent_session[agent_id] = value
        else:
            self.active_sessions[session_id] = {}
            agent_session = self.active_sessions[session_id]
            agent_session[agent_id] = value
        await self._update_last_used(session_id, agent_id)

    async def delete_session(self, session_id: str, agent_id: str = None) -> bool:
        """
        清空session历史记录

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID；默认为空，则代表删除session_id下所有agent的历史记录

        Returns:
            是否删除成功
        """
        if session_id in self.active_sessions:
            if not agent_id:
                del self.active_sessions[session_id]
                await self._delete_last_used(session_id)
                return True
            else:
                agent_session = self.active_sessions[session_id]
                if agent_id in agent_session:
                    del agent_session[agent_id]
                    await self._delete_last_used(session_id, agent_id)
                    return True
        return False

    async def clean_old_sessions(self, expired_days: int = 30) -> int:
        """
        清理过期的历史记录

        Args:
            expired_days: 清理多少天前未使用的历史记录

        Returns:
            删除的会话数量
        """
        count = 0
        delete_agents = []
        expired_time = datetime.utcnow() - timedelta(days=expired_days)
        for session_id in self.update_time:
            session_update_time = self.update_time[session_id]
            for agent_id in session_update_time:
                agent_session_update_time = session_update_time[agent_id]
                if agent_session_update_time < expired_time:
                    delete_agents.append(agent_id)
                    count += 1
            for agent_id in delete_agents:
                await self.delete_session(session_id, agent_id)
        return count

    async def _update_last_used(self, session_id: str, agent_id: str):
        """
        更新记录最近使用时间

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID
        """
        if session_id in self.update_time:
            agent_session_update_time = self.update_time[session_id]
            agent_session_update_time[agent_id] = datetime.utcnow()
        else:
            self.update_time[session_id] = {}
            agent_session_update_time = self.update_time[session_id]
            agent_session_update_time[agent_id] = datetime.utcnow()

    async def _delete_last_used(self, session_id: str, agent_id: str = None):
        """
        删除最近使用时间

        Args:
            session_id: 会话ID
            agent_id: agent的唯一标识ID；默认为空，则代表删除session_id下所有agent的最近使用时间
        """
        if session_id in self.update_time:
            if not agent_id:
                del self.update_time[session_id]
            else:
                agent_session_update_time = self.update_time[session_id]
                if agent_id in agent_session_update_time:
                    del agent_session_update_time[agent_id]


manager = SessionManager()

def get_session_manager():
    return manager


if __name__ == "__main__":
    manager = SessionManager()
    # get_logger().info("获取所有历史记录:", manager.get_all_sessions())

    # 测试保存历史记录
    test_session_id = "test-session-" + str(datetime.utcnow())
    test_agent_id = "test-agent-" + str(datetime.utcnow())
    test_value = {
        "role": "user",
        "content": "user enter agent1 test content that has no means"
    }
    manager.add_session_value(test_session_id, test_agent_id, test_value)
    print(f"保存历史记录，session_id: {test_session_id}，agent_id：{test_agent_id}")
    test_second_value = {
        "role": "user",
        "content": "user enter another agent1 test content that has no means"
    }
    manager.add_session_value(test_session_id, test_agent_id, test_second_value)
    print(f"保存历史记录，session_id: {test_session_id}，agent_id：{test_agent_id}")
    test_new_agent_id = "test-agent-" + str(datetime.utcnow())
    new_agent_test_value = {
        "role": "user",
        "content": "user enter agent2 test content that has no means"
    }
    manager.add_session_value(test_session_id, test_new_agent_id, new_agent_test_value)
    print(f"保存历史记录，session_id: {test_session_id}，agent_id：{test_new_agent_id}")

    # 测试获取所有历史记录
    print("获取所有历史记录:", manager.get_all_sessions())

    # 测试删除session维度历史记录
    if manager.delete_session(test_session_id):
        print(f"删除session历史记录成功，session_id: {test_session_id}")
    else:
        print(f"删除session历史记录失败！session_id: {test_session_id}")

    # 测试获取所有历史记录
    print("获取所有历史记录:", manager.get_all_sessions())

    # 测试修改历史记录
    test_new_value = [
        {
            "role": "user",
            "content": "user enter agent1 new test content that has no means"
        },
        {
            "role": "user",
            "content": "user enter agent1 another new test content that has no means"
        }
    ]
    manager.modify_session_value(test_session_id, test_agent_id, test_new_value)
    print(f"修改历史记录，session_id: {test_session_id}，agent_id：{test_agent_id}")

    # 测试获取历史记录，仅取首个
    session = manager.get_session(test_session_id, test_agent_id, 1)
    print(f"获取修改后的首个历史记录，session_id: {test_session_id}，agent_id：{test_agent_id}，内容：{session}")

    # 测试获取历史记录，无限制
    session = manager.get_session(test_session_id, test_agent_id)
    print(f"获取修改后的历史记录，session_id: {test_session_id}，agent_id：{test_agent_id}，内容：{session}")

    # 测试保存历史记录
    new_agent_test_new_value = {
        "role": "user",
        "content": "user enter another agent2 test content that has no means"
    }
    manager.add_session_value(test_session_id, test_new_agent_id, new_agent_test_new_value)
    print(f"保存历史记录，session_id: {test_session_id}，agent_id：{test_new_agent_id}")

    # 测试删除agent维度历史记录
    if manager.delete_session(test_session_id, test_agent_id):
        print(f"删除agent历史记录成功，session_id: {test_session_id}，agent_id：{test_agent_id}")
    else:
        print(f"删除agent历史记录失败！session_id: {test_session_id}，agent_id：{test_agent_id}")

    # 测试获取所有历史记录
    print("获取所有历史记录:", manager.get_all_sessions())

    # 测试清理过期历史记录
    expired_days = 0
    count = manager.clean_old_sessions(expired_days)
    print(f"清理过期历史记录,过期时间: {expired_days}，清理个数：{count}")

    # 测试获取所有历史记录
    print("获取所有历史记录:", manager.get_all_sessions())