import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { useServices, type RobotPose } from '@/services';

const RobotPoseContext = createContext<RobotPose | null>(null);

/**
 * Holds the robot's latest live pose (IF — /robotN/interacting_pose) so the map
 * can draw a live "현위치" dot. Mounted once at the app root so a pose that
 * arrives BEFORE the user opens the map (e.g. right after INTERACTING) is still
 * captured. Map-only consumers read it via `useRobotPose()`.
 *
 * Manual trigger (no robot) from the console:
 *   window.alfredRobotPose({ x: -3.2, y: 2.1, theta: 0 })
 */
export function RobotPoseProvider({ children }: { children: ReactNode }) {
  const { robotPose } = useServices();
  const [pose, setPose] = useState<RobotPose | null>(null);

  // Real source: ros_bridge robot pose → state.
  useEffect(() => robotPose.onPose(setPose), [robotPose]);

  // Manual test hook on window.
  useEffect(() => {
    const w = window as unknown as {
      alfredRobotPose?: (p: { x: number; y: number; theta?: number }) => void;
    };
    w.alfredRobotPose = (p) => setPose({ x: p.x, y: p.y, theta: p.theta });
    console.info(
      '[robot-pose] test: window.alfredRobotPose({ x: -3.2, y: 2.1, theta: 0 })',
    );
    return () => {
      delete w.alfredRobotPose;
    };
  }, []);

  return (
    <RobotPoseContext.Provider value={pose}>{children}</RobotPoseContext.Provider>
  );
}

/** The robot's latest pose (meters, map frame), or null if none yet. */
export function useRobotPose(): RobotPose | null {
  return useContext(RobotPoseContext);
}
