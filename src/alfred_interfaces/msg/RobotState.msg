# IF-02 로봇 상태 보고 (Driving/behavior_node → 브리지 → FMS robot/{id}/status)
# Robot State는 behavior_node 단독 소유. FMS는 관측만 한다.

string robot_id
string state              # IDLE|PATROL|INTERACTING|RESERVED|HANDOVER_READY|ESCORTING|WAITING_HANDOVER|RETURNING|EMERGENCY|ERROR
geometry_msgs/Pose2D pose # x, y, theta (ROS map 프레임, 미터/라디안)
int32 battery             # 0~100 (%)
string current_task_id    # 없으면 "" (기본동작: 순찰/대기)
string task_status        # ACCEPTED|RUNNING|SUCCEEDED|FAILED|""
string error_code         # 없으면 ""
string timestamp          # ISO 8601, ms 포함
