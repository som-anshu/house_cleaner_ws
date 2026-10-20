#!/usr/bin/env bash
# Launch GUI sim with mission_loop:=true, then watchdog for stalls.
# Usage: ./run_gui_loop.sh
#
# Display and GPU setup is NOT done here - run_docker.sh owns that, and it
# detects Wayland vs X11, native Docker vs Docker Desktop, and GPU availability
# on its own. This file used to duplicate all of it, including a hardcoded
# /run/user/1000/.mutter-Xwaylandauth.<random> filename that only existed on
# one particular machine and made the script fail everywhere else.

set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG=/tmp/opencode/gui_loop_watchdog.log
mkdir -p /tmp/opencode

# ros-distro.sh resolves the distro and the container name.
# shellcheck disable=SC1091
. "$DIR/ros-distro.sh"

cd "$DIR"
echo "Relaunching GUI + mission_loop (distro: ${ROS_DISTRO}, container: ${CONTAINER_NAME})..."

# XAUTHORITY is deliberately unset. Feeding our own generated cookie back in as
# the source used to produce a 0-byte rebuild; run_docker.sh rebuilds a fresh
# one when the Docker Desktop path actually needs it.
env -u XAUTHORITY ./run_docker.sh \
  --launch house_cleaner_bringup house_cleaning.launch.py \
  mode:=sim headless:=false use_sim_time:=true gui:=true mission_loop:=true

# Helpers for ROS one-liners
if [ -f /tmp/opencode/ros_exec.sh ]; then
  docker cp /tmp/opencode/ros_exec.sh "$CONTAINER_NAME:/tmp/ros_exec.sh" || true
  docker exec "$CONTAINER_NAME" chmod +x /tmp/ros_exec.sh || true
fi
if [ -f /tmp/opencode/set_drain.sh ]; then
  docker cp /tmp/opencode/set_drain.sh "$CONTAINER_NAME:/tmp/set_drain.sh" || true
  docker exec "$CONTAINER_NAME" chmod +x /tmp/set_drain.sh || true
fi

# Prefer repo scripts (versioned); fall back to /tmp/opencode copies.
for helper in diag_stuck.py cancel_nav.py; do
  if [ -f "$DIR/scripts/$helper" ]; then
    docker cp "$DIR/scripts/$helper" "$CONTAINER_NAME:/tmp/$helper" || true
    cp "$DIR/scripts/$helper" "/tmp/opencode/$helper" 2>/dev/null || true
  elif [ -f "/tmp/opencode/$helper" ]; then
    docker cp "/tmp/opencode/$helper" "$CONTAINER_NAME:/tmp/$helper" || true
  fi
done

# Single recover-capable watchdog (also handles container-down restart).
if [ -f "$DIR/watchdog.sh" ]; then
  cp "$DIR/watchdog.sh" /tmp/opencode/watchdog.sh
  chmod +x /tmp/opencode/watchdog.sh "$DIR/watchdog.sh"
  # Stop prior watchdogs (repo path, /tmp copy, and old embedded bash -c).
  for pid in $(pgrep -f 'watchdog\.sh|gui_loop_watchdog|LAST_TS=' 2>/dev/null || true); do
    if [ "$pid" != "$$" ] && [ "$pid" != "${BASHPID:-}" ]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  nohup bash "$DIR/watchdog.sh" >>/tmp/opencode/watchdog.out 2>&1 &
  echo "Watchdog PID $!  log=/tmp/opencode/watchdog.log"
else
  echo "WARNING: watchdog.sh missing - no stall recovery"
fi
echo "Foxglove: open https://app.foxglove.dev and connect to ws://localhost:8765 (WebSocket, not a web page)"
echo "Stop: docker stop $CONTAINER_NAME"
