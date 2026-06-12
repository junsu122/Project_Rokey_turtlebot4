#!/usr/bin/env python3
"""robot2 대기 순찰 및 시나리오 목표 실행 노드.

기존 순찰 노드에서 안정적이었던 구조를 유지한다.
하나의 TurtleBot4Navigator가 robot2를 제어하고, 작은 monitor 노드가 별도
스레드에서 정지/재개/목표 메시지를 받는다. 이렇게 해서 robot2의 순찰 주행과
시나리오 주행이 같은 Nav2 action 서버를 두고 충돌하지 않게 한다.
"""

from __future__ import annotations

from threading import Lock, Thread
from time import monotonic, sleep

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Empty, String
from turtlebot4_navigation.turtlebot4_navigator import TaskResult, TurtleBot4Navigator

from alfred_driving.locations import INITIAL_POSE, LOCATIONS, PATROL_ROUTES


ROBOT = 'robot2'
DOCK_STATUS_TIMEOUT_SEC = 5.0
UNDOCK_CONFIRM_TIMEOUT_SEC = 10.0


def namespaced_node(namespace: str, node_name: str) -> str:
    """Nav2 lifecycle 노드 이름을 robot namespace까지 포함한 절대 이름으로 만든다.

    TurtleBot4Navigator.waitUntilNav2Active()는 bt_navigator와 amcl 이름을
    받아서 Nav2 준비 여부를 확인한다. robot2는 namespace를 쓰기 때문에
    `/robot2/bt_navigator`, `/robot2/amcl` 형태로 넘겨야 한다.
    """
    return f'/{namespace.strip("/")}/{node_name}'


def wait_for_dock_status(
    navigator: TurtleBot4Navigator,
    timeout_sec: float = DOCK_STATUS_TIMEOUT_SEC,
):
    """dock_status가 들어올 때까지 잠깐 기다린다.

    robot2가 도킹 상태인지 모른 채 바로 patrol goal을 보내면, 로봇이 도크 위에서
    움직이려 하거나 Nav2 goal만 먼저 들어가는 상황이 생길 수 있다. 그래서
    `navigator.is_docked` 값이 채워질 때까지 spin_once로 dock_status callback을
    처리한다. 다만 dock_status 토픽이 없는 환경에서는 patrol이 아예 시작하지
    못하므로 timeout 이후에는 dock 확인 없이 계속 진행한다.
    """
    deadline = monotonic() + timeout_sec
    while rclpy.ok() and navigator.is_docked is None and monotonic() < deadline:
        rclpy.spin_once(navigator, timeout_sec=0.1)
    return navigator.is_docked


def wait_until_undocked(
    navigator: TurtleBot4Navigator,
    timeout_sec: float = UNDOCK_CONFIRM_TIMEOUT_SEC,
) -> bool:
    """undock 명령 이후 실제로 dock_status가 False가 될 때까지 기다린다.
    """
    deadline = monotonic() + timeout_sec
    while rclpy.ok() and monotonic() < deadline:
        rclpy.spin_once(navigator, timeout_sec=0.1)
        if navigator.is_docked is False:
            navigator.info('Confirmed robot is undocked.')
            return True

    navigator.warn('Undock confirmation timed out. Continuing patrol startup.')
    return False


def ensure_undocked(navigator: TurtleBot4Navigator) -> None:
    """patrol 또는 patrol 재개 전에 robot2가 반드시 도크에서 빠져 있는지 보장한다.

    이 함수는 시작 시 한 번, 그리고 시나리오 종료 후 patrol을 재개하기 전에도
    호출된다. docked 상태이면 undock action을 실행하고, dock_status가 False로
    바뀐 것을 확인한 뒤에만 다음 단계로 넘어간다.
    """
    navigator.info('Waiting for dock_status before patrol.')
    docked = wait_for_dock_status(navigator)
    if docked is None:
        navigator.warn('dock_status not received. Continuing patrol startup without dock check.')
        return
    if not docked:
        navigator.info('Robot is already undocked.')
        return

    navigator.warn('Robot is docked. Undocking before patrol.')
    navigator.undock()
    wait_until_undocked(navigator)


class Robot2Monitor(Node):
    """robot2 제어 명령을 별도 스레드에서 받는 보조 ROS 노드.

    patrol_node의 메인 스레드는 TurtleBot4Navigator로 Nav2 goal을 보내고 결과를
    기다린다. 그동안에도 `/robot2/stop_request`, `/robot2/resume_patrol_request`,
    `/robot2/goal_pose_request`를 놓치지 않기 위해 이 monitor 노드를 별도
    executor thread에서 계속 spin한다.
    """

    def __init__(self, lock: Lock):
        """구독/발행 토픽과 공유 상태 플래그를 초기화한다.

        공유 상태(`stop_requested`, `resume_requested`, `pending_goal`)는 메인
        순찰 루프와 callback 스레드가 함께 접근하므로 `lock`으로 보호한다.
        """
        super().__init__('patrol_monitor', namespace=ROBOT)

        self.lock = lock
        self.stop_requested = False
        self.resume_requested = False
        self.pending_goal = None

        self.create_subscription(Empty, 'stop_request', self.stop_request_callback, 10)
        self.create_subscription(
            Empty, 'resume_patrol_request', self.resume_patrol_callback, 10)
        self.create_subscription(PoseStamped, 'goal_pose_request', self.goal_callback, 10)
        self.status_publisher = self.create_publisher(String, 'nav_status', 10)

    def stop_request_callback(self, _msg: Empty):
        """scenario_manager_node가 보낸 순찰 정지 요청을 기록한다.

        실제 Nav2 cancel은 callback 안에서 바로 하지 않고, 메인 순찰 루프가
        안전한 지점에서 `cancel_and_wait()`로 처리한다.
        """
        with self.lock:
            self.stop_requested = True

    def resume_patrol_callback(self, _msg: Empty):
        """시나리오 종료 후 순찰 재개 요청을 기록한다."""
        with self.lock:
            self.resume_requested = True

    def goal_callback(self, msg: PoseStamped):
        """순찰이 멈춘 동안 실행할 robot2 시나리오 목표를 저장한다."""
        with self.lock:
            self.pending_goal = msg

    def publish_status(self, status: str):
        """robot2의 상태를 `/robot2/nav_status`로 발행한다.

        주요 값:
        - `patrol_stopped`: 순찰 goal 취소가 끝나서 ESCORT 목표를 받을 수 있음
        - `arrived`: 시나리오 goal에 도착함
        """
        msg = String()
        msg.data = status
        self.status_publisher.publish(msg)
        self.get_logger().info(f'Published nav_status={status}')

    def spin_thread(self):
        """monitor 노드를 별도 SingleThreadedExecutor에서 계속 spin한다."""
        executor = SingleThreadedExecutor()
        executor.add_node(self)
        executor.spin()


def cancel_and_wait(navigator: TurtleBot4Navigator):
    """실행 중인 Nav2 목표를 취소하고, Nav2가 종료 결과를 줄 때까지 기다린다.

    stop_request가 들어왔을 때 바로 다음 시나리오 goal을 보내면 이전 patrol goal과
    새 goal이 같은 Nav2 action 서버에서 겹칠 수 있다. 그래서 cancel 요청을 보내고,
    `isTaskComplete()`가 True가 될 때까지 기다린 뒤에만 `patrol_stopped`를
    발행한다.
    """
    if navigator.result_future is None or navigator.goal_handle is None:
        navigator.info('No active goal to cancel.')
        return

    navigator.info('Canceling current task...')
    try:
        cancel_future = navigator.goal_handle.cancel_goal_async()
    except Exception as err:
        navigator.warn(f'Cancel request failed or goal already ended: {err}')
        return

    while rclpy.ok() and not cancel_future.done():
        rclpy.spin_once(navigator, timeout_sec=0.1)

    navigator.info('Cancel accepted. Waiting for task result...')
    while rclpy.ok() and not navigator.isTaskComplete():
        rclpy.spin_once(navigator, timeout_sec=0.1)

    navigator.info(f'Task fully stopped with result={navigator.getResult()}.')


def refresh_goal_stamp(navigator: TurtleBot4Navigator, goal: PoseStamped) -> PoseStamped:
    """Reuse an existing map goal with a fresh stamp before sending it to Nav2."""
    goal.header.stamp = navigator.get_clock().now().to_msg()
    return goal


def run_patrol(navigator: TurtleBot4Navigator, monitor: Robot2Monitor, lock: Lock, goals):
    """robot2 대기 순찰을 수행한다. 정지 요청으로 중단되면 True를 반환한다.

    `PATROL_ROUTES["robot2"]`에서 만든 waypoint 목록을 순서대로 반복한다.
    순찰 중 `stop_request`가 들어오면 현재 goal을 취소하고 True를 반환한다.
    True가 반환되면 main 루프는 `/robot2/nav_status = patrol_stopped`를 발행하고
    시나리오 goal 대기 모드로 넘어간다.
    """
    position_index = 0

    while rclpy.ok():
        with lock:
            stop_requested = monitor.stop_requested

        if stop_requested:
            navigator.info('Stop request received before patrol goal. Stopping patrol.')
            cancel_and_wait(navigator)
            return True

        # 현재 순찰 waypoint를 Nav2 goal로 보낸다.
        goal_name, goal_pose = goals[position_index]
        goal_pose = refresh_goal_stamp(navigator, goal_pose)
        navigator.info(f'Driving to patrol waypoint {goal_name}')

        try:
            accepted = navigator.goToPose(goal_pose)
        except Exception as err:
            navigator.error(f'Failed to send patrol goal: {err}')
            sleep(1.0)
            continue

        if not accepted:
            navigator.error('Nav2 rejected patrol goal.')
            sleep(1.0)
            continue

        navigator.info(f'Patrol goal accepted: {goal_name}')
        interrupted = False

        # goal 수행 중에도 stop_request를 계속 확인해서 즉시 순찰을 중단할 수 있게 한다.
        while rclpy.ok() and not navigator.isTaskComplete():
            with lock:
                interrupted = monitor.stop_requested

            if interrupted:
                navigator.info('Stop request received mid-patrol. Canceling.')
                cancel_and_wait(navigator)
                break

            rclpy.spin_once(navigator, timeout_sec=0.1)

        if interrupted:
            return True

        result = navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            navigator.info(f'Patrol waypoint reached: {goal_name}')
            position_index = (position_index + 1) % len(goals)
        else:
            navigator.warn(f'Patrol goal result={result}. Retrying current waypoint.')

    return False


def run_scenario_goal_executor(
    navigator: TurtleBot4Navigator,
    monitor: Robot2Monitor,
    lock: Lock,
):
    """순찰이 멈춘 동안 /robot2/goal_pose_request 목표를 실행한다.

    INTERACTING 이후 ESCORT 단계에서 scenario_manager_node가 robot2 목표를
    `/robot2/goal_pose_request`로 보낸다. 이 함수는 그 목표를 받아 이동하고,
    도착하면 `/robot2/nav_status = arrived`를 발행한다. 시나리오가 끝나
    `resume_patrol_request`가 들어오면 True를 반환해서 main 루프가 patrol로
    복귀하게 한다.
    """
    navigator.info('Patrol fully stopped. Waiting for scenario goals.')

    while rclpy.ok():
        with lock:
            goal = monitor.pending_goal
            monitor.pending_goal = None
            resume_requested = monitor.resume_requested

        if resume_requested:
            navigator.info('Resume-patrol request received.')
            return True

        # 아직 scenario_manager_node가 보낸 목표가 없으면 대기한다.
        if goal is None:
            sleep(0.1)
            continue

        navigator.info('Received scenario navigation goal.')
        goal = refresh_goal_stamp(navigator, goal)
        try:
            accepted = navigator.goToPose(goal)
        except Exception as err:
            navigator.error(f'Failed to send scenario goal: {err}')
            continue

        if not accepted:
            navigator.error('Nav2 rejected scenario goal.')
            continue

        # 시나리오 goal 수행 중에도 resume 요청이 오면 goal을 취소하고 순찰로 복귀한다.
        while rclpy.ok() and not navigator.isTaskComplete():
            with lock:
                resume_requested = monitor.resume_requested

            if resume_requested:
                navigator.info('Resume requested during scenario goal. Canceling goal.')
                cancel_and_wait(navigator)
                return True

            rclpy.spin_once(navigator, timeout_sec=0.1)

        if navigator.getResult() == TaskResult.SUCCEEDED:
            navigator.info('Scenario goal reached.')
            monitor.publish_status('arrived')
        else:
            navigator.warn(f'Scenario goal result={navigator.getResult()}.')

    return False


def make_patrol_goals(navigator: TurtleBot4Navigator):
    """locations.py의 순찰 waypoint 이름을 실제 PoseStamped goal 목록으로 바꾼다.

    PATROL_ROUTES에는 문자열 이름만 들어 있다. Nav2에 보내려면 LOCATIONS에서
    좌표와 방향을 꺼내 `navigator.getPoseStamped()`로 변환해야 한다.
    반환 형식은 `(waypoint_name, pose)` 목록이며, 로그에 waypoint 이름을 남기기
    위해 이름도 함께 보관한다.
    """
    goals = []
    for name in PATROL_ROUTES[ROBOT]:
        position, direction = LOCATIONS[name]['pose']
        goals.append((name, navigator.getPoseStamped(position, direction)))
    return goals


def main(args=None):
    rclpy.init(args=args)

    lock = Lock()
    monitor = Robot2Monitor(lock)
    navigator = TurtleBot4Navigator(namespace=f'/{ROBOT}')

    thread = Thread(target=monitor.spin_thread, daemon=True)
    thread.start()

    position, direction = INITIAL_POSE[ROBOT]
    navigator.setInitialPose(navigator.getPoseStamped(position, direction))
    navigator.info(f'Set initial pose for {ROBOT}: {position}')

    navigator.info(
        f'Waiting for Nav2 lifecycle nodes: '
        f'{namespaced_node(ROBOT, "amcl")}, {namespaced_node(ROBOT, "bt_navigator")}'
    )
    navigator.waitUntilNav2Active(
        navigator=namespaced_node(ROBOT, 'bt_navigator'),
        localizer=namespaced_node(ROBOT, 'amcl'),
    )
    ensure_undocked(navigator)
    navigator.info('Nav2 active. Starting robot2 standby patrol.')

    patrol_goals = make_patrol_goals(navigator)

    while rclpy.ok():
        # 시작 시뿐 아니라 시나리오 후 순찰 재개 전에도 dock 상태를 다시 확인한다.
        ensure_undocked(navigator)
        stopped_for_scenario = run_patrol(navigator, monitor, lock, patrol_goals)
        if not stopped_for_scenario:
            break

        monitor.publish_status('patrol_stopped')
        should_resume = run_scenario_goal_executor(navigator, monitor, lock)
        if not should_resume:
            break

        with lock:
            monitor.stop_requested = False
            monitor.resume_requested = False
            monitor.pending_goal = None

        navigator.info('Scenario finished. Resuming robot2 standby patrol.')

    monitor.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
