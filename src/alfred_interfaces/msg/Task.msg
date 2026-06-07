# IF-03 임무 할당 (FMS → 브리지 robot/{id}/task → 재발행 → behavior_node 수행)
# FMS가 로봇에 내리는 유일한 명령. 목표 상태가 아니라 task만 보낸다.

string task_id
string robot_id
string task_type          # MOVE_TO_STANDBY|ESCORT_TO_HANDOVER|ESCORT_TO_FINAL|RETURN_TO_BASE
string goal_poi_id
geometry_msgs/Pose2D goal_pose
int32 goal_floor
string customer_id        # 없으면 ""
string customer_profile   # 예: ELDERLY (없으면 "")
string customer_language  # 예: ko (없으면 "")
string mission_id
string cancel_task_id     # 취소 대상 task_id, 없으면 ""
string timestamp          # ISO 8601, ms 포함
