#!/usr/bin/env bash
# Launch GUI sim with mission_loop:=true, then watchdog for stalls.
# Usage: ./run_gui_loop.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME=house_cleaner_jazzy
LOG=/tmp/opencode/gui_loop_watchdog.log
mkdir -p /tmp/opencode

# Wildcard Xauth for TCP-forwarded X11 clients (AGENTS.md recipe).
XAUTH_SRC="${XAUTHORITY:-/run/user/1000/.mutter-Xwaylandauth.1Z2BW3}"
if [ ! -f "$XAUTH_SRC" ]; then
  XAUTH_SRC="$(ls -t /run/user/1000/.mutter-Xwaylandauth.* 2>/dev/null | head -1 || true)"
fi
if [ -z "${XAUTH_SRC:-}" ] || [ ! -f "$XAUTH_SRC" ]; then
  echo "ERROR: no Xauthority source found (need mutter Xwayland cookie)"
  exit 1
fi
rm -f /tmp/xauth_docker
touch /tmp/xauth_docker
xauth -f "$XAUTH_SRC" nlist :0 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f /tmp/xauth_docker nmerge - || true
chmod 644 /tmp/xauth_docker
echo "xauth cookie ready from $XAUTH_SRC ($(wc -c </tmp/xauth_docker) bytes)"

# Ensure socat X11 forward is up (run_docker also does this).
if [ -S /tmp/.X11-unix/X0 ] && ! ss -ltn 2>/dev/null | grep -q ':6000 '; then
  setsid nohup socat "TCP-LISTEN:6000,reuseaddr,fork" "UNIX-CONNECT:/tmp/.X11-unix/X0" \
    >/tmp/opencode/x11_socat_0.log 2>&1 &
  sleep 1
fi

cd "$DIR"
echo "Relaunching GUI + mission_loop..."
XAUTHORITY=/tmp/xauth_docker ./run_docker.sh \
  --launch house_cleaner_bringup house_cleaning.launch.py \
  mode:=sim headless:=false use_sim_time:=true gui:=true mission_loop:=true

# Helpers for ROS one-liners
if [ -f /tmp/opencode/ros_exec.sh ]; then
  docker cp /tmp/opencode/ros_exec.sh "$NAME:/tmp/ros_exec.sh" || true
  docker exec "$NAME" chmod +x /tmp/ros_exec.sh || true
fi
if [ -f /tmp/opencode/set_drain.sh ]; then
  docker cp /tmp/opencode/set_drain.sh "$NAME:/tmp/set_drain.sh" || true
  docker exec "$NAME" chmod +x /tmp/set_drain.sh || true
fi
if [ -f /tmp/opencode/diag_stuck.py ]; then
  docker cp /tmp/opencode/diag_stuck.py "$NAME:/tmp/diag_stuck.py" || true
fi

# Stall watchdog: no new mission log line for 180s while running → dump diag.
nohup bash -c "
  LAST=''
  LAST_TS=\$(date +%s)
  while true; do
    sleep 15
    if ! docker ps --format '{{.Names}}' | grep -qx '$NAME'; then
      echo \"\$(date -Is) CONTAINER_DOWN — restarting via run_docker.sh\" | tee -a '$LOG'
      XAUTHORITY=/tmp/xauth_docker '$DIR/run_docker.sh' \
        --launch house_cleaner_bringup house_cleaning.launch.py \
        mode:=sim headless:=false use_sim_time:=true gui:=true mission_loop:=true \
        >>'$LOG' 2>&1 || true
      docker cp /tmp/opencode/ros_exec.sh '$NAME:/tmp/ros_exec.sh' 2>/dev/null || true
      LAST=''; LAST_TS=\$(date +%s)
      continue
    fi
    LINE=\$(docker logs --since 5m '$NAME' 2>&1 | grep -E 'mission_supervisor|COVERAGE|MISSION|CHARG|DOCK|goal |LOW BATTERY|loop' | tail -1 || true)
    if [ -n \"\$LINE\" ] && [ \"\$LINE\" != \"\$LAST\" ]; then
      LAST=\"\$LINE\"; LAST_TS=\$(date +%s); continue
    fi
    NOW=\$(date +%s)
    if [ \$((NOW - LAST_TS)) -ge 180 ]; then
      echo \"\$(date -Is) STALL \$((NOW-LAST_TS))s last='\$LINE'\" | tee -a '$LOG'
      docker exec '$NAME' python3 /tmp/diag_stuck.py >>'$LOG' 2>&1 || true
      docker logs --tail 80 '$NAME' >>'$LOG' 2>&1 || true
      LAST_TS=\$NOW
    fi
  done
" >/tmp/opencode/gui_loop_watchdog.out 2>&1 &
echo "Watchdog PID $!  log=$LOG"
echo "Foxglove: http://localhost:8765"
echo "Stop: docker stop $NAME"
