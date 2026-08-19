#!/usr/bin/env bash
# house_cleaner_ws — canonical environment
#
# ENVIRONMENT: ROS2 Lyrical (humble-based build)
# WHY THIS EXISTS: colcon on this host is old (<1.5): it writes hook-style package.dsv files
# (listing hook/*.sh directly) instead of the modern local_setup.* chain, so
# the ament_prefix_path hook is never invoked and package prefixes never enter
# AMENT_PREFIX_PATH. Result: `ros2 launch house_cleaner_bringup ...` and
# `ros2 run house_cleaner_bringup ...` fail with "package not found" even
# after sourcing install/setup.bash. This file sets the prefix path explicitly
# in the verified order (workspace packages first, Lyrical base last).
#
# Usage:
#   source /home/koko/house_cleaner_ws/env.sh

# Save current mode, switch to permissive for sourcing
set +o pipefail
set +o errexit

# Source ROS2 Environment (lyrical instead of jazzy)
if [ -f /opt/ros/lyrical/setup.bash ]; then
    source /opt/ros/lyrical/setup.bash
else
    echo "Warning: ROS2 lyrical not found at /opt/ros/lyrical/"
    echo "Falling back to jazzy..."
    source /opt/ros/jazzy/setup.bash 2>/dev/null || {
        echo "Error: Neither lyrical nor jazzy found"
        return 1 2>/dev/null || exit 1
    }
fi

export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30

# Explicit AMENT_PREFIX_PATH (required for old colcon hook behavior)
export AMENT_PREFIX_PATH="/home/koko/house_cleaner_ws/install/house_cleaner_bringup:/home/koko/house_cleaner_ws/install:/opt/ros/lyrical${AMENT_PREFIX_PATH:+:$AMENT_PREFIX_PATH}"

# Also export for child processes
export ROS_PACKAGE_PATH="/home/koko/house_cleaner_ws/install/share:/opt/ros/lyrical/share${ROS_PACKAGE_PATH:+:$ROS_PACKAGE_PATH}"

echo "house_cleaner_ws environment loaded (ROS2 Lyrical)"