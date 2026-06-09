/**
 * ros_bridge — a tiny, dependency-free client speaking the rosbridge v2 wire
 * protocol over a WebSocket. This is the link between the kiosk (browser) and
 * the laptop wired to the Turtlebot4, which runs `rosbridge_websocket`
 * (rosbridge_suite, default port 9090).
 *
 * Every frame is JSON, exactly the shape ROS expects, e.g. a publish:
 *
 *   { "op": "publish", "topic": "/information", "msg": { ...IF-01... } }
 *
 * We talk the protocol directly (no roslibjs) so "통신은 JSON" stays literally
 * true and the bundle stays small. The client is resilient: it auto-reconnects
 * with backoff, queues outbound frames while offline (bounded), and re-advertises
 * / re-subscribes after a reconnect so a dropped link self-heals.
 */
const TAG = '[ros-bridge]';

/** rosbridge `publish` frame — the wire envelope around a ROS message. */
export interface RosPublishEnvelope<T = unknown> {
  op: 'publish';
  topic: string;
  msg: T;
}

/** Wrap a ROS message in the rosbridge publish envelope (no transport). */
export function rosPublish<T>(topic: string, msg: T): RosPublishEnvelope<T> {
  return { op: 'publish', topic, msg };
}

export interface RosBridgeStatus {
  connected: boolean;
  url: string;
  lastError?: string;
}

export interface RosBridgeOptions {
  /** rosbridge_websocket URL, e.g. ws://192.168.0.42:9090 (the TB4 laptop). */
  url: string;
  /** Reconnect backoff bounds (ms). */
  minReconnectMs?: number;
  maxReconnectMs?: number;
  /** Max outbound frames buffered while disconnected (oldest dropped past this). */
  maxQueue?: number;
}

type Frame = Record<string, unknown>;
type MsgHandler = (msg: unknown) => void;

export class RosBridgeClient {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private readonly minReconnect: number;
  private readonly maxReconnect: number;
  private readonly maxQueue: number;
  private reconnectMs: number;
  private reconnectTimer: number | null = null;
  private closed = false;

  /** Frames buffered while the socket is down. */
  private queue: string[] = [];
  /** topic → ROS type, replayed as `advertise` on (re)connect. */
  private readonly advertised = new Map<string, string>();
  /** topic → handler, replayed as `subscribe` on (re)connect. */
  private readonly subscriptions = new Map<string, MsgHandler>();

  private status: RosBridgeStatus;

  constructor(opts: RosBridgeOptions) {
    this.url = opts.url;
    this.minReconnect = opts.minReconnectMs ?? 1_000;
    this.maxReconnect = opts.maxReconnectMs ?? 15_000;
    this.maxQueue = opts.maxQueue ?? 100;
    this.reconnectMs = this.minReconnect;
    this.status = { connected: false, url: this.url };
  }

  getStatus(): RosBridgeStatus {
    return this.status;
  }

  /** Open the socket (idempotent). Safe to call before publishing. */
  connect(): void {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    this.closed = false;

    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url);
    } catch (err) {
      this.status = { connected: false, url: this.url, lastError: String(err) };
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.status = { connected: true, url: this.url };
      this.reconnectMs = this.minReconnect; // reset backoff on success
      console.info(`${TAG} connected → ${this.url}`);
      // Re-establish advertise/subscribe state, then drain queued frames.
      for (const [topic, type] of this.advertised) {
        this.send({ op: 'advertise', topic, type });
      }
      for (const topic of this.subscriptions.keys()) {
        this.send({ op: 'subscribe', topic });
      }
      this.flush();
    };

    ws.onmessage = (ev) => this.handleMessage(ev.data);

    ws.onerror = () => {
      this.status = { ...this.status, connected: false, lastError: 'socket error' };
      // `onclose` fires next and owns reconnect scheduling.
    };

    ws.onclose = () => {
      this.status = { ...this.status, connected: false };
      this.ws = null;
      if (!this.closed) this.scheduleReconnect();
    };
  }

  /** Stop for good — no further reconnects. */
  disconnect(): void {
    this.closed = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.status = { connected: false, url: this.url };
    console.info(`${TAG} disconnected`);
  }

  /**
   * Declare a topic + ROS message type. Required by rosbridge to create a
   * publisher when the type isn't already known on the ROS graph. Remembered and
   * replayed on every reconnect.
   */
  advertise(topic: string, type: string): void {
    this.advertised.set(topic, type);
    this.send({ op: 'advertise', topic, type });
  }

  /** Publish a ROS message: `{op:'publish', topic, msg}`. Queued if offline. */
  publish(topic: string, msg: unknown): void {
    this.send({ op: 'publish', topic, msg });
  }

  /** Subscribe to a topic; `handler` gets each incoming `msg`. */
  subscribe(topic: string, handler: MsgHandler): void {
    this.subscriptions.set(topic, handler);
    this.send({ op: 'subscribe', topic });
  }

  /** Stop receiving a topic (best-effort). */
  unsubscribe(topic: string): void {
    if (this.subscriptions.delete(topic)) {
      this.send({ op: 'unsubscribe', topic });
    }
  }

  // ---- internals ----------------------------------------------------------

  private send(frame: Frame): void {
    const text = JSON.stringify(frame);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(text);
      return;
    }
    // Offline: buffer (drop oldest past the cap) and make sure we're connecting.
    this.queue.push(text);
    if (this.queue.length > this.maxQueue) this.queue.shift();
    this.connect();
  }

  private flush(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    const pending = this.queue;
    this.queue = [];
    for (const text of pending) this.ws.send(text);
  }

  private handleMessage(data: unknown): void {
    if (typeof data !== 'string') return;
    let frame: { op?: string; topic?: string; msg?: unknown };
    try {
      frame = JSON.parse(data);
    } catch {
      return;
    }
    if (frame.op === 'publish' && typeof frame.topic === 'string') {
      this.subscriptions.get(frame.topic)?.(frame.msg);
    }
  }

  private scheduleReconnect(): void {
    if (this.closed || this.reconnectTimer !== null) return;
    const delay = this.reconnectMs;
    console.warn(`${TAG} link down; retrying in ${delay}ms`);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectMs = Math.min(this.reconnectMs * 2, this.maxReconnect);
      this.connect();
    }, delay);
  }
}
