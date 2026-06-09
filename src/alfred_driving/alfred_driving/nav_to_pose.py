import rclpy
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Directions, TurtleBot4Navigator

# ======================
# 초기 설정 (파일 안에서 직접 정의)
# ======================
INITIAL_POSE_POSITION = [0.01, 0.01]
INITIAL_POSE_DIRECTION = TurtleBot4Directions.NORTH

GOAL_POSES = [
    ([-1.5, 1.1], TurtleBot4Directions.NORTH),
    ([0.0, 1.5], TurtleBot4Directions.NORTH),
    ([-3.2, 1.25], TurtleBot4Directions.NORTH),
    ([-1.3, 2.0], TurtleBot4Directions.NORTH),
    ([-0.25, 2.5], TurtleBot4Directions.NORTH),
    ([-0.25, 3.2], TurtleBot4Directions.NORTH),
    ([-1.3, 2.0], TurtleBot4Directions.NORTH),
    ([-2.1, 3.2], TurtleBot4Directions.NORTH),
]
# ======================

def main():
    rclpy.init()
    navigator = TurtleBot4Navigator()

    navigator.waitUntilNav2Active()
    for i in range(len(GOAL_POSES)) :
        goal_pose = navigator.getPoseStamped(*GOAL_POSES[i])
        navigator.startToPose(goal_pose)
        while not navigator.isTaskComplete():
            rclpy.spin_once(navigator, timeout_sec=0.1)


    navigator.dock()
    rclpy.shutdown()

if __name__ == '__main__':
    main()