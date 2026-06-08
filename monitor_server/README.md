# Monitoring Server

This directory contains the monitoring-only server.

It receives ROS2 messages, stores observation data in SQLite, and serves
the administrator dashboard. It does not create missions, dispatch tasks, or
control robots.

## Runtime Flow

```text
Robot status   -> ROS2 /robot2/robot_state, /robot4/robot_state -> monitor_server -> latest_robot_status + robot_status_log
Detector event -> ROS2 /robot2/vision/alert, /robot4/vision/alert -> monitor_server -> events
Admin browser -> Flask API/dashboard -> read SQLite
```

## Run

```bash
cd /home/rokey/Desktop/alfred_ws/monitor_server
source /opt/ros/humble/setup.bash
source ../install/setup.bash
unset ROS_DISCOVERY_SERVER
export ROS_DOMAIN_ID=2
python3 main.py
```

Dashboard:

```text
http://localhost:5000
admin / admin1234
```

## Kept Modules

| File | Role |
| --- | --- |
| `main.py` | Starts ROS2 subscriptions and Flask API |
| `ros_ingest.py` | ROS2 RobotState/Event subscriptions |
| `robot_registry.py` | Robot status ingestion into SQLite |
| `event_service.py` | Detector event ingestion |
| `db.py` | SQLite tables for monitoring records |
| `api.py` | Read-only dashboard/API routes plus event resolve |
| `web/dashboard.html` | Admin monitoring dashboard |

## ROS2 Topics

The server subscribes only to:

```text
/robot2/robot_state
/robot4/robot_state
/robot2/vision/alert
/robot4/vision/alert
```

## SQLite Tables

```text
latest_robot_status
robot_status_log
events
ui_usage_log
monitor_counters
```

Old mission/task tables may still exist inside an existing `fms.db` file if the
database was created before the monitoring-only refactor, but this server no
longer creates, writes, or reads them.

## Test Tools

```bash
ros2 topic echo /robot2/robot_state
ros2 topic echo /robot2/vision/alert
```
