import type { RosBridgeClient } from '../ros';
import type { FmsService } from './FmsService';
import { toRosPayload, type If01Request } from './if01';

const TAG = '[FMS]';

/**
 * Real FMS request channel over the ros_bridge. Every IF-01 request (ESCORT /
 * CANCEL / INTERACTING) is published to the `/information` topic as a rosbridge
 * frame: `{op:'publish', topic:'/information', msg:<payload>}`. The Turtlebot4
 * laptop's rosbridge_websocket relays it to the consuming ROS node.
 *
 * `msgType` is the topic's ROS message type (advertised on connect so rosbridge
 * can create the publisher). With std_msgs/String the IF-01 object rides as JSON
 * text in `.data`; a custom type carries the structured fields directly
 * (see `toRosPayload`).
 *
 * `RosBridgeClient` owns connect/reconnect/queueing, so a request issued while
 * the link is briefly down is buffered and flushed on reconnect rather than lost.
 */
export class RosBridgeFmsService implements FmsService {
  constructor(
    private readonly bridge: RosBridgeClient,
    private readonly topic: string,
    private readonly msgType: string,
  ) {}

  async sendRequest(request: If01Request): Promise<void> {
    this.bridge.publish(this.topic, toRosPayload(request, this.msgType));
    console.info(`${TAG} IF-01 ${request.request_type} → ${this.topic}`, request);
  }
}
