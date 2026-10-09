#!/usr/bin/env bash
# Monitor live GUI mission for the low-battery -> return-to-dock -> seat ->
# charge -> resume loop.
#
# Portable: the container name and ROS distro come from ros-distro.sh, so this
# works on any machine without editing.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$DIR/ros-distro.sh"

LOG=/tmp/opencode/dockloop.txt
NAME="$CONTAINER_NAME"

# Sourcing preamble used inside the container. Kept in one variable so the
# distro is only written down once.
ROS_SRC=". /opt/ros/${ROS_DISTRO}/setup.bash >/dev/null 2>&1
. /workspace/install/setup.bash >/dev/null 2>&1"

> "$LOG"
for i in $(seq 1 48); do
  ts=$(date +%H:%M:%S)
  batt=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 5 ros2 topic echo /battery_state --once 2>/dev/null | grep -m1 percentage | grep -oE \"[0-9.]+\"" 2>/dev/null)
  seated=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 5 ros2 topic echo /dock/state --once 2>/dev/null | grep -m1 seated | grep -oE \"(true|false)\"" 2>/dev/null)
  mode=$(docker logs "$NAME" 2>&1 | grep -E "mission_supervisor" | grep -oE "return-to-dock|charging|SEATED|creeping|actively charging|resuming mission|overall mission" | tail -1)
  goal=$(docker logs "$NAME" 2>&1 | grep -oE "goal [0-9]+/[0-9]+" | tail -1)
  echo "$ts batt=${batt:-NA}% seated=${seated:-NA} mission=$goal $mode" >> "$LOG"
  # stop early if we saw a charge->resume transition
  if grep -qE "resuming mission" "$LOG"; then echo "DONE - charge->resume observed" >> "$LOG"; break; fi
  sleep 20
done
echo "=== final ==="; tail -6 "$LOG"
