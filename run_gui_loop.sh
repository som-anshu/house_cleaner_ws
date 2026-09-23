#!/usr/bin/env bash
# Launch GUI sim with mission_loop:=true, then watchdog for stalls.
# Usage: ./run_gui_loop.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAME=house_cleaner_jazzy
LOG=/tmp/opencode/gui_loop_watchdog.log
mkdir -p /tmp/opencode

# Wildcard Xauth for TCP-forwarded X11 clients (AGENTS.md recipe).
# Never trust XAUTHORITY if it points at our own (possibly empty) output
# cookie — watchdog restarts used to export XAUTHORITY=/tmp/xauth_docker
# and then failed to rebuild it (nlist on an empty file → 0-byte cookie).
XAUTH_SRC=""
if [ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ] && [ "$XAUTHORITY" != "/tmp/xauth_docker" ] \
   && [ -s "$XAUTHORITY" ]; then
  XAUTH_SRC="$XAUTHORITY"
fi
if [ -z "$XAUTH_SRC" ]; then
  for cand in /run/user/1000/.mutter-Xwaylandauth.* "$HOME/.Xauthority"; do
    # shellcheck disable=SC2086
    if [ -f $cand ] && [ -s $cand ]; then XAUTH_SRC=$cand; break; fi
  done
fi
# Prefer mutter cookie over anything else when present.
if [ -s /run/user/1000/.mutter-Xwaylandauth.1Z2BW3 ]; then
  XAUTH_SRC=/run/user/1000/.mutter-Xwaylandauth.1Z2BW3
else
  M=$(ls -t /run/user/1000/.mutter-Xwaylandauth.* 2>/dev/null | head -1 || true)
  if [ -n "$M" ] && [ -s "$M" ]; then XAUTH_SRC="$M"; fi
fi
if [ -z "${XAUTH_SRC:-}" ] || [ ! -s "$XAUTH_SRC" ]; then
  echo "ERROR: no non-empty Xauthority source found (need mutter Xwayland cookie)"
  exit 1
fi
rm -f /tmp/xauth_docker
touch /tmp/xauth_docker
# nlist writes to stdout; feed via file to avoid stdin-empty race under pipefail.
xauth -f "$XAUTH_SRC" nlist :0 2>/dev/null > /tmp/opencode/xauth_nlist.txt || true
if [ ! -s /tmp/opencode/xauth_nlist.txt ]; then
  xauth -f "$XAUTH_SRC" nlist 2>/dev/null > /tmp/opencode/xauth_nlist.txt || true
fi
if [ -s /tmp/opencode/xauth_nlist.txt ]; then
  sed -e 's/^..../ffff/' /tmp/opencode/xauth_nlist.txt > /tmp/opencode/xauth_nlist_ff.txt
  xauth -f /tmp/xauth_docker nmerge - < /tmp/opencode/xauth_nlist_ff.txt || true
fi
chmod 644 /tmp/xauth_docker
if [ ! -s /tmp/xauth_docker ]; then
  echo "ERROR: failed to build wildcard xauth cookie from $XAUTH_SRC"
  exit 1
fi
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
# Prefer repo scripts (versioned); fall back to /tmp/opencode copies.
for helper in diag_stuck.py cancel_nav.py; do
  if [ -f "$DIR/scripts/$helper" ]; then
    docker cp "$DIR/scripts/$helper" "$NAME:/tmp/$helper" || true
    cp "$DIR/scripts/$helper" "/tmp/opencode/$helper" 2>/dev/null || true
  elif [ -f "/tmp/opencode/$helper" ]; then
    docker cp "/tmp/opencode/$helper" "$NAME:/tmp/$helper" || true
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
  echo "WARNING: watchdog.sh missing — no stall recovery"
fi
echo "Foxglove: http://localhost:8765"
echo "Stop: docker stop $NAME"
