# Monitoring Server

This directory contains the monitoring-only server.

It receives MQTT JSON messages, stores observation data in SQLite, and serves
the administrator dashboard. It does not create missions, dispatch tasks, or
control robots.

## Runtime Flow

```text
Robot/bridge status  -> MQTT robot/+/status -> monitor_server -> memory + robot_status_log
Detector events      -> MQTT robot/+/event  -> monitor_server -> events
Admin browser        -> Flask API/dashboard -> read memory + SQLite
```

## Run

```bash
sudo systemctl start mosquitto
cd /home/rokey/Desktop/alfred_ws/monitor_server
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
| `main.py` | Starts MQTT subscriptions and Flask API |
| `transport.py` | MQTT JSON wrapper |
| `robot_registry.py` | Latest robot status snapshot + status-change log |
| `event_service.py` | Detector event ingestion |
| `db.py` | SQLite tables for monitoring records |
| `api.py` | Read-only dashboard/API routes plus event resolve |
| `web/dashboard.html` | Admin monitoring dashboard |

## MQTT Topics

The server subscribes only to:

```text
robot/+/status
robot/+/event
```

Removed control topics:

```text
robot/+/request
robot/+/task
robot/+/task_ack
```

## SQLite Tables

```text
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
python3 tools/echo_test.py
python3 tools/send_event.py --robot-id robot2 --type FIRE --class fire --floor 1 --x 1.2 --y 3.4
python3 tools/demo_events.py --count 5
```
