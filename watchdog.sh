#!/usr/bin/env bash
# Watchdog with recovery:
#  - container down            -> relaunch GUI loop
#  - no new mission log 180s   -> diag dump
#  - repeated RETURNING TIMEOUT / battery empty / vel-chain silent
#                              -> cancel goals + bounce smoother/collision_monitor
#                              -> full restart if still stuck
#
# Portable: workspace root, ROS distro and container name are all derived, not
# hardcoded, so this file works on any machine and any distro.

set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ros-distro.sh resolves ROS_DISTRO and CONTAINER_NAME. It is safe to source
# even with `set -u` because it only reads already-set variables.
# shellcheck disable=SC1091
. "$DIR/ros-distro.sh"

NAME="$CONTAINER_NAME"
LOG=/tmp/opencode/watchdog.log
INTERVAL=15
STALL=180
# consecutive recovery failures before full container restart
MAX_SOFT=2
# debounce: velocity-chain probe must hit twice in a row before we bounce
CHAIN_HIT=0

mkdir -p /tmp/opencode
echo "$(date -Is) watchdog start (recover mode) distro=${ROS_DISTRO} container=${NAME}" >>"$LOG"

# Source the ROS distro and the workspace overlay inside a container. Used in
# several places, so it lives in one variable. Note: no `set -u` inside -
# setup.bash dereferences unset AMENT_TRACE_* variables.
ROS_SRC=". /opt/ros/${ROS_DISTRO}/setup.bash >/dev/null 2>&1
. /workspace/install/setup.bash >/dev/null 2>&1"

LAST=""
LAST_TS=$(date +%s)
SOFT=0
LAST_REASON=""

up() {
  docker ps --format '{{.Names}}' | grep -qx "$NAME"
}

copy_helpers() {
  [ -f /tmp/opencode/ros_exec.sh ] && docker cp /tmp/opencode/ros_exec.sh "$NAME:/tmp/ros_exec.sh" 2>/dev/null || true
  [ -f /tmp/opencode/cancel_nav.py ] && docker cp /tmp/opencode/cancel_nav.py "$NAME:/tmp/cancel_nav.py" 2>/dev/null || true
  [ -f /tmp/opencode/diag_stuck.py ] && docker cp /tmp/opencode/diag_stuck.py "$NAME:/tmp/diag_stuck.py" 2>/dev/null || true
}

restart_gui() {
  echo "$(date -Is) FULL_RESTART via run_gui_loop" | tee -a "$LOG"
  # Do NOT export XAUTHORITY=/tmp/xauth_docker - that empty/self cookie
  # used to be fed back as the source and produced a 0-byte rebuild.
  env -u XAUTHORITY "$DIR/run_gui_loop.sh" >>"$LOG" 2>&1 || true
  echo "$(date -Is) handed off to run_gui_loop watchdog" | tee -a "$LOG"
  exit 0
}

soft_recover() {
  local reason="$1"
  echo "$(date -Is) RECOVER reason=$reason soft=$SOFT" | tee -a "$LOG"
  copy_helpers
  docker logs --tail 80 "$NAME" >>"$LOG" 2>&1 || true
  docker exec "$NAME" bash -lc "$ROS_SRC
    python3 /tmp/diag_stuck.py 6" >>"$LOG" 2>&1 || true
  docker exec "$NAME" bash -lc "$ROS_SRC
    python3 /tmp/cancel_nav.py" >>"$LOG" 2>&1 || true
  # Bounce the tail of the velocity chain (common starvation / dead monitor).
  docker exec "$NAME" bash -lc "$ROS_SRC
    ros2 lifecycle set /velocity_smoother deactivate >/dev/null 2>&1 || true
    sleep 1
    ros2 lifecycle set /velocity_smoother activate >/dev/null 2>&1 || true
    ros2 lifecycle set /collision_monitor deactivate >/dev/null 2>&1 || true
    sleep 1
    ros2 lifecycle set /collision_monitor activate >/dev/null 2>&1 || true
    echo recovered_chain" >>"$LOG" 2>&1 || true
  SOFT=$((SOFT + 1))
  LAST_TS=$(date +%s)
  LAST=""
  if [ "$SOFT" -ge "$MAX_SOFT" ]; then
    echo "$(date -Is) soft recover failed $SOFT times - full restart" | tee -a "$LOG"
    restart_gui
  fi
}

# Returns a reason string on stdout, empty if healthy enough.
probe_reason() {
  # 1) log silence
  local now age
  now=$(date +%s)
  age=$((now - LAST_TS))
  if [ "$age" -ge "$STALL" ]; then
    echo "LOG_SILENCE_${age}s"
    return
  fi
  # 2) mission wedged: fresh stall lines AND no progress markers.
  #    The window must be SHORT and progress must be zero: the old check
  #    counted VEL_STALL lines over 6 minutes, so one goal that stalled and
  #    then recovered (4 lines) kept tripping for minutes after the mission
  #    was already reaching goals again — that fed full-restart loops
  #    (2026-10-20 19:08-19:26).  "Reached the goal!"/DOCKED/CHARGED in the
  #    last 240 s means the stack is alive; skip.
  local stalls reached
  stalls=$(docker logs --since 100s "$NAME" 2>/dev/null \
    | grep -c 'Return-to-dock approach TIMEOUT\|RETURN BUDGET exceeded\|BATTERY EMPTY\|VEL_CHAIN_STALL\|VEL_STALL' \
    || true)
  if [ "${stalls:-0}" -ge 4 ]; then
    reached=$(docker logs --since 240s "$NAME" 2>/dev/null \
      | grep -c 'Reached the goal!\|DOCKED\|CHARGED to' \
      || true)
    if [ "${reached:-0}" -eq 0 ]; then
      echo "STUCK_PATTERN stalls=${stalls} reached=${reached}"
      return
    fi
  fi
  # 3) battery empty while not charging
  local pct seated charge
  pct=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 3 ros2 topic echo /battery_state --once 2>/dev/null \
      | grep -m1 percentage | grep -oE \"[0-9.]+\" | head -1" 2>/dev/null || true)
  seated=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 3 ros2 topic echo /dock/seated --once 2>/dev/null \
      | grep -oE \"(true|false)\" | head -1" 2>/dev/null || true)
  if [ -n "${pct:-}" ]; then
    # empty if percentage field (0..1) is ~0 OR raw 0
    if awk -v p="$pct" 'BEGIN { exit !(p <= 0.01) }'; then
      if [ "${seated:-false}" != "true" ]; then
        echo "BATTERY_EMPTY pct=$pct seated=$seated"
        return
      fi
    fi
  fi
  # 4) velocity chain: nav live, final silent (quick 2s hz probe).
  #    Debounced: one 3 s window under host load or during an inter-goal gap
  #    can read empty, and the bounce it triggers itself creates 4 s of real
  #    /cmd_vel silence that looks like a stall to the supervisor.  Require
  #    two consecutive hits (one probe interval apart) before reacting.
  local nav_hz out_hz
  nav_hz=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 3 ros2 topic hz /cmd_vel_nav 2>/dev/null | head -1 | grep -oE \"[0-9.]+\" | head -1" 2>/dev/null || true)
  out_hz=$(docker exec "$NAME" bash -lc "$ROS_SRC
    timeout 3 ros2 topic hz /cmd_vel 2>/dev/null | head -1 | grep -oE \"[0-9.]+\" | head -1" 2>/dev/null || true)
  if [ -n "${nav_hz:-}" ] && awk -v h="$nav_hz" 'BEGIN { exit !(h >= 2) }'; then
    if [ -z "${out_hz:-}" ] || awk -v h="$out_hz" 'BEGIN { exit !(h < 1) }'; then
      if [ "${CHAIN_HIT:-0}" -ge 1 ]; then
        echo "VEL_CHAIN nav_hz=$nav_hz out_hz=${out_hz:-0}"
        return
      fi
      CHAIN_HIT=1
      return
    fi
  fi
  CHAIN_HIT=0
  echo ""
}

while true; do
  sleep "$INTERVAL"
  if ! up; then
    echo "$(date -Is) CONTAINER_DOWN - restarting GUI loop" | tee -a "$LOG"
    restart_gui
  fi

  LINE=$(docker logs --since 3m "$NAME" 2>&1 \
    | grep -E 'mission_supervisor|COVERAGE|MISSION|CHARG|DOCK|goal |LOW BATTERY|MISSION LOOP|BATTERY EMPTY|VEL_CHAIN|RETURN BUDGET' \
    | tail -1 || true)
  if [ -n "$LINE" ] && [ "$LINE" != "$LAST" ]; then
    LAST="$LINE"
    LAST_TS=$(date +%s)
    echo "$(date -Is) progress: $LINE" >>"$LOG"
    # healthy chatter resets soft-recover budget
    case "$LINE" in
      *CHARGING*|*CHARGED*|*Parked*|*COVERAGE*|*done*) SOFT=0 ;;
    esac
  fi

  # Always probe - a chatty-but-stuck mission (VEL_STALL storm) must not
  # skip recovery just because each log line differs from the last.
  REASON=$(probe_reason)
  if [ -n "$REASON" ]; then
    if [ "$REASON" != "$LAST_REASON" ]; then
      LAST_REASON="$REASON"
    fi
    soft_recover "$REASON"
  else
    LAST_REASON=""
  fi
done
