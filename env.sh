#!/usr/bin/env bash
# house_cleaner_ws — canonical environment
#
# ENVIRONMENT: ROS2 (Jazzy or Lyrical)
# WHY THIS EXISTS: colcon on some hosts is old (<1.5): it writes hook-style
# package.dsv files instead of the modern local_setup.* chain, so the
# ament_prefix_path hook is never invoked and package prefixes never enter
# AMENT_PREFIX_PATH. This file sets the prefix path explicitly in the
# verified order (workspace packages first, ROS base last).
#
# Usage:
#   source <workspace>/env.sh

# Save current mode, switch to permissive for sourcing
set +o pipefail
set +o errexit

# Determine workspace root dynamically (works regardless of absolute path)
_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INSTALL_DIR="${_WS_DIR}/install"

# Source ROS2 Environment (Jazzy preferred; fall back to Lyrical if available)
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f /opt/ros/lyrical/setup.bash ]; then
    source /opt/ros/lyrical/setup.bash
else
    echo "Error: Neither jazzy nor lyrical found in /opt/ros/"
    return 1 2>/dev/null || exit 1
fi

export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30

# Explicit AMENT_PREFIX_PATH (required for old colcon hook behavior)
# Prioritize workspace packages over system ROS packages
if [ -d "${_INSTALL_DIR}/house_cleaner_bringup" ]; then
    export AMENT_PREFIX_PATH="${_INSTALL_DIR}/house_cleaner_bringup:${_INSTALL_DIR}:${AMENT_PREFIX_PATH}"
else
    echo "Warning: workspace not built. Run 'colcon build' first in ${_WS_DIR}"
fi

# Also export package path
if [ -d "${_INSTALL_DIR}/share" ]; then
    export ROS_PACKAGE_PATH="${_INSTALL_DIR}/share:${ROS_PACKAGE_PATH}"
fi

echo "house_cleaner_ws environment loaded (workspace: ${_WS_DIR})"