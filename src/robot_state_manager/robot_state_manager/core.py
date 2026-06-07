#!/usr/bin/env python3
"""RobotStateManager — FMS task(IF-03) 기반 상태 머신 (robot2/robot4 공용 본체).

설계 원칙(요구사항 그대로):
  - 자율 판단 없음. 모든 행동은 FMS가 내려준 task(IF-03)에서만 비롯된다.
    "다음에 뭘 할지"는 절대 스스로 정하지 않는다 — mission 판단(누가 언제
    핸드오버하는지 등)은 FMS의 mission_manager 몫이다(절대 규칙 4).
  - state(및 IF-02 보고)는 오직 아래 입력들을 '취합'해서만 바뀐다 — 절대
    스스로 다음 행동을 정하지 않는다:
      ① FMS가 보낸 task(IF-03)        → 무엇을 해야 하는가 (state/task_status 결정)
      ② Nav2 주행 결과(성공/실패)      → 그 일이 어떻게 됐는가 (state/task_status 결정)
      ③ map→base_link TF(localization) → 지금 어디에 있는가 (pose만 갱신, 주행 여부 무관)
    ①·②를 합쳐 (state, task_status)를, ③으로 pose를 계산해 IF-02로 즉시 보고한다.
  - 유일한 예외: PATROL(절대 규칙 8 — FMS는 PATROL을 모르고 명령하지도 않는다).
    task가 없을 때만 로봇이 알아서 config['patrol_waypoints']를 순환 주행한다.
    task가 들어오면 즉시 멈추고, RETURN_TO_BASE로 task가 완전히 끝나면 다시 돈다.
  - 별도 브리지 노드 없이 이 노드가 'FMS와 직접 MQTT로 대화하는 로봇'
    역할을 겸한다(mqtt_link.FmsLink). ROS2 쪽은 Nav2 주행 실행·위치 추적에만 쓴다.

직접 실행하지 말고 robot2_state_manager / robot4_state_manager를 사용하세요.
"""
from __future__ import annotations

import logging
import os
import threading

from rclpy.node import Node

from . import contract
from .contract import (
    ROBOT_PATROL, ROBOT_INTERACTING, ROBOT_ERROR,
    TASK_PROGRESS_STATE, TASK_DONE_STATE, IDLE_LIKE, ESCORT_TASK_TYPES,
    ACK_ACCEPT, ACK_REJECT, TS_ACCEPTED, TS_RUNNING, TS_SUCCEEDED, TS_FAILED,
    TASK_RETURN_TO_BASE,
)
from .docking import DockController
from .localization import Localizer
from .mqtt_link import FmsLink
from .navigator import Nav2Readiness, Navigator


logger = logging.getLogger('robot_sm.core')

_STATUS_PERIOD_SEC = 0.5    # IF-02 주기 보고 = 2Hz (계약 §6 "1~2Hz" 충족)
_UI_POSE_PERIOD_SEC = 1.0   # UI 좌표 보고 주기 (FMS와 무관, 별도 채널)
_POSE_PERIOD_SEC = 0.2      # map→base_link TF 폴링 주기 — 주행 여부와 무관하게 항상 갱신
_PATROL_RETRY_PERIOD_SEC = 2.0  # 자율 PATROL 시작/재개 점검 주기(액션 서버 미준비 시 재시도 포함)


class RobotStateManager(Node):
    def __init__(self, robot_id: str, config: dict) -> None:
        namespace = config['namespace']
        # tf2_ros(Buffer/TransformListener)는 절대경로 /tf, /tf_static을 구독하도록
        # 고정돼 있다. 그런데 이 로봇의 실제 TF는 /robot2/tf, /robot2/tf_static처럼
        # 네임스페이스 하위에 발행된다(`ros2 topic list`로 확인) — 리매핑 없이는
        # 빈 전역 /tf만 보게 되어 lookup_transform이 항상 실패하고 pose가 (0,0)에
        # 고정된다. 노드 단위 리매핑으로 실제 발행 토픽을 보게 한다.
        tf_remap_args = [
            '--ros-args',
            '--remap', f'/tf:={namespace}/tf',
            '--remap', f'/tf_static:={namespace}/tf_static',
        ]
        super().__init__(f'robot_state_manager_{robot_id}', cli_args=tf_remap_args)
        self._robot_id = robot_id
        self._namespace = namespace
        self._ui_pose_topic = config.get('ui_pose_topic', f'ui/{robot_id}/pose')
        self._battery = config.get('initial_battery')  # 보고용 자리값 — 실배터리 연동은 범위 밖(아래 설명 참고)

        # ── 상태 — FMS 계약 값만 사용. MQTT 스레드 / Nav2 콜백이 함께 건드리므로 락 보호 ──
        self._lock = threading.Lock()
        self._state        = ROBOT_PATROL   # task 없을 때 기본 동작 (계약 §6.1: "순찰은 task 아님")
        self._task_id      = None
        self._task_type    = None
        self._mission_id   = None
        self._task_status  = None
        self._error_code   = None
        self._pose         = {'x': 0.0, 'y': 0.0, 'theta': 0.0}

        # ── 자율 PATROL — task 없을 때 로봇이 알아서 도는 유일한 예외 동작
        # (절대 규칙 8: FMS는 PATROL을 모르고 명령하지도 않는다 — 좌표는
        # ROBOT{2,4}_CONFIG['patrol_waypoints']에서만 온다). 비어 있으면 그냥 대기.
        self._patrol_waypoints = config.get('patrol_waypoints') or []
        self._patrol_index = 0
        self._patrolling   = False   # True인 동안만 _on_patrol_result가 다음 목표로 이어감

        # ── 도킹 — 기동 시 도크에 있으면 PATROL보다 undock이 먼저(절대 규칙 8과
        # 같은 결: FMS는 도킹 여부를 모르고 명령하지도 않는다 — 전적으로 로봇 쪽 판단).
        # _maybe_start_patrol 점검에서 "도킹 중이면 undock부터" 식으로 함께 처리한다.
        self._undocking = False   # undock 결과를 기다리는 동안 재요청 방지
        self._dock = DockController(self, self._namespace, on_undock_result=self._on_undock_result)

        # ── 주행 실행기 (Nav2) ───────────────────────────────────────
        # FMS task용과 자율 PATROL용을 분리한다 — 결과 콜백에서 "이게 task 결과인지
        # patrol 결과인지" 뒤섞이는 걸 원천 차단(서버가 새 목표를 받으면 이전 목표를
        # 선점하므로, task가 들어오면 patrol 목표는 자동으로 종료 콜백을 받는다).
        # bt_navigator/amcl 준비 여부 추적 — task용·patrol용 Navigator가 같은
        # namespace를 보므로 get_state 클라이언트·amcl_pose 구독을 하나로 공유한다
        # (waitUntilNav2Active와 달리 멈춰서 기다리지 않고 send_goal마다 확인만 한다).
        self._nav_ready = Nav2Readiness(self, self._namespace)
        self._nav = Navigator(self, self._namespace, on_result=self._on_nav_result,
                              ready=self._nav_ready)
        self._patrol_nav = Navigator(self, self._namespace, on_result=self._on_patrol_result,
                                     ready=self._nav_ready)

        # ── 위치 추적 — map→base_link TF 폴링(주행 중이 아니어도 항상 최신 pose 유지) ──
        self._localizer = Localizer(self,
                                    map_frame=config.get('map_frame', 'map'),
                                    base_frame=config.get('base_frame', 'base_link'))

        # ── FMS 연결 — 이 노드가 '로봇+브리지'를 겸해 IF-02/03/ack를 직접 주고받음 ──
        # ROBOT{2,4}_CONFIG의 mqtt_host/port는 실제 FMS PC 주소(운영값)다.
        # 로컬 mosquitto 등으로 단독 점검할 땐 코드/설정을 건드리지 않고
        # 환경변수로만 잠시 덮어쓸 수 있게 한다(예: ROBOT_SM_MQTT_HOST=127.0.0.1).
        mqtt_host = os.environ.get('ROBOT_SM_MQTT_HOST', config['mqtt_host'])
        mqtt_port = int(os.environ.get('ROBOT_SM_MQTT_PORT', config['mqtt_port']))
        self._fms = FmsLink(robot_id, mqtt_host, mqtt_port,
                            on_task=self._on_task,
                            on_test_cmd=self._on_test_cmd,
                            client_id=config.get('mqtt_client_id'))
        self._fms.connect()

        self.create_timer(_POSE_PERIOD_SEC, self._update_pose)
        self.create_timer(_STATUS_PERIOD_SEC, self._publish_status)
        self.create_timer(_UI_POSE_PERIOD_SEC, self._publish_ui_pose)
        self.create_timer(_PATROL_RETRY_PERIOD_SEC, self._maybe_start_patrol)
        self.get_logger().info(f'[{robot_id}] 준비 완료 — FMS task(IF-03) 대기 중')

    # ════════════════════════════════════════════════════════════════
    # ① 입력: FMS task(IF-03) 수신 — state가 바뀌는 유일한 '결정' 지점
    # ════════════════════════════════════════════════════════════════
    def _on_task(self, task: dict) -> None:
        """paho 네트워크 스레드에서 호출된다."""
        task_id    = task.get('task_id')
        task_type  = task.get('task_type')
        goal       = task.get('goal') or {}
        mission_id = task.get('mission_id')
        cancel_id  = task.get('cancel_task_id')

        with self._lock:
            result = self._decide_ack_locked(task_type)
            self._fms.publish_task_ack(contract.build_task_ack(task_id, self._robot_id, result))
            self.get_logger().warn(
                f'[TASK] {task_id} {task_type} → {result}  (현재 state={self._state})')
            if result == ACK_REJECT:
                return   # PATROL/IDLE에서 받은 ESCORT 계열 — 유령 에스코트 방지(계약 §6.2)

            if task_type not in TASK_PROGRESS_STATE:
                self.get_logger().error(f'[TASK] 알 수 없는 task_type "{task_type}" — 무시')
                return

            if cancel_id and cancel_id == self._task_id:
                self.get_logger().info(f'[TASK] 진행 중이던 {cancel_id} 취소 후 신규 task 수행')
                self._nav.cancel()

            self._patrolling = False  # FMS task 시작 — 자율 PATROL 중단(끝나면 타이머가 재개)

            self._task_id     = task_id
            self._task_type   = task_type
            self._mission_id  = mission_id
            self._task_status = TS_ACCEPTED
            self._set_state_locked(TASK_PROGRESS_STATE[task_type])
            self._task_status = TS_RUNNING
            self._publish_status_locked()   # 전이 즉시 보고(계약 §6: 변화 시 즉시)

        # Nav2 호출은 락 밖에서(액션 콜백이 다시 락을 잡으므로 보유 중 호출 금지)
        self._patrol_nav.cancel()  # 순찰 중이던 목표 선점 취소 — task 주행에 집중
        pose = goal.get('pose') or {}
        if not self._nav.send_goal(pose.get('x', 0.0), pose.get('y', 0.0), pose.get('theta', 0.0)):
            with self._lock:
                self._fail_current_task_locked('NAV_SERVER_NOT_READY')

    def _decide_ack_locked(self, task_type: str) -> str:
        """거절 규칙(계약 §6.2): "지금 임무 없이 PATROL/IDLE인가"가 유일한 기준.

        INTERACTING/RESERVED/HANDOVER_READY/WAITING_HANDOVER/ESCORTING 등
        '임무 중' 상태에서는 ESCORT 계열도 항상 수락한다(특히 next_robot이
        HANDOVER_READY 상태에서 ESCORT_TO_FINAL을 받는 정상 흐름을 막지 않도록).
        """
        if task_type in ESCORT_TASK_TYPES and self._state in IDLE_LIKE:
            return ACK_REJECT
        return ACK_ACCEPT

    # ════════════════════════════════════════════════════════════════
    # 테스트 전용 제어 채널(계약 외, mock_robot.py와 동일 — mock/{robot_id}/cmd)
    # ════════════════════════════════════════════════════════════════
    def _on_test_cmd(self, payload: dict) -> None:
        """실제로는 키오스크/버튼 등 로봇 자신의 판단으로 일어나
        PATROL ⇄ INTERACTING 전이(고객 호출/응대 종료)를 테스트에서 흉내 낸다.
        FMS는 이 전이를 모르고 명령하지도 않으므로(절대 규칙 8과 같은 결),
        임무 중(task_id 있음)에는 무시한다 — paho 네트워크 스레드에서 호출됨."""
        cmd = payload.get('cmd')
        with self._lock:
            if self._task_id is not None:
                return
            if cmd == 'call':
                self._set_state_locked(ROBOT_INTERACTING)
            elif cmd == 'idle':
                self._set_state_locked(ROBOT_PATROL)

    # ════════════════════════════════════════════════════════════════
    # ② 입력: 위치 — map→base_link TF (주행 여부와 무관하게 항상 갱신)
    # ════════════════════════════════════════════════════════════════
    def _update_pose(self) -> None:
        """주기 타이머 콜백 — TF가 아직 없으면(기동 직후 등) 이전 값 유지."""
        pose = self._localizer.current_pose()
        if pose is None:
            return
        with self._lock:
            self._pose = pose

    # ════════════════════════════════════════════════════════════════
    # ③ 입력: Nav2 주행 결과 — task_status/state 계산의 마지막 조각
    # ════════════════════════════════════════════════════════════════

    def _on_nav_result(self, success: bool) -> None:
        with self._lock:
            if self._task_id is None:
                return  # 이미 취소·종료된 task의 뒤늦은 콜백 — 무시

            if success:
                self._task_status = TS_SUCCEEDED
                done_state = TASK_DONE_STATE[self._task_type]
                self.get_logger().warn(
                    f'[TASK] {self._task_id} {self._task_type} 완료 → {done_state}')
                self._set_state_locked(done_state)
                if self._task_type == TASK_RETURN_TO_BASE:
                    # 계약상 RETURN_TO_BASE는 'task 완전 종료' — 보고 필드 초기화
                    self._task_id = self._task_type = self._mission_id = None
                    self._task_status = None
            else:
                self._fail_current_task_locked('NAV_FAILED')

            self._publish_status_locked()  # 전이/완료 즉시 보고

    def _fail_current_task_locked(self, error_code: str) -> None:
        self._task_status = TS_FAILED
        self._error_code = error_code
        self._set_state_locked(ROBOT_ERROR)
        self.get_logger().error(f'[TASK] {self._task_id} 실패({error_code}) → ERROR')

    # ════════════════════════════════════════════════════════════════
    # ④ 자율 PATROL — task 없을 때 로봇이 알아서 도는 유일한 예외 동작
    #    (절대 규칙 8: FMS는 모르고 명령하지도 않는다 — 좌표는 config에서만 옴)
    # ════════════════════════════════════════════════════════════════
    def _maybe_start_patrol(self) -> None:
        """주기 점검 — PATROL ∧ task 없음 ∧ 아직 순찰 중 아니면 다음 목표로 출발.

        기동 직후 액션 서버 미준비로 못 떠났거나, task를 마치고 PATROL로
        돌아온 경우를 같은 경로로 처리한다(별도 이벤트 훅 없이 이 타이머가
        다 흡수 — 자율 동작이라 실패해도 FMS에 보고할 대상이 없으므로
        그냥 다음 주기에 다시 시도한다).

        도킹 중이면 순찰보다 undock이 먼저다 — 도크에 얹힌 채로는 순찰을
        시작해 봐야 제자리에서 헛돌 뿐이므로, 같은 점검에서 "도킹 중 ⇒ undock,
        아니면 ⇒ 순찰"로 함께 가른다(둘 다 '로봇이 알아서 정하는' 자율 동작이라
        FMS 보고 대상이 없다는 점에서 PATROL과 결이 같다).
        """
        if not self._patrol_waypoints:
            return
        with self._lock:
            if self._patrolling or self._state != ROBOT_PATROL or self._task_id is not None:
                return
            docked = self._dock.is_docked
            if docked is None:
                return   # dock_status 아직 수신 전 — 섣불리 판단하지 않고 다음 주기에 재확인
            start_undock = docked and not self._undocking
            if start_undock:
                self._undocking = True
            wp = self._patrol_waypoints[self._patrol_index]

        if docked:
            if start_undock:
                self.get_logger().warn('[DOCK] 도킹 상태로 기동 — undock 먼저 수행 후 순찰 시작')
                if not self._dock.undock():
                    with self._lock:
                        self._undocking = False  # 서버 미준비 — 다음 주기에 재시도
            return   # undock 끝나면 dock_status가 갱신되어 다음 주기에 자연히 순찰로 이어짐

        if self._patrol_nav.send_goal(wp['x'], wp['y'], wp.get('theta', 0.0)):
            with self._lock:
                self._patrolling = True

    def _on_undock_result(self, success: bool) -> None:
        with self._lock:
            self._undocking = False
        if success:
            self.get_logger().warn('[DOCK] undock 완료 — 순찰로 진행')
        else:
            self.get_logger().error('[DOCK] undock 실패 — 다음 주기에 재시도')

    def _on_patrol_result(self, success: bool) -> None:
        """순찰 목표 종료 콜백 — 성공/실패 무관하게 다음 waypoint로 순환한다.

        task가 들어와 _patrolling=False로 내려간 뒤 도착하는 선점 취소의
        뒤늦은 콜백은 여기서 조용히 무시된다(다음 목표를 잇지 않음).
        """
        with self._lock:
            if not self._patrolling:
                return
            self._patrol_index = (self._patrol_index + 1) % len(self._patrol_waypoints)
            wp = self._patrol_waypoints[self._patrol_index]
        if not self._patrol_nav.send_goal(wp['x'], wp['y'], wp.get('theta', 0.0)):
            with self._lock:
                self._patrolling = False  # 재시도는 _maybe_start_patrol 주기 타이머가

    # ════════════════════════════════════════════════════════════════
    # 상태 전이 / IF-02(FMS) · UI 보고
    # ════════════════════════════════════════════════════════════════
    def _set_state_locked(self, new_state: str) -> None:
        if self._state == new_state:
            return
        self.get_logger().warn(f'[STATE] {self._state} → {new_state}')
        self._state = new_state

    def _publish_status(self) -> None:
        """주기 보고 타이머 콜백 (0.5s = 2Hz)."""
        with self._lock:
            self._publish_status_locked()

    def _publish_status_locked(self) -> None:
        msg = contract.build_if02(
            robot_id=self._robot_id,
            state=self._state,
            pose=dict(self._pose),
            battery=self._battery,
            current_task_id=self._task_id,
            task_status=self._task_status,
            error_code=self._error_code,
        )
        self._fms.publish_status(msg)

    def _publish_ui_pose(self) -> None:
        """UI에는 FMS 계약과 무관하게 x, y, z 좌표만 별도 채널로 알린다."""
        with self._lock:
            pose = dict(self._pose)
        payload = {'robot_id': self._robot_id, 'x': pose['x'], 'y': pose['y'], 'z': 0.0}
        self._fms.publish_ui_pose(self._ui_pose_topic, payload)

    def destroy_node(self) -> bool:
        self._fms.stop()
        return super().destroy_node()
