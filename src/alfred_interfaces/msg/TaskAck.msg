# task_ack 수락/거절 (behavior_node → 브리지 robot/{id}/task_ack → FMS).
# 거절 규칙(계약 §6.2): PATROL/IDLE 상태에서 받은 ESCORT 계열 task는 REJECT.

string task_id
string robot_id
string result             # ACCEPT|REJECT
string timestamp          # ISO 8601, ms 포함
