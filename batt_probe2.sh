#!/usr/bin/env bash
# Diagnose why /battery_state is frozen: which battery node is really running,
# and does the command_velocity the sim wires to actually have a live publisher?
#
# Run INSIDE the container (ros2 must be on PATH), or on the host with ROS
# sourced. The distro is detected, not hardcoded.
set -u
if [ -n "${ROS_DISTRO:-}" ] && [ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
    . "/opt/ros/${ROS_DISTRO}/setup.bash" >/dev/null 2>&1
elif [ -f /workspace/install/setup.bash ]; then
    # In a container: the image sets ROS_DISTRO; fall back to the only install.
    for _s in /opt/ros/*/setup.bash; do
        [ -f "$_s" ] && . "$_s" && break
    done
    [ -f /workspace/install/setup.bash ] && . /workspace/install/setup.bash >/dev/null 2>&1
else
    # On the host: use the workspace repo copy to find the distro.
    _DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    [ -f "$_DIR/ros-distro.sh" ] && . "$_DIR/ros-distro.sh"
    [ -n "${ROS_SETUP:-}" ] && . "$ROS_SETUP" >/dev/null 2>&1
fi

echo "=== 1. nodes matching battery or dock ==="
timeout 5 ros2 node list 2>/dev/null | grep -iE "battery|dock" || echo "(none)"

echo "=== 2. does /cmd_vel (and /cmd_vel_smoothed) have a Twist publisher? ==="
for t in /cmd_vel /cmd_vel_smoothed /cmd_vel_nav; do
  timeout 5 ros2 topic info -v "$t" 2>/dev/null | grep -E "Topic name|Type:|Publisher count|QoS|covered" | head -4 | sed "s/^/   ${t}: /"
done

echo "=== 3. every battery-related node's drain_rate/low_threshold/charge_rate ==="
for n in $(timeout 5 ros2 node list 2>/dev/null | grep -iE "battery"); do
  echo "  -- node $n --"
  for p in drain_rate charge_rate low_threshold charge_target speed_threshold battery.drain_rate battery.charge_rate; do
    v=$(timeout 4 ros2 param get "$n" "$p" 2>&1 | grep -oE "value: .*" | head -1)
    [ -n "$v" ] && echo "     $p = $v"
  done
done

echo "=== 4. /odom twist linear speed (is the robot genuinely moving now?) ==="
timeout 5 ros2 topic echo /odom --once 2>/dev/null | grep -A1 "linear:" | grep "x:" | head -1
