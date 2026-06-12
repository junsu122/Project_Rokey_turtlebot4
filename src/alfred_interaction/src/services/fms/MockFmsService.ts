import type { MockRobotLink } from '../MockRobotLink';
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
 *
 * mock-robot 데모(VITE_MOCK_ROBOT)에서는 `link`를 받아, 발행한 IF-01을 가짜 로봇에게
 * 그대로 넘긴다(가짜 로봇이 ui_state로 응답 → 전체 흐름이 rosbridge 없이 돈다).
 */
export class MockFmsService implements FmsService {
  constructor(
    private readonly topic = '/information',
    private readonly msgType = 'std_msgs/String',
    private readonly link?: MockRobotLink,
  ) {}

  async sendRequest(request: If01Request): Promise<void> {
    console.info(
      `${TAG} IF-01 ${request.request_type} → ${this.topic}`,
      rosPublish(this.topic, toRosPayload(request, this.msgType)),
    );
    this.link?.submit(request); // 가짜 로봇 연결 시: 이 요청으로 ui_state 시퀀스를 유발
  }
}
