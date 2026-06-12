import type { MockRobotLink } from '../MockRobotLink';
import type { RobotPoseHandler, RobotPoseService } from './RobotPoseService';

const TAG = '[MockRobotPose]';

/**
 * Offline stand-in (no robot / no rosbridge).
 *
 * - link 없음(기본): 스스로는 아무것도 보내지 않음 — 현위치는 RobotPoseProvider의 window
 *   훅(`window.alfredRobotPose({x,y})`)으로 수동 주입 가능.
 * - link 있음(VITE_MOCK_ROBOT): 가짜 로봇이 INTERACTING/ESCORT 때 emit하는 pose(m)를
 *   그대로 흘려보낸다 → rosbridge 없이 현위치 점이 맵에서 움직이는 데모.
 */
export class MockRobotPoseService implements RobotPoseService {
  constructor(private readonly link?: MockRobotLink) {}

  onPose(handler: RobotPoseHandler): () => void {
    if (!this.link) return () => {};
    return this.link.onPose((pose) => {
      console.debug(`${TAG} (${pose.x.toFixed(2)}, ${pose.y.toFixed(2)}) ← (mock)`);
      handler(pose);
    });
  }
}
