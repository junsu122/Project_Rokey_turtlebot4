"""Mission Manager — IF-01 수신 → mission 생성·배정 → IF-03 task 발행,
IF-02 task 완료 이벤트로 전이 진행, 핸드오버 승인·3초 지연 산출.

이벤트 구동(절대 규칙 2): 모든 핸들러는 MQTT 콜백에서 호출되어 즉시 리턴한다.
"블로킹 대기"나 "도착까지 기다리는 루프"는 없다 — IF-02가 올 때마다 반응할 뿐.

명령은 task로만(절대 규칙 3). Mission State는 로봇에 보내지 않는다(절대 규칙 4).
콜백은 paho 단일 네트워크 스레드에서 순차 실행되므로 _missions 접근은 직렬화된다.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone

import config
import db
import messages
import poi
import state_machine as sm
from states import (
    MISSION_ASSIGNED, MISSION_CANCELLED, MISSION_COMPLETED, MISSION_EMERGENCY,
    MISSION_ESCORTING_TO_FINAL, MISSION_ESCORTING_TO_HANDOVER,
    MISSION_FAILED, MISSION_HANDOVER_WAITING, MISSION_REQUESTED,
    ROBOT_EMERGENCY, ROBOT_HANDOVER_READY, ROBOT_WAITING_HANDOVER,
    TASK_ESCORT_TO_FINAL, TASK_ESCORT_TO_HANDOVER, TASK_MOVE_TO_STANDBY,
    TASK_RETURN_TO_BASE, TS_FAILED, TS_SUCCEEDED,
    ACK_REJECT,
)


logger = logging.getLogger("fms.mission")


def _gen_id(prefix: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{prefix}_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def _latency_ms(t_arrival: str | None, t_pickup: str | None) -> int | None:
    if not t_arrival or not t_pickup:
        return None
    try:
        a = datetime.fromisoformat(t_arrival)
        p = datetime.fromisoformat(t_pickup)
        return int((p - a).total_seconds() * 1000)
    except ValueError:
        return None


class MissionManager:
    def __init__(self, transport, registry) -> None:
        self.transport = transport
        self.registry = registry
        self._missions: dict[str, dict] = {}        # mission_id -> mission
        self._robot_active: dict[str, str] = {}     # robot_id -> mission_id
        # paho 콜백 스레드 + 타임아웃 감시 스레드가 _missions를 함께 건드리므로 보호.
        self._lock = threading.RLock()
        # 타임아웃으로 ERROR 표기한 로봇(중복 로그 방지). 신선한 status 오면 해제.
        self._timed_out: set[str] = set()

    # ════════════════════════════════════════════════════════════════════
    # IF-01 수신 → mission 생성·배정·초기 task 발행
    # ════════════════════════════════════════════════════════════════════
    def on_request(self, if01: dict) -> None:
        request_type = if01.get("request_type", "ESCORT")
        with self._lock:
            if request_type == "CANCEL":
                self._on_cancel(if01)
                return
            if request_type != "ESCORT":
                logger.info("unsupported request_type: %s", request_type)
                return
            self._create_escort(if01)

    def _create_escort(self, if01: dict) -> None:
        robot_id = if01.get("robot_id")
        dest = if01.get("destination") or {}
        origin = if01.get("origin") or {}
        dest_poi_id = dest.get("poi_id")

        # poi_table에 없으면 버그 → ERROR 로그 후 무시 (가이드 §4.1)
        if poi.get(dest_poi_id) is None:
            logger.error("unknown destination poi_id=%s — request ignored", dest_poi_id)
            return
        if robot_id not in config.ROBOT_IDS:
            logger.error("unknown request robot_id=%s — ignored", robot_id)
            return

        start_robot = robot_id
        next_robot = config.partner_of(robot_id)
        same_floor = dest.get("floor") == origin.get("floor")

        mission_id = _gen_id("MISSION")
        request_id = if01.get("request_id") or _gen_id("REQ")
        now = db.utc_now_iso()

        mission = {
            "mission_id": mission_id,
            "request_id": request_id,
            "state": MISSION_REQUESTED,
            "start_robot": start_robot,
            "next_robot": next_robot,
            "dest_poi": dest_poi_id,
            "same_floor": same_floor,
            "customer": if01.get("customer") or {},
            "flags": {"start_arrived": False, "next_ready": False},
            "t_arrival": None,
            "t_pickup_cmd": None,
            "handover_latency_ms": None,
            "tasks": {},  # task_id -> {robot_id, task_type, done}
            "goals": {
                "final": poi.goal_for(dest_poi_id),
                "handover": poi.goal_for(poi.first_of_type("HANDOVER")) if not same_floor else None,
                "standby": poi.goal_for(poi.first_of_type("STANDBY")) if not same_floor else None,
            },
            "created_at": now,
        }
        self._missions[mission_id] = mission
        self._robot_active[start_robot] = mission_id
        if next_robot and not same_floor:
            self._robot_active[next_robot] = mission_id

        db.execute(
            "INSERT INTO requests(request_id, robot_id, request_type, payload_json, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (request_id, robot_id, "ESCORT", json.dumps(if01, ensure_ascii=False), now),
        )
        db.execute(
            "INSERT INTO missions(mission_id, request_id, state, start_robot, next_robot, "
            "dest_poi, customer_profile, created_at, completed_at, handover_latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mission_id, request_id, MISSION_REQUESTED, start_robot, next_robot,
             dest_poi_id, mission["customer"].get("profile"), now, None, None),
        )
        logger.info("mission %s created: start=%s next=%s dest=%s same_floor=%s",
                    mission_id, start_robot, next_robot, dest_poi_id, same_floor)

        self._assign_and_dispatch(mission)

    def _assign_and_dispatch(self, mission: dict) -> None:
        self._set_state(mission, MISSION_ASSIGNED, "ASSIGN", "robots assigned")

        if mission["same_floor"]:
            # 같은 층 직행 (전이 11): next 없이 start에 ESCORT_TO_FINAL
            self._set_state(mission, MISSION_ESCORTING_TO_FINAL,
                            "DISPATCH_FINAL_DIRECT", "same-floor direct escort")
            self._issue_task(mission, mission["start_robot"],
                             TASK_ESCORT_TO_FINAL, mission["goals"]["final"])
            return

        # 층 다름: next에 대기지점, start에 핸드오버 지점
        self._issue_task(mission, mission["next_robot"],
                         TASK_MOVE_TO_STANDBY, mission["goals"]["standby"])
        self._set_state(mission, MISSION_ESCORTING_TO_HANDOVER,
                        "DISPATCH_HANDOVER", "start dispatched to handover")
        self._issue_task(mission, mission["start_robot"],
                         TASK_ESCORT_TO_HANDOVER, mission["goals"]["handover"])

    # ════════════════════════════════════════════════════════════════════
    # IF-02 수신 → task 완료(SUCCEEDED) 감지로 전이 진행
    # ════════════════════════════════════════════════════════════════════
    def on_robot_status(self, payload: dict) -> None:
        robot_id = payload.get("robot_id")
        with self._lock:
            # 신선한 보고 도착 → 타임아웃 표기 해제
            self._timed_out.discard(robot_id)

            mission_id = self._robot_active.get(robot_id)
            if not mission_id:
                return
            mission = self._missions.get(mission_id)
            if not mission:
                return

            state = payload.get("state")
            task_status = payload.get("task_status")

            # ── 예외 우선 (진행 중 미션에서만) ──────────────────────────
            if mission["state"] in sm.ACTIVE_STATES:
                if state == ROBOT_EMERGENCY:
                    self._terminate(mission, MISSION_EMERGENCY, "EMERGENCY",
                                    f"{robot_id} reported EMERGENCY",
                                    emergency_robot=robot_id)
                    return
                if task_status == TS_FAILED:
                    self._terminate(mission, MISSION_FAILED, "FAIL",
                                    f"{robot_id} task FAILED")
                    return

            # ── 정상: 발행한 task가 SUCCEEDED로 처음 보고될 때만 1회 반응 ──
            task_id = payload.get("current_task_id")
            tinfo = mission["tasks"].get(task_id)
            if not tinfo or task_status != TS_SUCCEEDED or tinfo.get("done"):
                return
            tinfo["done"] = True
            self._on_task_succeeded(mission, robot_id, tinfo["task_type"], payload)

    def _on_task_succeeded(self, mission: dict, robot_id: str,
                           task_type: str, payload: dict) -> None:
        mid = mission["mission_id"]
        self._finish_task_row(payload.get("current_task_id"), TS_SUCCEEDED)

        if task_type == TASK_MOVE_TO_STANDBY:
            mission["flags"]["next_ready"] = True
            logger.info("mission %s: next_robot %s ready (HANDOVER_READY)", mid, robot_id)
            self._maybe_approve_handover(mission)

        elif task_type == TASK_ESCORT_TO_HANDOVER:
            mission["flags"]["start_arrived"] = True
            # t_arrival = 로봇의 도착 보고 시각(IF-02 timestamp) — 3초 측정 기준
            mission["t_arrival"] = payload.get("timestamp")
            if mission["state"] == MISSION_ESCORTING_TO_HANDOVER:
                self._set_state(mission, MISSION_HANDOVER_WAITING,
                                "START_ARRIVED", "start arrived at handover")
            logger.info("mission %s: start_robot %s arrived (t_arrival=%s)",
                        mid, robot_id, mission["t_arrival"])
            self._maybe_approve_handover(mission)

        elif task_type == TASK_ESCORT_TO_FINAL:
            self._complete_mission(mission, robot_id)

        elif task_type == TASK_RETURN_TO_BASE:
            logger.info("mission %s: %s returned to base", mid, robot_id)

    def _maybe_approve_handover(self, mission: dict) -> None:
        # 승인 조건: start 도착 ∧ next 준비 (도착 순서 무관). 정의서 §6
        if mission["state"] != MISSION_HANDOVER_WAITING:
            return
        if not (mission["flags"]["start_arrived"] and mission["flags"]["next_ready"]):
            return

        mission["t_pickup_cmd"] = db.utc_now_iso()
        latency = _latency_ms(mission["t_arrival"], mission["t_pickup_cmd"])
        mission["handover_latency_ms"] = latency
        db.execute("UPDATE missions SET handover_latency_ms=? WHERE mission_id=?",
                   (latency, mission["mission_id"]))

        target = config.HANDOVER_TARGET_MS
        ok = "OK" if (latency is not None and latency <= target) else "OVER"
        self._set_state(mission, MISSION_ESCORTING_TO_FINAL, "HANDOVER_APPROVED",
                        f"handover approved; latency={latency}ms")
        logger.info("mission %s: HANDOVER APPROVED — latency=%sms (target ≤%sms) [%s]",
                    mission["mission_id"], latency, target, ok)

        # next에 ESCORT_TO_FINAL, start에 RETURN_TO_BASE
        self._issue_task(mission, mission["next_robot"],
                         TASK_ESCORT_TO_FINAL, mission["goals"]["final"])
        self._issue_task(mission, mission["start_robot"],
                         TASK_RETURN_TO_BASE, self._base_goal(mission["start_robot"]))

    def _complete_mission(self, mission: dict, robot_id: str) -> None:
        now = db.utc_now_iso()
        self._set_state(mission, MISSION_COMPLETED, "FINAL_ARRIVED",
                        "final destination reached")
        db.execute("UPDATE missions SET completed_at=? WHERE mission_id=?",
                   (now, mission["mission_id"]))
        # 도착 로봇 복귀
        self._issue_task(mission, robot_id, TASK_RETURN_TO_BASE, self._base_goal(robot_id))
        # 로봇 해제 (다음 요청 배정 가능)
        for rid in (mission["start_robot"], mission["next_robot"]):
            if self._robot_active.get(rid) == mission["mission_id"]:
                del self._robot_active[rid]
        logger.info("mission %s COMPLETED (handover_latency_ms=%s)",
                    mission["mission_id"], mission["handover_latency_ms"])

    # ════════════════════════════════════════════════════════════════════
    # task_ack 수신 (DB 기록). REJECT의 FAILED 처리는 M3.
    # ════════════════════════════════════════════════════════════════════
    def on_task_ack(self, ack: dict) -> None:
        task_id = ack.get("task_id")
        result = ack.get("result")
        robot_id = ack.get("robot_id")
        db.execute("UPDATE tasks SET ack=?, ack_at=? WHERE task_id=?",
                   (result, db.utc_now_iso(), task_id))
        logger.info("task %s ack=%s (%s)", task_id, result, robot_id)

        if result != ACK_REJECT:
            return
        # 거절 → 미션 FAILED (시연 전제상 재배정 없음 — 정의서 부록 C)
        with self._lock:
            mission_id = self._robot_active.get(robot_id)
            mission = self._missions.get(mission_id) if mission_id else None
            if mission and mission["state"] in sm.ACTIVE_STATES:
                self._terminate(mission, MISSION_FAILED, "FAIL",
                                f"{robot_id} rejected task {task_id}")

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────
    def _issue_task(self, mission: dict, robot_id: str | None,
                    task_type: str, goal: dict | None,
                    cancel_task_id: str | None = None) -> str | None:
        if robot_id is None:
            return None
        task_id = _gen_id("TASK")
        msg = messages.if03(task_id, robot_id, task_type, goal or {},
                            mission["mission_id"], customer=mission["customer"],
                            cancel_task_id=cancel_task_id)
        mission["tasks"][task_id] = {"robot_id": robot_id, "task_type": task_type, "done": False}
        db.execute(
            "INSERT INTO tasks(task_id, mission_id, robot_id, task_type, goal_poi, "
            "issued_at, ack, ack_at, final_status, finished_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, mission["mission_id"], robot_id, task_type,
             (goal or {}).get("poi_id"), db.utc_now_iso(), None, None, None, None),
        )
        self.transport.publish(config.topic_task(robot_id), msg, config.QOS_TASK)
        logger.info("mission %s ▶ %s → %s (task %s)",
                    mission["mission_id"], task_type, robot_id, task_id)
        return task_id

    def _finish_task_row(self, task_id: str | None, status: str) -> None:
        if not task_id:
            return
        db.execute("UPDATE tasks SET final_status=?, finished_at=? WHERE task_id=?",
                   (status, db.utc_now_iso(), task_id))

    def _set_state(self, mission: dict, new_state: str, event: str, trigger: str = "") -> None:
        cur = mission["state"]
        expected = sm.next_state(cur, event)
        if expected is not None and expected != new_state:
            logger.warning("FSM mismatch: (%s, %s) expected %s but set %s",
                           cur, event, expected, new_state)
        mission["state"] = new_state
        now = db.utc_now_iso()
        db.execute(
            "INSERT INTO mission_transitions(mission_id, from_state, to_state, trigger, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (mission["mission_id"], cur, new_state, trigger or event, now),
        )
        db.execute("UPDATE missions SET state=? WHERE mission_id=?",
                   (new_state, mission["mission_id"]))
        logger.info("mission %s: %s → %s (%s)", mission["mission_id"], cur, new_state, event)

    def _base_goal(self, robot_id: str) -> dict | None:
        base_poi = config.ROBOTS.get(robot_id, {}).get("base_poi")
        return poi.goal_for(base_poi)

    # ════════════════════════════════════════════════════════════════════
    # 예외 처리 (정의서 §7 예외 매핑 / 계약 §10)
    # ════════════════════════════════════════════════════════════════════
    def _on_cancel(self, if01: dict) -> None:
        robot_id = if01.get("robot_id")
        mission_id = self._robot_active.get(robot_id)
        mission = self._missions.get(mission_id) if mission_id else None
        if not mission or mission["state"] not in sm.ACTIVE_STATES:
            logger.info("CANCEL from %s but no active mission", robot_id)
            return
        self._terminate(mission, MISSION_CANCELLED, "CANCEL", "user cancelled")

    def check_timeouts(self) -> None:
        """status 미수신(>STATUS_TIMEOUT) 로봇 → 미션 FAILED + 로봇 ERROR 표기.

        타임아웃 감시 스레드가 주기 호출(절대 규칙 2: sleep 흐름 아닌 주기 체크).
        """
        with self._lock:
            for robot_id in self.registry.stale_robots(config.STATUS_TIMEOUT):
                if robot_id in self._timed_out:
                    continue  # 이미 처리한 로봇은 중복 처리 안 함
                self._timed_out.add(robot_id)
                logger.warning("status timeout: %s silent > %.0fs → ERROR",
                               robot_id, config.STATUS_TIMEOUT)
                mission_id = self._robot_active.get(robot_id)
                mission = self._missions.get(mission_id) if mission_id else None
                if mission and mission["state"] in sm.ACTIVE_STATES:
                    self._terminate(mission, MISSION_FAILED, "FAIL",
                                    f"{robot_id} status timeout (>{config.STATUS_TIMEOUT:.0f}s)",
                                    silent_robot=robot_id)

    def _terminate(self, mission: dict, terminal_state: str, event: str,
                   reason: str, emergency_robot: str | None = None,
                   silent_robot: str | None = None) -> None:
        """미션을 종결 상태로 전이 + 관련 로봇에 복귀(취소) task 발행 + 로봇 해제."""
        if mission["state"] in sm.TERMINAL_STATES:
            return
        self._set_state(mission, terminal_state, event, reason)
        db.execute("UPDATE missions SET completed_at=? WHERE mission_id=?",
                   (db.utc_now_iso(), mission["mission_id"]))

        # 진행 중이던 task들을 취소하고 복귀 지시.
        # 단, 비상/통신두절 로봇엔 명령하지 않는다(로봇 소유 상태, 명령 무의미).
        existing = list(mission["tasks"].items())
        for robot_id in (mission["start_robot"], mission["next_robot"]):
            if robot_id is None:
                continue
            if robot_id in (emergency_robot, silent_robot):
                continue
            active_task = next(
                (tid for tid, t in reversed(existing)
                 if t["robot_id"] == robot_id and not t.get("done")),
                None,
            )
            self._issue_task(mission, robot_id, TASK_RETURN_TO_BASE,
                             self._base_goal(robot_id), cancel_task_id=active_task)
        # 기존 task는 취소된 것으로 표시(완료 이벤트 재처리 방지)
        for _tid, t in existing:
            t["done"] = True

        for robot_id in (mission["start_robot"], mission["next_robot"]):
            if self._robot_active.get(robot_id) == mission["mission_id"]:
                del self._robot_active[robot_id]

        logger.warning("mission %s %s — %s", mission["mission_id"], terminal_state, reason)
