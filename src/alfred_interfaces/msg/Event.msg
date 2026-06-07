# IF-05 이상 상황 알림 (Vision/yolo_monitor_node → 브리지 robot/{id}/event → FMS).

string event_type         # FIRE|SUSPICIOUS_PERSON
string robot_id
float32 confidence        # 0.0~1.0
geometry_msgs/Pose2D location
int32 floor
string snapshot_ref       # 스냅샷 참조(URL/경로), 없으면 ""
string timestamp          # ISO 8601, ms 포함
