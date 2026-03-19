/**
 * Live2D Controller
 *
 * 动态加载 pixi-live2d-display/cubism4（仅 Cubism 4）。
 * 如果 Live2D 模型加载失败，其他功能照常运行。
 *
 * 适配后端 ExpressionDeltaPayload: {action?, expression?, intensity?}
 */

export type ExpressionType =
  | 'neutral'
  | 'happy'
  | 'sad'
  | 'angry'
  | 'surprise'
  | 'thinking';

export interface Live2DControllerOptions {
  container: HTMLElement;
  modelPath: string;
  width?: number;
  height?: number;
  backgroundColor?: number;
}

export class Live2DController {
  private app: any = null;
  private model: any = null;
  private container: HTMLElement;
  private modelPath: string;
  private ready: boolean = false;
  private currentExpression: string = 'neutral';
  private _width: number;
  private _height: number;
  private _bgColor: number;

  constructor(options: Live2DControllerOptions) {
    this.container = options.container;
    this.modelPath = options.modelPath;
    this._width = options.width || options.container.clientWidth || 800;
    this._height = options.height || options.container.clientHeight || 600;
    this._bgColor = options.backgroundColor ?? 0x00000000;
  }

  /** 异步加载，不会抛出 */
  async loadModel(): Promise<boolean> {
    try {
      const PIXI = await import('pixi.js');
      (window as any).PIXI = PIXI;

      const { Live2DModel } = await import('pixi-live2d-display/cubism4');

      this.app = new PIXI.Application({
        width: this._width,
        height: this._height,
        backgroundColor: this._bgColor,
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: window.devicePixelRatio || 1,
      });

      this.container.appendChild(this.app.view as unknown as HTMLElement);

      this.model = await Live2DModel.from(this.modelPath, {
        autoInteract: false,
      });

      const scaleX = this.app.screen.width / this.model.width;
      const scaleY = this.app.screen.height / this.model.height;
      const scale = Math.min(scaleX, scaleY) * 0.8;
      this.model.scale.set(scale);
      this.model.anchor.set(0.5, 0.5);
      this.model.x = this.app.screen.width / 2;
      this.model.y = this.app.screen.height / 2;

      this.app.stage.addChild(this.model);

      this.app.stage.interactive = true;
      this.app.stage.hitArea = this.app.screen;
      this.app.stage.on('pointermove', (e: any) => {
        if (this.model) {
          const pos = e.data?.global || e.global;
          if (pos) this.model.focus(pos.x, pos.y);
        }
      });

      this.ready = true;
      console.log('[Live2D] Model loaded successfully');
      console.log('[Live2D] Motion groups:', this.getMotionGroups());
      return true;
    } catch (e) {
      console.error('[Live2D] Failed to load model:', e);
      this.ready = false;
      return false;
    }
  }

  get isReady(): boolean {
    return this.ready;
  }

  getMotionGroups(): string[] {
    if (!this.model?.internalModel) return [];
    const defs = this.model.internalModel.motionManager?.definitions;
    return defs ? Object.keys(defs) : [];
  }

  async playMotion(group: string, index: number = 0, priority: number = 2): Promise<void> {
    if (!this.ready || !this.model) return;
    try {
      await this.model.motion(group, index, priority);
    } catch (e) {
      console.warn(`[Live2D] Motion "${group}" failed:`, e);
    }
  }

  async setExpression(name: string): Promise<void> {
    if (!this.ready || !this.model) return;
    try {
      await this.model.expression(name);
    } catch (e) {
      console.warn(`[Live2D] Expression "${name}" failed:`, e);
    }
  }

  setLipSync(value: number): void {
    if (!this.ready || !this.model?.internalModel) return;
    const coreModel = (this.model.internalModel as any).coreModel;
    if (!coreModel) return;

    try {
      if (typeof coreModel.setParameterValueById === 'function') {
        coreModel.setParameterValueById('ParamMouthOpenY', value);
      }
    } catch { /* ignore */ }
  }

  /**
   * 处理后端 expression_delta 事件
   *
   * 对应 ExpressionDeltaPayload: {action?, expression?, intensity?}
   * - action: 动作名（映射到 motion group）
   * - expression: 表情名（映射到 Live2D expression）
   * - intensity: 强度（0-1，预留字段）
   */
  handleExpressionDelta(payload: { action?: string; expression?: string; intensity?: number }): void {
    const { action, expression, intensity } = payload;

    // 处理表情
    if (expression && expression !== this.currentExpression) {
      this.currentExpression = expression;
      this.setExpression(expression);
    }

    // 处理动作（action 映射到 motion group）
    if (action) {
      this.playMotion(action, 0);
    }
  }

  resize(width: number, height: number): void {
    if (!this.ready || !this.app) return;
    this.app.renderer.resize(width, height);
    if (this.model) {
      this.model.x = width / 2;
      this.model.y = height / 2;
    }
  }

  destroy(): void {
    if (this.app) {
      this.app.destroy(true, { children: true, texture: true, baseTexture: true });
    }
  }
}
