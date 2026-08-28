#!/usr/bin/env bash
# =============================================================================
# env.sh - House Cleaner Workspace Environment Setup
# =============================================================================
# This script sets up the ROS2 Jazzy environment for the house_cleaner_ws.
# Source this file in every new terminal before running ROS2 commands:
#
#   source <workspace>/env.sh
#
# What it does:
#   1. Sources ROS2 Jazzy base environment
#   2. Sets TurtleBot3 model to Burger
#   3. Sets ROS_DOMAIN_ID for isolation
#   4. Sources workspace install overlay (if built)
# =============================================================================

# Determine workspace root dynamically (works regardless of where script is called from)
_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source ROS2 Jazzy base environment
# This provides: ros2, colcon, and all base ROS2 packages
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
else
    echo "ERROR: ROS2 Jazzy not found at /opt/ros/jazzy/"
    echo "Please install ROS2 Jazzy first: https://docs.ros.org/en/jazzy/Installation.html"
    return 1 2>/dev/null || exit 1
fi

# Robot model configuration
# TurtleBot3 Burger is the target robot for this project
export TURTLEBOT3_MODEL=burger

# ROS Domain ID isolates this robot's communication from others on the network
# Change this if running multiple robots on the same network
export ROS_DOMAIN_ID=30

# Source workspace install overlay if it exists
# This allows 'ros2 launch' to find our packages
_INSTALL_DIR="${_WS_DIR}/install"
if [ -d "${_INSTALL_DIR}/house_cleaner_bringup" ]; then
    source "${_INSTALL_DIR}/setup.bash"
    echo "house_cleaner_ws environment loaded"
    echo "  Workspace: ${_WS_DIR}"
    echo "  Robot: TurtleBot3 Burger"
    echo "  Domain ID: ${ROS_DOMAIN_ID}"
else
    echo "WARNING: Workspace not built yet. Run 'colcon build' first in ${_WS_DIR}"
    echo "  Workspace: ${_WS_DIR}"
fi
