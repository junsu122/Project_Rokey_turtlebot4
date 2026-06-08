import type { FmsService } from './FmsService';
import type { If01Request } from './if01';

const TAG = '[MockFMS]';

/**
 * Stand-in for the FMS request channel. Logs the IF-01 JSON so the request flow
 * is fully observable without a server attached. Replace with an MQTT/WebSocket-
 * backed implementation that fulfills the same FmsService contract.
 */
export class MockFmsService implements FmsService {
  async sendRequest(request: If01Request): Promise<void> {
    console.info(`${TAG} IF-01 ${request.request_type} →`, request);
  }
}
