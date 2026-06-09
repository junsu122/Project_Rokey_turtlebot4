# mission_signal — partner 로봇 간 예외 전파 전용 (ABORT|EMERGENCY|TASK_FAILED).
# fms_server 폐기로 사라진 중앙 _terminate 캐스케이드를 대체하는 유일한
# 비-task 피어투피어 채널 — 한쪽의 취소/비상/실패를 상대에게 즉시 알린다.

string mission_id
string robot_id           # 신호의 원인이 된(보낸) 로봇
string signal             # ABORT|EMERGENCY|TASK_FAILED
string reason
string timestamp          # ISO 8601, ms 포함
