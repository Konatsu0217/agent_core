# orchestrator/session_orchestrator.py
import asyncio
import uuid
import dataclasses
from typing import Dict, Optional
from datetime import datetime

from src.coordinator.work_flow_engine import WorkflowEngine
from src.domain.agent_data_models import AgentRequest
from src.domain.events import (
    ServiceEventEnvelope, ServerEventType, StatePayload, ClientEventType, ClientEventEnvelope,
    ClientEventPayload, ServiceEventPayload, HeartbeatPayload, TextDeltaPayload, ThinkDeltaPayload,
    ToolCallPayload, ToolResultPayload, FinalPayload, ApprovalRequiredPayload, ApprovalDecisionPayload,
    ErrorPayload, ToolApprovalPayload
)
from src.infrastructure.utils.connet_manager import get_ws_manager
from src.infrastructure.utils.pipe import ProcessPipe, AgentEvent
from src.main.runtime import RuntimeSession

class SessionOrchestrator:
    """会话编排器 - 只负责连接、转发、插件触发"""

    def __init__(
            self,
            workflow_engine: WorkflowEngine,  # AgentCoordinator 的接口
    ):
        self.engine = workflow_engine
        self.ws = get_ws_manager()

        # 会话状态
        self.active_sessions: Dict[str, RuntimeSession] = {}

    async def handle_client_message(
            self,
            session_id: str,
            message: ClientEventEnvelope
    ):
        """处理客户端消息"""
        event_type = message.type
        match event_type:
            case ClientEventType.USER_MESSAGE:
                await self.handle_user_message(session_id, message.payload)

            case ClientEventType.INIT_SESSION:
                await self.handle_session_init(session_id, message.payload)

            case ClientEventType.ATTACH_SESSION:
                await self.handle_attach_session(session_id, message.payload)

            case ClientEventType.DETACH_SESSION:
                await self.handle_detach_session(session_id, message.payload)

            case ClientEventType.DELETE_SESSION:
                await self.handle_delete_session(session_id, message.payload)

            case ClientEventType.HEARTBEAT:
                await self.handle_heartbeat(session_id, message.payload)

            case ClientEventType.TOOL_APPROVAL:
                await self.handle_tool_approval(session_id, message.payload)

            case _:
                print(f"未处理事件类型: {event_type}")

    async def handle_session_init(self, session_id: str, payload: ClientEventPayload):
        """处理会话初始化"""
        session = RuntimeSession(
            session_id=session_id,
            plugin_config=payload.plugin_config,
        )

        # 存一下会话
        self.active_sessions[session_id] = session

        # 发送确认
        await self._send_event(session_id, ServiceEventEnvelope(
            session_id=session_id,
            event_id=str(uuid.uuid4()),
            type=ServerEventType.STATE,
            ts=datetime.now().timestamp(),
            source="system",
            payload=StatePayload(
                phase="initialized",
                progress=0.0
            )
        ))

    async def handle_attach_session(self, session_id: str, payload: ClientEventPayload):
        """处理会话连接"""
        if session_id not in self.active_sessions:
            # 尝试恢复会话或新建会话
            session = RuntimeSession(session_id=session_id)
            self.active_sessions[session_id] = session
        
        # 发送当前状态
        await self._send_event(session_id, ServiceEventEnvelope(
            session_id=session_id,
            event_id=str(uuid.uuid4()),
            type=ServerEventType.STATE,
            ts=datetime.now().timestamp(),
            source="system",
            payload=StatePayload(
                phase="attached",
                progress=0.0
            )
        ))

    async def handle_detach_session(self, session_id: str, payload: ClientEventPayload):
        """处理会话断开"""
        if session_id in self.active_sessions:
            await self._send_event(session_id, ServiceEventEnvelope(
                session_id=session_id,
                event_id=str(uuid.uuid4()),
                type=ServerEventType.STATE,
                ts=datetime.now().timestamp(),
                source="system",
                payload=StatePayload(
                    phase="detached",
                    progress=0.0
                )
            ))
            session = self.active_sessions[session_id]
            session.release()
            del self.active_sessions[session_id]

    async def handle_delete_session(self, session_id: str, payload: ClientEventPayload):
        """处理会话删除"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.delete()
            del self.active_sessions[session_id]
            
            # 发送最后确认
            try:
                await self._send_event(session_id, ServiceEventEnvelope(
                    session_id=session_id,
                    event_id=str(uuid.uuid4()),
                    type=ServerEventType.STATE,
                    ts=datetime.now().timestamp(),
                    source="system",
                    payload=StatePayload(
                        phase="deleted",
                        progress=1.0
                    )
                ))
            except Exception:
                pass

    async def handle_heartbeat(self, session_id: str, payload: ClientEventPayload):
        """处理心跳"""
        await self._send_event(session_id, ServiceEventEnvelope(
            session_id=session_id,
            event_id=str(uuid.uuid4()),
            type=ServerEventType.HEARTBEAT,
            ts=datetime.now().timestamp(),
            source="system",
            payload=StatePayload(
                phase="heartbeat",
            )
        ))

    async def handle_tool_approval(self, session_id: str, payload: ClientEventPayload):
        """处理工具审批"""
        if isinstance(payload, ToolApprovalPayload):
            await self._handle_approval_decision(session_id, payload)

    async def handle_user_message(
            self,
            session_id: str,
            payload: ClientEventPayload
    ):
        """
        处理用户消息 - 核心转发逻辑
        """
        session = self.active_sessions.get(session_id)
        if not session:
            session = RuntimeSession(session_id=session_id)
            self.active_sessions[session_id] = session

        # 1. 生成 request_id
        request_id = self._generate_request_id()

        # 2. 创建 ProcessPipe
        pipe = self.active_sessions[session_id].createPipe()

        # 3. 构建标准请求
        # UserMessagePayload 使用 text 字段
        query_text = getattr(payload, 'text', '')
        request = AgentRequest(
            query=query_text,
            session_id=session_id,
        )

        # 4. 启动两个并发任务
        await asyncio.gather(
            # 任务 A: 调用工作流引擎
            self._run_workflow(request, pipe, None),
            # 任务 B: 消费 pipe 事件并转发
            self._consume_and_forward(session, request_id, pipe)
        )

    async def _run_workflow(
            self,
            request: AgentRequest,
            pipe: ProcessPipe,
            agent_name: Optional[str]
    ):
        """调用工作流引擎"""
        try:
            await self.engine.process(request, pipe, agent_name)
        except Exception as e:
            await pipe.error(f"工作流执行失败: {str(e)}")

    async def _consume_and_forward(
            self,
            session: RuntimeSession,
            request_id: str,
            pipe: ProcessPipe
    ):
        """
        消费 pipe 事件并转发

        这里做两件事：
        1. 发送到客户端 (WS)
        2. 发布到内部事件总线 (EventBus)
        """
        session.buffer = []

        async for event in pipe.reader():
            event_type = self._map_to_ws_event_type(event["type"])
            event_payload = None
            
            # 映射事件内容到 ServiceEventPayload
            if event["type"] == "text_delta":
                chunk = event["payload"].get("text", "")
                session.buffer.append(chunk)
                print(f"\033[31m{chunk}\033[0m", end="", flush=True)
                event_payload = TextDeltaPayload(text=chunk)
                
            elif event["type"] == "think_delta":
                chunk = event["payload"].get("text", "")
                event_payload = ThinkDeltaPayload(text=chunk)

            elif event["type"] == "tool_call":
                event_payload = ToolCallPayload(
                    name=event["payload"].get("name"),
                    arguments=event["payload"].get("arguments")
                )
                
            elif event["type"] == "tool_result":
                event_payload = ToolResultPayload(
                    name=event["payload"].get("name"),
                    success=event["payload"].get("success"),
                    result=event["payload"].get("result")
                )
                
            elif event["type"] == "final":
                event_payload = FinalPayload(
                    text=event["payload"].get("text", ""),
                    structured=event["payload"].get("structured")
                )
                
            elif event["type"] == "approval_required":
                approval_id = event["payload"].get("approval_id", "")
                event_payload = ApprovalRequiredPayload(
                    approval_id=approval_id,
                    name=event["payload"].get("name"),
                    arguments=event["payload"].get("arguments"),
                    message=event["payload"].get("message"),
                    safety_assessment=event["payload"].get("safety_assessment")
                )
                
            elif event["type"] == "approval_decision":
                event_payload = ApprovalDecisionPayload(
                    approval_id=event["payload"].get("approval_id"),
                    decision=event["payload"].get("decision"),
                    message=event["payload"].get("message")
                )
                
            elif event["type"] == "error":
                event_payload = ErrorPayload(
                    code=event["payload"].get("code"),
                    message=event["payload"].get("message"),
                    recoverable=event["payload"].get("recoverable"),
                    detail=event["payload"].get("detail")
                )
            
            if event_payload:
                # 发送到客户端
                await self._send_event(session.session_id, ServiceEventEnvelope(
                    session_id=session.session_id,
                    event_id=str(uuid.uuid4()),
                    type=event_type,
                    ts=datetime.now().timestamp(),
                    source="agent",
                    payload=event_payload
                ))

            # 发布到内部事件总线（供插件消费）
            # 仅通过 RuntimeSession 侧调用
            if hasattr(session, 'event_bus'):
                session.event_bus.publish(
                    f"agent.{event['type']}",
                    {
                        "session_id": session.session_id,
                        "request_id": request_id,
                        "event": event
                    }
                )

    async def _handle_approval_decision(
            self,
            session_id: str,
            message: ToolApprovalPayload
    ):
        """处理审批决策"""
        session = self.active_sessions.get(session_id)
        if not session:
            return

        approval_id = message.approval_id
        pipe = session.pipe

        if pipe:
            # 回传决策给 pipe
            await pipe.approval_decision(
                approval_id=approval_id,
                approved=message.decision,
                reason=message.message
            )
            # # 清理(需要吗，这里会不会阻塞其他会话？）
            # del session.pending_approvals[approval_id]

    async def _handle_cancel(self, session_id: str, request_id: str):
        """处理取消请求"""
        session = self.active_sessions.get(session_id)
        if session and hasattr(session, 'event_bus'):
             session.event_bus.publish(
                 "request.cancel",
                 {"request_id": request_id}
             )

    @staticmethod
    def _generate_request_id() -> str:
        """生成唯一请求 ID"""
        return f"req_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _map_to_ws_event_type(event_type: str) -> ServerEventType:
        """将内部事件映射为 WebSocket 事件类型"""
        event_map = {
            "text_delta": ServerEventType.AGENT_TEXT_DELTA,
            "think_delta": ServerEventType.AGENT_THINK_DELTA,
            "tool_call": ServerEventType.AGENT_TOOL_CALL,
            "tool_result": ServerEventType.AGENT_TOOL_RESULT,
            "approval_required": ServerEventType.AGENT_APPROVAL_REQUIRED,
            "approval_decision": ServerEventType.AGENT_APPROVAL_DECISION,
            "final": ServerEventType.FINAL,
            "error": ServerEventType.ERROR,
        }
        return event_map.get(event_type, ServerEventType.ERROR)

    async def _send_event(self, session_id: str, envelope: ServiceEventEnvelope):
        """发送事件到客户端，处理序列化"""
        try:
            # 转换为 dict 以便 JSON 序列化
            data = dataclasses.asdict(envelope)
            await self.ws.send_event_to(session_id, data)
        except Exception as e:
            print(f"发送消息失败: {e}")
