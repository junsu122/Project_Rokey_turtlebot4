import type { RosConnectionStatus, RosGoal, RosService } from './RosService';

const TAG = '[MockROS]';

/**
 * Stand-in for the real ROS bridge. Logs every command so the UI flow is fully
 * observable without a robot/server attached. Replace with a roslibjs-backed
 * implementation that fulfills the same RosService contract.
 */
export class MockRosService implements RosService {
  private status: RosConnectionStatus = { connected: false };

  async connect(): Promise<void> {
    this.status = { connected: true, url: 'mock://rosbridge' };
    console.info(`${TAG} connected (simulated)`);
  }

  disconnect(): void {
    this.status = { connected: false };
    console.info(`${TAG} disconnected`);
  }

  getStatus(): RosConnectionStatus {
    return this.status;
  }

  async publishGoal(goal: RosGoal): Promise<void> {
    console.info(`${TAG} publishGoal →`, goal);
  }

  async cancelGoal(): Promise<void> {
    console.info(`${TAG} cancelGoal`);
  }

  async requestHandoff(toFloorId: string, goal: RosGoal): Promise<void> {
    console.info(`${TAG} requestHandoff → floor ${toFloorId}`, goal);
  }
}
