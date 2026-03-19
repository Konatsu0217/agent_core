/**
 * Subtitle Manager - 字幕管理
 * 
 * 负责展示 text_delta 增量文本，
 * 模拟虚拟主播的实时字幕效果。
 * final 事件不更新字幕文本，仅启动自动隐藏。
 */

export interface SubtitleOptions {
  container: HTMLElement;
  /** 字幕自动消失时间（ms），0 = 不自动消失 */
  autoHideDelay?: number;
  /** 最大显示字符数 */
  maxLength?: number;
}

export class SubtitleManager {
  private container: HTMLElement;
  private textEl: HTMLElement;
  private autoHideDelay: number;
  private maxLength: number;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private currentText: string = '';

  constructor(options: SubtitleOptions) {
    this.container = options.container;
    this.autoHideDelay = options.autoHideDelay ?? 5000;
    this.maxLength = options.maxLength ?? 200;

    this.textEl = document.createElement('div');
    this.textEl.className = 'subtitle-text';
    this.container.appendChild(this.textEl);
  }

  /** 增量追加文字（text_delta） */
  appendText(text: string): void {
    this.cancelAutoHide();
    this.currentText += text;

    // 超长截断（保留末尾）
    if (this.currentText.length > this.maxLength) {
      this.currentText = '...' + this.currentText.slice(-this.maxLength);
    }

    this.textEl.textContent = this.currentText;
    this.container.classList.add('visible');
  }

  /** 完成一轮对话（final）— 不替换文本，仅启动自动隐藏 */
  finalize(): void {
    this.container.classList.add('visible');
    this.scheduleAutoHide();
  }

  /** 清空字幕（新一轮对话开始时） */
  clear(): void {
    this.cancelAutoHide();
    this.currentText = '';
    this.textEl.textContent = '';
    this.container.classList.remove('visible');
  }

  private scheduleAutoHide(): void {
    if (this.autoHideDelay <= 0) return;
    this.cancelAutoHide();
    this.hideTimer = setTimeout(() => {
      this.container.classList.remove('visible');
    }, this.autoHideDelay);
  }

  private cancelAutoHide(): void {
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
  }
}
