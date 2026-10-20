#!/usr/bin/env bash
# =============================================================================
# run_all.sh - one command for the whole simulation stack
# =============================================================================
#   ./run_all.sh            kill stale instances, launch everything, verify
#   ./run_all.sh --stop     kill stale instances (container, watchdog, monitors)
#   ./run_all.sh --verify   re-run the health checks against the live stack
#
# Brings up, all in one go:
#   * Gazebo GUI + RViz + Nav2 + SLAM + mission loop   (inside Docker)
#   * Foxglove bridge            -> https://app.foxglove.dev, ws://localhost:8765
#   * stall watchdog             -> /tmp/opencode/watchdog.log
#   * battery / dock monitor     -> /tmp/opencode/dockloop.txt
#
# Stale instances are killed first, and in this order on purpose: the watchdog
# must die before the container, otherwise it sees the container disappear and
# relaunches it underneath us.
#
# The distro and container name come from ros-distro.sh - nothing here is
# hardcoded to one machine.
# =============================================================================
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR=/tmp/opencode
mkdir -p "$LOGDIR"

# shellcheck disable=SC1091
. "$DIR/ros-distro.sh"

MODE="all"
case "${1:-}" in
  --stop)   MODE="stop" ;;
  --verify) MODE="verify" ;;
  "") ;;
  *) echo "Usage: $0 [--stop|--verify]" >&2; exit 2 ;;
esac

# --- Docker access ----------------------------------------------------------
# The user may be in the docker group without this login session knowing it
# yet (group membership is only applied at login), which shows up as
# "permission denied" on the socket. Re-exec through sg once so the one
# command works either way.
if ! docker info >/dev/null 2>&1; then
  if sg docker -c "docker info" >/dev/null 2>&1; then
    exec sg docker -c "bash '$DIR/run_all.sh' ${1:-}"
  fi
  echo "ERROR: Docker daemon not reachable (see ./run_docker.sh for hints)." >&2
  exit 1
fi

# --- Kill stale instances ---------------------------------------------------
kill_stale() {
  echo "==> Killing stale instances"
  local pat pid
  # Host-side helpers from previous runs. These patterns never match this
  # script's own command line, so only the real helpers are hit.
  for pat in 'watchdog\.sh' 'monitor_loop\.sh'; do
    for pid in $(pgrep -f "$pat" 2>/dev/null || true); do
      if [ "$pid" != "$$" ] && [ "$pid" != "${BASHPID:-}" ]; then
        kill "$pid" 2>/dev/null && echo "    stopped ${pat} (pid ${pid})" || true
      fi
    done
  done

  # The container holds Gazebo, RViz, Nav2, SLAM, the mission supervisor and
  # the Foxglove bridge - removing it clears all of them at once.
  if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    echo "    removed container ${CONTAINER_NAME}"
  fi

  sleep 1
  # Stray host processes from a native (non-Docker) run, if any. The container
  # is already gone by now, so anything still matching lives on the host.
  for pat in 'gz sim' 'gz-sim' 'rviz2' 'parameter_bridge' 'slam_toolbox' 'foxglove_bridge'; do
    pkill -f "$pat" 2>/dev/null && echo "    killed stray host process: ${pat}" || true
  done
}

# --- Verify -----------------------------------------------------------------
verify() {
  echo "==> Verifying stack (container: ${CONTAINER_NAME})"
  local fail=0 code
  ok()  { printf '  [OK]   %s\n' "$1"; }
  bad() { printf '  [FAIL] %s\n' "$1"; fail=1; }

  # RViz and the monitors come up a little after the Nav2 READY marker, so a
  # single instantaneous probe reports false failures right after launch.
  # retry() re-runs a check for up to ~60s before declaring it dead.
  retry() {
    local i
    for i in $(seq 1 12); do
      "$@" >/dev/null 2>&1 && return 0
      sleep 5
    done
    return 1
  }

  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_NAME"; then
    bad "container ${CONTAINER_NAME} not running"
    echo "==> 1 check failed."
    return 1
  fi
  ok "container ${CONTAINER_NAME} running"

  # pipefail must be off here: `grep -q` exits on the first match, docker logs
  # then dies with SIGPIPE (141), and pipefail would report the pipeline as
  # failed even though the pattern matched.
  ctop_has() {
    set +o pipefail
    docker top "$CONTAINER_NAME" 2>&1 | grep -q "$1"
    local st=$?
    set -o pipefail
    return $st
  }
  clog_has() {
    set +o pipefail
    docker logs "$CONTAINER_NAME" 2>&1 | grep -q "$1"
    local st=$?
    set -o pipefail
    return $st
  }

  if retry ctop_has gz-sim-main; then
    ok "Gazebo (gz-sim-main) running"
  else
    bad "Gazebo not running"
  fi

  if retry ctop_has rviz2; then
    ok "RViz running"
  else
    bad "RViz not running"
  fi

  if retry clog_has "Nav2 lifecycle bringup complete"; then
    ok "Nav2 lifecycle bringup complete"
  else
    bad "Nav2 bringup marker not seen yet (wait ~90s after launch)"
  fi

  # The bridge is a WebSocket server and only accepts the foxglove subprotocol;
  # a plain page load returns 400, so probe with a real upgrade request.
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    -H 'Sec-WebSocket-Protocol: foxglove.sdk.v1' \
    http://localhost:8765 2>/dev/null || true)
  if [ "$code" = "101" ]; then
    ok "Foxglove bridge accepts WebSocket on ws://localhost:8765"
  else
    bad "Foxglove handshake returned HTTP ${code:-none} (expected 101)"
  fi

  battery_ok() {
    docker exec "$CONTAINER_NAME" bash -lc \
      ". /opt/ros/${ROS_DISTRO}/setup.bash >/dev/null 2>&1; . /workspace/install/setup.bash >/dev/null 2>&1; timeout 8 ros2 topic echo /battery_state --once 2>/dev/null | grep -m1 percentage" \
      >/dev/null 2>&1
  }
  if retry battery_ok; then
    ok "/battery_state publishing"
  else
    bad "/battery_state not publishing"
  fi

  if pgrep -f 'watchdog\.sh' >/dev/null; then
    ok "watchdog running (log: ${LOGDIR}/watchdog.log)"
  else
    bad "watchdog not running"
  fi

  if pgrep -f 'monitor_loop\.sh' >/dev/null; then
    ok "battery monitor running (log: ${LOGDIR}/dockloop.txt)"
  else
    bad "battery monitor not running"
  fi

  if [ "$fail" -eq 0 ]; then
    echo "==> All checks passed."
  else
    echo "==> Some checks FAILED."
  fi
  return "$fail"
}

# --- Modes ------------------------------------------------------------------
case "$MODE" in
  stop)
    kill_stale
    echo "Stopped."
    ;;

  all)
    kill_stale
    # Blocks until Nav2 reports READY (or ~180s timeout); also copies the
    # helper scripts into the fresh container and starts the watchdog.
    "$DIR/run_gui_loop.sh"

    # Battery / dock monitor, looping forever. APPEND keeps history across
    # passes instead of truncating dockloop.txt every cycle.
    nohup env APPEND=1 bash -c "while :; do bash '$DIR/monitor_loop.sh'; sleep 5; done" \
      >>"${LOGDIR}/monitor_loop.out" 2>&1 &
    echo "Battery monitor PID $!  log=${LOGDIR}/dockloop.txt"

    echo
    echo "Foxglove: open https://app.foxglove.dev and connect to ws://localhost:8765"
    echo "Logs:     docker logs -f ${CONTAINER_NAME}   (also: ${LOGDIR}/watchdog.log, ${LOGDIR}/dockloop.txt)"
    echo "Stop:     ./run_all.sh --stop"
    echo
    verify
    ;;

  verify)
    verify
    ;;
esac
