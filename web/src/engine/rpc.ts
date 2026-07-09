/**
 * Typed RPC client for the engine worker (S2, issue #42).
 *
 * Design contract (docs/sprint-2/qrep-web-design-doc.md): request id, method,
 * JSON payload; ONE in-flight call with a FIFO queue and busy states; the
 * worker is disposable - every bridge call is stateless, so terminate +
 * re-boot is always safe (restart() rejects outstanding calls with kind
 * "worker" and boots a fresh worker).
 *
 * The worker protocol:
 *   main -> worker: {type:"call", id, method, args}
 *   worker -> main: {type:"boot-progress", step}
 *                   {type:"boot-done"}
 *                   {type:"boot-failed", message}
 *                   {type:"result", id, envelope}
 * where envelope is the bridge's typed envelope {ok, result | error}.
 */

export type ErrorKind =
  | "schema"
  | "validation"
  | "value"
  | "internal"
  | "not_implemented"
  | "worker";

export class EngineError extends Error {
  readonly kind: ErrorKind;

  constructor(kind: ErrorKind, message: string) {
    super(message);
    this.name = "EngineError";
    this.kind = kind;
  }
}

export type EngineStatus =
  | { phase: "booting"; step: string }
  | { phase: "ready" }
  | { phase: "busy"; method: string; queued: number }
  | { phase: "failed"; message: string };

/** Vision wheel lifecycle (S6): lazy, prefetchable, retryable. */
export type VisionState = "cold" | "loading" | "ready" | "failed";

export interface WorkerLike {
  postMessage(message: unknown): void;
  terminate(): void;
  onmessage: ((event: MessageEvent) => void) | null;
}

interface Envelope {
  ok: boolean;
  result?: unknown;
  error?: { kind: ErrorKind; message: string };
}

interface QueuedCall {
  id: number;
  method: string;
  args: unknown[];
  resolve: (value: unknown) => void;
  reject: (error: EngineError) => void;
}

export class EngineClient {
  private worker: WorkerLike | null = null;
  private nextId = 1;
  private booted = false;
  private queue: QueuedCall[] = [];
  private inFlight: QueuedCall | null = null;
  private status: EngineStatus = { phase: "booting", step: "Starting the engine" };
  private listeners = new Set<(status: EngineStatus) => void>();
  private vision: VisionState = "cold";
  private visionListeners = new Set<(state: VisionState) => void>();
  private readonly createWorker: () => WorkerLike;

  constructor(createWorker: () => WorkerLike) {
    this.createWorker = createWorker;
  }

  onVision(listener: (state: VisionState) => void): () => void {
    this.visionListeners.add(listener);
    listener(this.vision);
    return () => this.visionListeners.delete(listener);
  }

  getVision(): VisionState {
    return this.vision;
  }

  /** Ask the worker to load the vision wheel now (idle prefetch / retry). */
  prefetchVision(): void {
    this.worker?.postMessage({ type: "load-vision" });
  }

  private setVision(state: VisionState): void {
    this.vision = state;
    for (const listener of this.visionListeners) listener(state);
  }

  start(): void {
    this.booted = false;
    this.worker = this.createWorker();
    this.worker.onmessage = (event: MessageEvent) => this.handleMessage(event.data);
    this.setStatus({ phase: "booting", step: "Starting the engine" });
  }

  restart(): void {
    const outstanding = [...(this.inFlight ? [this.inFlight] : []), ...this.queue];
    this.inFlight = null;
    this.queue = [];
    this.worker?.terminate();
    for (const call of outstanding) {
      call.reject(new EngineError("worker", "the engine was restarted"));
    }
    this.setVision("cold");
    this.start();
  }

  onStatus(listener: (status: EngineStatus) => void): () => void {
    this.listeners.add(listener);
    listener(this.status);
    return () => this.listeners.delete(listener);
  }

  getStatus(): EngineStatus {
    return this.status;
  }

  call<T>(method: string, ...args: unknown[]): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.queue.push({
        id: this.nextId++,
        method,
        args,
        resolve: resolve as (value: unknown) => void,
        reject,
      });
      this.pump();
    });
  }

  private handleMessage(message: {
    type: string;
    step?: string;
    message?: string;
    id?: number;
    envelope?: Envelope;
  }): void {
    switch (message.type) {
      case "boot-progress":
        this.setStatus({ phase: "booting", step: message.step ?? "Loading the engine" });
        break;
      case "boot-done":
        this.booted = true;
        this.pump();
        break;
      case "boot-failed":
        this.booted = false;
        this.setStatus({ phase: "failed", message: message.message ?? "engine failed to load" });
        break;
      case "vision-progress":
        this.setVision("loading");
        break;
      case "vision-ready":
        this.setVision("ready");
        break;
      case "vision-failed":
        this.setVision("failed");
        break;
      case "result": {
        if (this.inFlight === null || message.id !== this.inFlight.id) return;
        const call = this.inFlight;
        this.inFlight = null;
        const envelope = message.envelope;
        if (envelope && envelope.ok) {
          call.resolve(envelope.result);
        } else {
          const error = envelope?.error ?? { kind: "internal" as const, message: "no envelope" };
          call.reject(new EngineError(error.kind, error.message));
        }
        this.pump();
        break;
      }
    }
  }

  private pump(): void {
    if (!this.booted) return;
    if (this.inFlight === null && this.queue.length > 0) {
      this.inFlight = this.queue.shift()!;
      this.worker?.postMessage({
        type: "call",
        id: this.inFlight.id,
        method: this.inFlight.method,
        args: this.inFlight.args,
      });
    }
    if (this.inFlight !== null) {
      this.setStatus({
        phase: "busy",
        method: this.inFlight.method,
        queued: this.queue.length,
      });
    } else {
      this.setStatus({ phase: "ready" });
    }
  }

  private setStatus(status: EngineStatus): void {
    this.status = status;
    for (const listener of this.listeners) {
      listener(status);
    }
  }
}
