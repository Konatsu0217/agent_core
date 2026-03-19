/**
 * Amadues WebSocket Client
 *
 * 严格适配 agent_core 后端 /ws/agent 端点，
 * 遵循 events.py + back_end.py + session_orchestrator.py 定义的协议。
 *
 * 关键协议细节：
 * - _parse_client_event 从顶层 message 取 session_id 和 agent_id
 * - InitSessionPayload: {user_id?, agent_id?, metadata?, plugin_config?}
 * - AudioDeltaPayload: {audio: base64, text?, end: bool}  (无 job_id)
 * - StatePayload: {state?, phase?, progress?, avatar_url?}
 * - ExpressionDeltaPayload: {action?, expression?, intensity?}
 */

// ── 协议类型定义 ──

export type ClientEventType =
  | 'init_session'
  | 'attach_session'
  | 'user_message'
  | 'tool_approval'
  | 'heartbeat'
  | 'detach_session'
  | 'delete_session';

export type ServerEventType =
  | 'text_delta'
  | 'think_delta'
  | 'tool_call'
  | 'tool_result'
  | 'approval_required'
  | 'approval_decision'
  | 'heartbeat'
  | 'final'
  | 'error'
  | 'usage'
  | 'state'
  | 'audio_delta'
  | 'expression_delta';

/**
 * 客户端 → 服务端 信封格式
 * 对应 back_end.py._parse_client_event 解析逻辑
 */
export interface ClientEventEnvelope {
  event_id: string;
  session_id: string;       // 顶层必填，_parse_client_event 首先取这里
  agent_id?: string;        // 顶层 agent_id，session_orchestrator 从 envelope.agent_id 取
  type: ClientEventType;
  ts: number;
  source: 'client';
  payload: Record<string, any>;
  trace_id?: string;
  version: string;
}

/**
 * 服务端 → 客户端 信封格式
 * 对应 ServiceEventEnvelope
 */
export interface ServerEventEnvelope {
  event_id: string;
  session_id: string;
  type: ServerEventType;
  ts: number;
  source: 'agent' | 'system' | 'tool';
  payload: Record<string, any>;
  trace_id?: string;
  version: string;
}

// ── Payload 类型（对齐 events.py 中的 dataclass）──

export interface StatePayload {
  state?: string;
  phase?: string;
  progress?: number;
  avatar_url?: string;
}

export interface TextDeltaPayload {
  text: string;
}

export interface ThinkDeltaPayload {
  text: string;
}

export interface ToolCallPayload {
  name: string;
  arguments: any;
}

export interface ToolResultPayload {
  name: string;
  success: boolean;
  result: any;
}

export interface AudioDeltaPayload {
  audio: string;        // base64 编码的音频数据
  text?: string;        // 仅 end=true 时携带完整文本
  end: boolean;
}

export interface ExpressionDeltaPayload {
  action?: string;
  expression?: string;
  intensity?: number;
}

export interface FinalPayload {
  text: string;
  structured?: Record<string, any>;
}

export interface ErrorPayload {
  code?: string;
  message: string;
  recoverable?: boolean;
  detail?: Record<string, any>;
}

export interface ApprovalRequiredPayload {
  approval_id: string;
  name: string;
  arguments: any;
  message?: string;
  safety_assessment?: Record<string, any>;
}

// ── 事件回调 ──

export interface AmaduesEventHandlers {
  onStateChange?: (payload: StatePayload, sessionId: string) => void;
  onTextDelta?: (payload: TextDeltaPayload, sessionId: string) => void;
  onThinkDelta?: (payload: ThinkDeltaPayload, sessionId: string) => void;
  onToolCall?: (payload: ToolCallPayload, sessionId: string) => void;
  onToolResult?: (payload: ToolResultPayload, sessionId: string) => void;
  onAudioDelta?: (payload: AudioDeltaPayload, sessionId: string) => void;
  onExpressionDelta?: (payload: ExpressionDeltaPayload, sessionId: string) => void;
  onFinal?: (payload: FinalPayload, sessionId: string) => void;
  onError?: (payload: ErrorPayload, sessionId: string) => void;
  onApprovalRequired?: (payload: ApprovalRequiredPayload, sessionId: string) => void;
  onHeartbeat?: (payload: StatePayload, sessionId: string) => void;
  onConnected?: () => void;
  onDisconnected?: (code: number, reason: string) => void;
}

// ── WebSocket Client ──

export class AmaduesWSClient {
  private ws: WebSocket | null = null;
  private sessionId: string = '';
  private agentId: string = '';
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectDelay: number = 2000;

  constructor(
    private url: string,
    private handlers: AmaduesEventHandlers = {},
  ) {}

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get currentSessionId(): string {
    return this.sessionId;
  }

  // ── 连接管理 ──

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('[WS] Connected to', this.url);
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.handlers.onConnected?.();
    };

    this.ws.onmessage = (event) => {
      try {
        const data: ServerEventEnvelope = JSON.parse(event.data);
        this.dispatch(data);
      } catch (e) {
        console.error('[WS] Failed to parse message:', e);
      }
    };

    this.ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code, event.reason);
      this.stopHeartbeat();
      this.handlers.onDisconnected?.(event.code, event.reason);
      this.scheduleReconnect();
    };

    this.ws.onerror = (event) => {
      console.error('[WS] Error:', event);
    };
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // prevent reconnect
    this.ws?.close(1000, 'client disconnect');
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnect attempts reached');
      return;
    }
    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts);
    this.reconnectAttempts++;
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  // ── 心跳 ──

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.sessionId) {
        this.send('heartbeat', {
          session_id: this.sessionId,
          client_time: Date.now() / 1000,
        });
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // ── 发送消息 ──

  /**
   * 构建并发送 ClientEventEnvelope。
   *
   * 关键：agent_id 放在顶层（envelope.agent_id），
   *       session_id 同时放顶层和 payload（back_end.py 两处都检查）。
   */
  private send(type: ClientEventType, payload: Record<string, any> = {}): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[WS] Not connected, cannot send:', type);
      return;
    }

    const sid = this.sessionId || payload.session_id || '';

    const envelope: ClientEventEnvelope = {
      event_id: this.generateId(),
      session_id: sid,
      agent_id: this.agentId || undefined,  // 顶层 agent_id
      type,
      ts: Date.now() / 1000,
      source: 'client',
      payload,
      version: '1.0',
    };

    console.log('[WS] Sending:', type, JSON.stringify(envelope).slice(0, 300));
    this.ws.send(JSON.stringify(envelope));
  }

  /**
   * 初始化新 session
   *
   * 对应 InitSessionPayload: {user_id?, agent_id?, metadata?, plugin_config?}
   * agent_id 同时放在 envelope 顶层和 payload 中（双保险）。
   * session_id 由前端预生成（_parse_client_event 强制要求）。
   */
  initSession(agentId: string = 'fast_agent_v1', pluginConfig?: Record<string, any>): void {
    this.sessionId = this.generateUUID();
    this.agentId = agentId;
    this.send('init_session', {
      agent_id: agentId,
      plugin_config: pluginConfig || null,
    });
  }

  /**
   * 恢复已有 session
   *
   * 对应 AttachSessionPayload: {session_id, agent_id?, metadata?}
   */
  attachSession(sessionId: string, agentId: string = 'fast_agent_v1'): void {
    this.sessionId = sessionId;
    this.agentId = agentId;
    this.send('attach_session', {
      session_id: sessionId,
      metadata: {},
    });
  }

  /**
   * 发送用户消息
   *
   * 对应 UserMessagePayload: {text, session_id, attachments?, metadata?}
   */
  sendMessage(text: string, attachments?: any[], metadata?: Record<string, any>): void {
    if (!this.sessionId) {
      console.warn('[WS] No session, init first');
      return;
    }
    this.send('user_message', {
      text,
      session_id: this.sessionId,
      attachments: attachments || null,
      metadata: metadata || null,
    });
  }

  /**
   * 发送工具审批决策
   *
   * 对应 ToolApprovalPayload: {approval_id, session_id, decision, message?}
   */
  sendToolApproval(approvalId: string, decision: 'approved' | 'rejected', message?: string): void {
    if (!this.sessionId) return;
    this.send('tool_approval', {
      approval_id: approvalId,
      session_id: this.sessionId,
      decision,
      message: message || null,
    });
  }

  /**
   * 断开会话
   */
  detachSession(): void {
    if (!this.sessionId) return;
    this.send('detach_session', {
      session_id: this.sessionId,
      reason: 'client_detach',
    });
  }

  /**
   * 删除会话
   */
  deleteSession(): void {
    if (!this.sessionId) return;
    this.send('delete_session', {
      session_id: this.sessionId,
      reason: 'client_delete',
    });
  }

  // ── 事件分发 ──

  private dispatch(event: ServerEventEnvelope): void {
    const { type, payload, session_id } = event;

    // 自动绑定 session_id（后端 state 事件带回 session_id）
    if (session_id && type === 'state') {
      if (!this.sessionId || this.sessionId !== session_id) {
        this.sessionId = session_id;
        console.log('[WS] Session bound:', session_id);
      }
    }

    switch (type) {
      case 'state':
        this.handlers.onStateChange?.(payload as StatePayload, session_id);
        break;
      case 'text_delta':
        this.handlers.onTextDelta?.(payload as TextDeltaPayload, session_id);
        break;
      case 'think_delta':
        this.handlers.onThinkDelta?.(payload as ThinkDeltaPayload, session_id);
        break;
      case 'tool_call':
        this.handlers.onToolCall?.(payload as ToolCallPayload, session_id);
        break;
      case 'tool_result':
        this.handlers.onToolResult?.(payload as ToolResultPayload, session_id);
        break;
      case 'audio_delta':
        this.handlers.onAudioDelta?.(payload as AudioDeltaPayload, session_id);
        break;
      case 'expression_delta':
        this.handlers.onExpressionDelta?.(payload as ExpressionDeltaPayload, session_id);
        break;
      case 'final':
        this.handlers.onFinal?.(payload as FinalPayload, session_id);
        break;
      case 'error':
        this.handlers.onError?.(payload as ErrorPayload, session_id);
        break;
      case 'approval_required':
        this.handlers.onApprovalRequired?.(payload as ApprovalRequiredPayload, session_id);
        break;
      case 'heartbeat':
        this.handlers.onHeartbeat?.(payload as StatePayload, session_id);
        break;
      default:
        console.log('[WS] Unknown event type:', type, payload);
    }
  }

  private generateId(): string {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  /** 生成 UUID v4 */
  private generateUUID(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}
