/**
 * Amadues Live2D Virtual Streamer - 主应用
 *
 * 严格适配 agent_core 后端协议:
 * - WebSocket: /ws/agent
 * - StatePayload: {state?, phase?, progress?, avatar_url?}
 * - AudioDeltaPayload: {audio, text?, end}
 * - ExpressionDeltaPayload: {action?, expression?, intensity?}
 */

import {
  AmaduesWSClient,
  type StatePayload,
  type TextDeltaPayload,
  type ThinkDeltaPayload,
  type ToolCallPayload,
  type ToolResultPayload,
  type AudioDeltaPayload,
  type ExpressionDeltaPayload,
  type FinalPayload,
  type ErrorPayload,
  type ApprovalRequiredPayload,
} from './ws-client';
import { AudioPlayer } from './audio-player';
import { Live2DController } from './live2d-controller';
import { SubtitleManager } from './subtitle';

// ── 配置 ──

interface AppConfig {
  wsUrl: string;
  httpBaseUrl: string;
  modelPath: string;
  agentId: string;
}

const DEFAULT_CONFIG: AppConfig = {
  wsUrl: `ws://${window.location.hostname}:${window.location.port || '3000'}/ws/agent`,
  httpBaseUrl: `http://${window.location.hostname}:${window.location.port || '3000'}`,
  modelPath: './models/hiyori/hiyori_pro_jp.model3.json',
  agentId: 'fast_agent_v1',
};

// ── 全局状态 ──

let config: AppConfig = { ...DEFAULT_CONFIG };
let wsClient: AmaduesWSClient;
let audioPlayer: AudioPlayer;
let live2dController: Live2DController | null = null;
let subtitleManager: SubtitleManager;

let isWaitingResponse: boolean = false;
let statusEl: HTMLElement;
let inputEl: HTMLInputElement;
let sendBtn: HTMLButtonElement;
let logEl: HTMLElement;

// ── 日志 ──

function appendLog(tag: string, message: string, type: 'info' | 'warn' | 'error' | 'success' = 'info'): void {
  const line = document.createElement('div');
  line.className = `log-line log-${type}`;
  const time = new Date().toLocaleTimeString();
  line.textContent = `[${time}] [${tag}] ${message}`;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
  while (logEl.children.length > 200) {
    logEl.removeChild(logEl.firstChild!);
  }
}

function setStatus(text: string, type: 'connected' | 'disconnected' | 'thinking' | 'speaking'): void {
  statusEl.textContent = text;
  statusEl.className = `status status-${type}`;
}

function setInputEnabled(enabled: boolean): void {
  inputEl.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function sendMessage(): void {
  const text = inputEl.value.trim();
  if (!text || isWaitingResponse) return;

  isWaitingResponse = true;
  setInputEnabled(false);
  setStatus('思考中...', 'thinking');
  subtitleManager.clear();
  audioPlayer.stop();

  appendLog('USER', text, 'info');
  wsClient.sendMessage(text);
  inputEl.value = '';
}

// ── 初始化 WebSocket ──

function initWebSocket(): void {
  wsClient = new AmaduesWSClient(config.wsUrl, {
    onConnected: () => {
      setStatus('已连接，正在初始化...', 'connected');
      appendLog('WS', '已连接', 'success');
      wsClient.initSession(config.agentId);
    },

    onDisconnected: (code: number, reason: string) => {
      setStatus('已断开连接', 'disconnected');
      setInputEnabled(false);
      isWaitingResponse = false;
      appendLog('WS', `已断开 (${code}: ${reason})`, 'warn');
    },

    /**
     * 对应后端 StatePayload: {state?, phase?, progress?, avatar_url?}
     *
     * 后端 session_orchestrator 在 init 完成后发:
     *   phase="initialized", progress=0.0, avatar_url=...
     * attach 完成后发:
     *   phase="attached", progress=0.0
     */
    onStateChange: (payload: StatePayload, sid: string) => {
      const phase = payload.phase || '';
      const state = payload.state || '';
      const progress = payload.progress ?? 0;
      const avatarUrl = payload.avatar_url || '';

      appendLog('STATE', `phase=${phase} state=${state} progress=${progress} session=${sid?.slice(0, 8) || '?'}`, 'info');

      // session 就绪判断：后端发 phase=initialized 或 phase=attached
      if (phase === 'initialized' || phase === 'attached') {
        setStatus('就绪', 'connected');
        setInputEnabled(true);
        appendLog('WS', `Session 就绪 (${phase}): ${sid?.slice(0, 8) || '?'}...`, 'success');

        // 如果后端返回了 avatar_url，可以在这里使用
        if (avatarUrl) {
          appendLog('STATE', `Avatar: ${avatarUrl}`, 'info');
        }
      } else if (phase === 'detached') {
        setStatus('已断开', 'disconnected');
        setInputEnabled(false);
      } else if (phase === 'deleted') {
        setStatus('会话已删除', 'disconnected');
        setInputEnabled(false);
      }
    },

    onTextDelta: (payload: TextDeltaPayload) => {
      subtitleManager.appendText(payload.text);
    },

    onThinkDelta: (payload: ThinkDeltaPayload) => {
      appendLog('THINK', payload.text, 'info');
    },

    onToolCall: (payload: ToolCallPayload) => {
      appendLog('TOOL', `调用 ${payload.name}(${JSON.stringify(payload.arguments).slice(0, 80)})`, 'info');
    },

    onToolResult: (payload: ToolResultPayload) => {
      const status = payload.success ? '✓' : '✗';
      const resultStr = typeof payload.result === 'string' ? payload.result : JSON.stringify(payload.result);
      appendLog('TOOL', `${status} ${payload.name}: ${resultStr.slice(0, 80)}`, payload.success ? 'info' : 'warn');
    },

    /**
     * 对应后端 AudioDeltaPayload: {audio: string, text?: string, end: boolean}
     *
     * 后端逐 chunk 发送 {audio: "<base64>", end: false}
     * 最终发送 {audio: "", end: true, text: "完整文本"}
     */
    onAudioDelta: (payload: AudioDeltaPayload) => {
      const { audio, text, end } = payload;

      console.log(`[App] audio_delta: end=${end} audioLen=${audio?.length || 0}`);

      if (!end && audio) {
        // 第一个 chunk 时更新状态
        setStatus('说话中...', 'speaking');
      }
      if (end) {
        appendLog('AUDIO', `音频流接收完毕`, 'success');
      }

      // 直接透传给 AudioPlayer
      audioPlayer.handleAudioDelta(payload);
    },

    /**
     * 对应后端 ExpressionDeltaPayload: {action?, expression?, intensity?}
     */
    onExpressionDelta: (payload: ExpressionDeltaPayload) => {
      const parts: string[] = [];
      if (payload.action) parts.push(`action=${payload.action}`);
      if (payload.expression) parts.push(`expr=${payload.expression}`);
      if (payload.intensity !== undefined) parts.push(`intensity=${payload.intensity}`);
      appendLog('EXPR', parts.join(' ') || 'empty', 'info');
      live2dController?.handleExpressionDelta(payload);
    },

    onFinal: (payload: FinalPayload) => {
      isWaitingResponse = false;
      setInputEnabled(true);
      subtitleManager.finalize();
      if (!audioPlayer.isPlaying) {
        setStatus('就绪', 'connected');
      }
      appendLog('FINAL', `对话结束 (text_len=${(payload.text || '').length})`, 'success');
    },

    onError: (payload: ErrorPayload) => {
      isWaitingResponse = false;
      setInputEnabled(true);
      setStatus('就绪', 'connected');
      appendLog('ERROR', `[${payload.code || 'unknown'}] ${payload.message}`, 'error');
      if (payload.detail) {
        appendLog('ERROR', `detail: ${JSON.stringify(payload.detail).slice(0, 120)}`, 'error');
      }
    },

    onApprovalRequired: (payload: ApprovalRequiredPayload) => {
      appendLog('APPROVAL', `需要审批: ${payload.name} (${payload.approval_id})`, 'warn');
      if (payload.message) {
        appendLog('APPROVAL', payload.message, 'warn');
      }
      // TODO: 实现审批 UI，调用 wsClient.sendToolApproval(...)
      // 暂时自动批准
      wsClient.sendToolApproval(payload.approval_id, 'approved');
      appendLog('APPROVAL', `已自动批准: ${payload.approval_id}`, 'success');
    },

    onHeartbeat: () => { /* silent */ },
  });

  appendLog('WS', `正在连接 ${config.wsUrl} ...`, 'info');
  wsClient.connect();
}

// ── 初始化 Live2D ──

async function initLive2D(): Promise<void> {
  const container = document.getElementById('live2d-container')!;

  live2dController = new Live2DController({
    container,
    modelPath: config.modelPath,
  });

  const ok = await live2dController.loadModel();
  if (ok) {
    appendLog('Live2D', '模型加载成功', 'success');
  } else {
    appendLog('Live2D', '模型加载失败（WS 通信不受影响）', 'warn');
  }
}

// ── 主入口 ──

function init(): void {
  statusEl = document.getElementById('status')!;
  inputEl = document.getElementById('user-input') as HTMLInputElement;
  sendBtn = document.getElementById('send-btn') as HTMLButtonElement;
  logEl = document.getElementById('log')!;
  const subtitleContainer = document.getElementById('subtitle')!;

  // 支持 URL 参数覆盖配置
  const params = new URLSearchParams(window.location.search);
  if (params.get('ws')) config.wsUrl = params.get('ws')!;
  if (params.get('http')) config.httpBaseUrl = params.get('http')!;
  if (params.get('model_path')) config.modelPath = params.get('model_path')!;
  if (params.get('agent_id')) config.agentId = params.get('agent_id')!;

  appendLog('APP', `AgentID=${config.agentId}  WS=${config.wsUrl}`, 'info');

  audioPlayer = new AudioPlayer({
    onLipSync: (volume) => {
      live2dController?.setLipSync(volume);
    },
    onPlayStart: (text) => {
      setStatus('说话中...', 'speaking');
      appendLog('TTS', `▶ 播放: ${text.slice(0, 30)}`, 'info');
    },
    onPlayEnd: () => {
      if (!isWaitingResponse) setStatus('就绪', 'connected');
      appendLog('TTS', '■ 播放结束', 'info');
    },
  });

  subtitleManager = new SubtitleManager({
    container: subtitleContainer,
    autoHideDelay: 8000,
  });

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  window.addEventListener('resize', () => {
    const container = document.getElementById('live2d-container')!;
    const rect = container.getBoundingClientRect();
    live2dController?.resize(rect.width, rect.height);
  });

  setStatus('正在连接...', 'disconnected');
  initWebSocket();
  initLive2D();
}

document.addEventListener('DOMContentLoaded', init);
