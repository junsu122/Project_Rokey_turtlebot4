# IF-01 고객 요청 (Interaction → 브리지 robot/{id}/request → FMS). ESCORT/CANCEL.

string request_id
string robot_id
string request_type       # ESCORT|CANCEL
string dest_poi_id        # 목적지 POI (Interaction이 검증 완료한 값)
int32 dest_floor
int32 origin_floor
geometry_msgs/Pose2D origin_pose
string customer_id
string customer_profile    # 예: ELDERLY
string customer_language   # 예: ko
string target_request_id   # CANCEL 시 취소 대상, 없으면 ""
string timestamp           # ISO 8601, ms 포함
