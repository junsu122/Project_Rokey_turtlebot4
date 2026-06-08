import type { If01Request } from './if01';

/**
 * FMS request channel (IF-01) — the customer-request boundary, separate from the
 * ROS motion channel. The UI publishes a request when a destination is confirmed
 * (ESCORT) or cancelled (CANCEL); the FMS handles assignment and the cross-floor
 * relay. In production this is an MQTT/WebSocket transport (정의서 §9); the UI
 * depends only on this interface — swap MockFmsService for a real one.
 */
export interface FmsService {
  /** Publish an IF-01 request (ESCORT or CANCEL) to the FMS. */
  sendRequest(request: If01Request): Promise<void>;
}
