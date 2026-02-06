# 前端接入与消息协议规范（WebSocket）

## 1. 连接方式
- 连接地址：`ws://<host>/ws/agent`
- 连接后无需额外握手，但第一条业务消息应包含 session_id
- 断开后可重连，重连后发送 attach_session 复用已有 session_id

## 1.1 外部连接 403 排查要点
- 路径错误：仅支持 `/ws/agent`，连接 `/ws` 会在路由匹配前失败
- 非 WebSocket 握手：必须使用 WS 客户端发起 Upgrade 请求
- 反向代理未放行 Upgrade：需透传 `Upgrade` 与 `Connection` 头
- Origin 策略：浏览器环境需要代理/网关允许对应 Origin

### Nginx 参考配置
```nginx
location /ws/agent {
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_set_header Host $host;
  proxy_read_timeout 3600s;
  proxy_pass http://127.0.0.1:38888;
}
```

## 2. 通用 Envelope 结构（Client/Server 共用）
```json
{
  "event_id": "string",
  "session_id": "string",
  "type": "string",
  "ts": 1730000000.123,
  "source": "client | system | agent | tool",
  "payload": {},
  "trace_id": "string",
  "version": "1.0"
}
```
- session_id：必填。后端会从顶层 session_id 或 payload.session_id 取值，uuid 格式
- event_id：前端可不传，后端会补生成
- ts：前端可不传，后端会补当前时间戳
- source：客户端应为 client
- trace_id：可选，用于链路追踪
- version：可选，默认 "1.0"

## 3. Client → Server 事件类型与 Payload

### 3.1 init_session（初始化会话）
```json
{
  "type": "init_session",
  "session_id": "s_123",
  "payload": {
    "user_id": "u_1",
    "agent_id": "agent_x",
    "metadata": {},
    "plugin_config": {}
  }
}
```

### 3.2 attach_session（绑定已有会话）
```json
{
  "type": "attach_session",
  "session_id": "s_123",
  "payload": {
    "session_id": "s_123",
    "metadata": {}
  }
}
```

### 3.3 user_message（发送用户消息）
```json
{
  "type": "user_message",
  "session_id": "s_123",
  "payload": {
    "text": "你好",
    "session_id": "s_123",
    "attachments": [],
    "metadata": {}
  }
}
```

### 3.4 tool_approval（工具审批回传）
```json
{
  "type": "tool_approval",
  "session_id": "s_123",
  "payload": {
    "approval_id": "ap_456",
    "session_id": "s_123",
    "decision": "approved | rejected",
    "message": "optional"
  }
}
```

### 3.5 heartbeat（心跳）
```json
{
  "type": "heartbeat",
  "session_id": "s_123",
  "payload": {
    "session_id": "s_123",
    "client_time": 1730000000.123
  }
}
```

### 3.6 detach_session（断开会话）
```json
{
  "type": "detach_session",
  "session_id": "s_123",
  "payload": {
    "session_id": "s_123",
    "reason": "optional"
  }
}
```

### 3.7 delete_session（删除会话）
```json
{
  "type": "delete_session",
  "session_id": "s_123",
  "payload": {
    "session_id": "s_123",
    "reason": "optional"
  }
}
```

## 4. Server → Client 事件类型与 Payload

### 4.1 文本流增量 text_delta
```json
{
  "type": "text_delta",
  "payload": { "text": "分片文本" }
}
```

### 4.2 思考流增量 think_delta
```json
{
  "type": "think_delta",
  "payload": { "text": "思考片段" }
}
```

### 4.3 工具调用 tool_call
```json
{
  "type": "tool_call",
  "payload": { "name": "search", "arguments": { "q": "xxx" } }
}
```

### 4.4 工具结果 tool_result
```json
{
  "type": "tool_result",
  "payload": { "name": "search", "success": true, "result": {} }
}
```

### 4.5 工具审批请求 approval_required
```json
{
  "type": "approval_required",
  "payload": {
    "approval_id": "ap_456",
    "name": "tool_name",
    "arguments": {},
    "message": "optional",
    "safety_assessment": {}
  }
}
```

### 4.6 工具审批结果回显 approval_decision
```json
{
  "type": "approval_decision",
  "payload": {
    "approval_id": "ap_456",
    "decision": "approved | rejected",
    "message": "optional"
  }
}
```

### 4.7 最终回复 final
```json
{
  "type": "final",
  "payload": {
    "text": "最终回复",
    "structured": {}
  }
}
```

### 4.8 错误 error
```json
{
  "type": "error",
  "payload": {
    "code": "optional",
    "message": "错误描述",
    "recoverable": true,
    "detail": {}
  }
}
```

### 4.9 心跳 heartbeat
```json
{
  "type": "heartbeat",
  "payload": {
    "phase": "heartbeat"
  }
}
```

### 4.10 会话状态 state
```json
{
  "type": "state",
  "payload": {
    "phase": "initialized | attached | detached | deleted",
    "progress": 0.0
  }
}
```

## 5. 推荐时序
1. WS 连接 /ws
2. 发送 init_session（或有历史则直接 attach_session）
3. 发送 user_message
4. 接收 text_delta/think_delta 流式输出
5. 接收 final 结束
6. 断开时发送 detach_session；需要清理时发送 delete_session

## 6. 审批回路（可选）
- 服务端发 approval_required → 前端弹框 → 发送 tool_approval
- 服务端可能回 approval_decision 做回显

## 7. 注意事项
- session_id 必须在顶层或 payload 中携带
- event_id/ts 可由前端或后端自动生成，建议前端生成便于链路追踪
- 后端当前会忽略解析失败的消息，不会返回错误包

## 8. 来源参考
- src/main/back_end.py
- src/domain/events.py
