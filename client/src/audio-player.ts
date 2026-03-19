/**
 * Audio Player - 流式接收 base64 音频 chunk 并播放
 *
 * 适配 agent_core 后端 AudioDeltaPayload: {audio: string, text?: string, end: boolean}
 *
 * 后端行为（session_orchestrator._handle_buffered_tts）：
 * - 每个 TTS chunk 发一个 audio_delta: {audio: "<base64>", end: false}
 * - 所有 chunk 发完后发结束标记: {audio: "", end: true, text: "完整文本"}
 * - 没有 job_id / chunk_index，是无序号的流式推送
 *
 * 播放策略：
 * - 每收到一个非空 audio chunk 立即解码入队
 * - end=true 时标记当前批次完成
 * - 队列顺序播放，保证流畅
 */

export interface AudioPlayerOptions {
  onLipSync?: (volume: number) => void;
  onPlayStart?: (text: string) => void;
  onPlayEnd?: (text: string) => void;
}

export class AudioPlayer {
  private playQueue: Array<{ blob: Blob; text: string }> = [];
  private chunkBuffer: Uint8Array[] = [];  // 累积当前批次的 chunk
  private totalBufferBytes: number = 0;
  private currentBatchText: string = '';
  private playing: boolean = false;
  private currentAudio: HTMLAudioElement | null = null;
  private lipSyncTimer: number | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private sourceNode: MediaElementAudioSourceNode | null = null;
  private options: AudioPlayerOptions;

  constructor(options: AudioPlayerOptions = {}) {
    this.options = options;
  }

  /**
   * 接收一个 audio_delta 事件的 payload。
   *
   * 对应后端 AudioDeltaPayload: {audio: string, text?: string, end: boolean}
   */
  handleAudioDelta(payload: { audio: string; text?: string; end: boolean }): void {
    const { audio, text, end } = payload;

    console.log(`[AudioPlayer] audio_delta: end=${end} dataLen=${audio?.length || 0} text="${(text || '').slice(0, 30)}"`);

    // 收集 base64 chunk
    if (audio && audio.length > 0) {
      try {
        const binary = Uint8Array.from(atob(audio), c => c.charCodeAt(0));
        this.chunkBuffer.push(binary);
        this.totalBufferBytes += binary.length;
        console.log(`[AudioPlayer] chunk#${this.chunkBuffer.length} +${binary.length}B total=${this.totalBufferBytes}B`);
      } catch (e) {
        console.error(`[AudioPlayer] base64 decode error:`, e);
      }
    }

    // end=true 时的 text 字段是完整文本
    if (text) {
      this.currentBatchText = text;
    }

    if (end) {
      // 当前批次结束，拼接并加入播放队列
      if (this.totalBufferBytes > 0) {
        const merged = new Uint8Array(this.totalBufferBytes);
        let offset = 0;
        for (const chunk of this.chunkBuffer) {
          merged.set(chunk, offset);
          offset += chunk.length;
        }
        const blob = new Blob([merged], { type: 'audio/mpeg' });
        console.log(`[AudioPlayer] batch done: ${this.chunkBuffer.length} chunks, ${this.totalBufferBytes} bytes`);
        this.playQueue.push({ blob, text: this.currentBatchText });

        if (!this.playing) {
          console.log(`[AudioPlayer] 开始播放队列 (queue=${this.playQueue.length})`);
          this.playNext();
        } else {
          console.log(`[AudioPlayer] 已在播放中，加入队列 (queue=${this.playQueue.length})`);
        }
      } else {
        console.warn(`[AudioPlayer] end=true 但没有累积音频数据`);
      }

      // 重置缓冲区
      this.chunkBuffer = [];
      this.totalBufferBytes = 0;
      this.currentBatchText = '';
    }
  }

  stop(): void {
    this.chunkBuffer = [];
    this.totalBufferBytes = 0;
    this.currentBatchText = '';
    this.playQueue = [];
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.stopLipSync();
    this.playing = false;
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  private async playNext(): Promise<void> {
    if (this.playQueue.length === 0) {
      this.playing = false;
      this.options.onLipSync?.(0);
      console.log('[AudioPlayer] 播放队列为空，停止');
      return;
    }

    this.playing = true;
    const item = this.playQueue.shift()!;

    try {
      console.log(`[AudioPlayer] playBlob: size=${item.blob.size} text="${item.text.slice(0, 30)}"`);
      await this.playBlob(item.blob, item.text);
    } catch (e) {
      console.error('[AudioPlayer] play failed:', e);
    }

    this.playNext();
  }

  private playBlob(blob: Blob, text: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      this.currentAudio = audio;

      audio.oncanplaythrough = () => {
        console.log(`[AudioPlayer] canplaythrough, duration=${audio.duration}`);
      };

      audio.onplay = () => {
        console.log('[AudioPlayer] ▶ playing');
        this.options.onPlayStart?.(text);
        this.startLipSync(audio);
      };

      audio.onended = () => {
        console.log('[AudioPlayer] ■ ended');
        this.stopLipSync();
        this.options.onPlayEnd?.(text);
        URL.revokeObjectURL(url);
        this.currentAudio = null;
        resolve();
      };

      audio.onerror = () => {
        const errMsg = audio.error ? `code=${audio.error.code} msg=${audio.error.message}` : 'unknown';
        console.error(`[AudioPlayer] audio error: ${errMsg}`);
        this.stopLipSync();
        URL.revokeObjectURL(url);
        this.currentAudio = null;
        reject(new Error(`play error: ${errMsg}`));
      };

      const playPromise = audio.play();
      if (playPromise) {
        playPromise.catch((e) => {
          console.error('[AudioPlayer] audio.play() rejected:', e);
          reject(e);
        });
      }
    });
  }

  private startLipSync(audio: HTMLAudioElement): void {
    this.stopLipSync();
    try {
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume();
      }

      if (this.sourceNode) {
        try { this.sourceNode.disconnect(); } catch (_) {}
      }

      this.sourceNode = this.audioContext.createMediaElementSource(audio);

      if (!this.analyser) {
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
      }
      this.sourceNode.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);

      const loop = () => {
        if (!this.analyser) return;
        const data = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        const avg = sum / data.length / 255;
        this.options.onLipSync?.(Math.min(1, avg * 2.5));
        this.lipSyncTimer = requestAnimationFrame(loop);
      };
      this.lipSyncTimer = requestAnimationFrame(loop);
    } catch (e) {
      console.warn('[AudioPlayer] lip sync init failed:', e);
    }
  }

  private stopLipSync(): void {
    if (this.lipSyncTimer !== null) {
      cancelAnimationFrame(this.lipSyncTimer);
      this.lipSyncTimer = null;
    }
    this.options.onLipSync?.(0);
  }
}
