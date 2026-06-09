import { rosPublish } from '../ros';
import type { FmsService } from './FmsService';
import { toRosPayload, type If01Request } from './if01';

const TAG = '[MockFMS]';

/**
 * Offline stand-in for the FMS request channel. Logs the EXACT rosbridge frame
 * (`{op:'publish', topic, msg}`) that RosBridgeFmsService would put on the wire
 * — including the std_msgs/String JSON wrapping — so the request flow and the
 * contract are fully observable with no robot / rosbridge attached. Swap for
 * RosBridgeFmsService to go live.
 */
export class MockFmsService implements FmsService {
  constructor(
    private readonly topic = '/information',
    private readonly msgType = 'std_msgs/String',
  ) {}

  async sendRequest(request: If01Request): Promise<void> {
    console.info(
      `${TAG} IF-01 ${request.request_type} → ${this.topic}`,
      rosPublish(this.topic, toRosPayload(request, this.msgType)),
    );
  }
}
