#!/usr/bin/env bash
# =============================================================================
# env.sh - House Cleaner Workspace Environment Setup
# =============================================================================
# Source this file in every new terminal before running ROS2 commands:
#
#   source <workspace>/env.sh
#
# What it does:
#   1. Detects the ROS2 distro (lyrical on Ubuntu 26.04, jazzy on 24.04, ...)
#   2. Sources that distro's base environment
#   3. Sets the TurtleBot3 model to Burger
#   4. Sets ROS_DOMAIN_ID for isolation
#   5. Sources the workspace install overlay (if built)
#
# The distro is detected, not hardcoded, so this file works unchanged on any
# machine. Override it by exporting ROS_DISTRO before sourcing.
# =============================================================================

# Resolve the workspace root from this file's own location.
_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ros-distro.sh sets ROS_DISTRO, ROS_ROOT and ROS_SETUP.
# It is safe to source in an environment where ROS is not installed - it
# warns and picks the distro that matches the host OS.
_ROS_DISTRO_SH="${_WS_DIR}/ros-distro.sh"
if [ -f "${_ROS_DISTRO_SH}" ]; then
    # shellcheck disable=SC1090
    source "${_ROS_DISTRO_SH}"
else
    echo "ERROR: ros-distro.sh not found next to env.sh at ${_WS_DIR}" >&2
    return 1 2>/dev/null || exit 1
fi

if [ -f "${ROS_SETUP}" ]; then
    # shellcheck disable=SC1090
    source "${ROS_SETUP}"
else
    echo "ERROR: ROS2 ${ROS_DISTRO} not found at ${ROS_ROOT}/" >&2
    echo "Install it from https://docs.ros.org/en/${ROS_DISTRO}/Installation.html" >&2
    echo "(detected distro: ${ROS_DISTRO} - export ROS_DISTRO=<other> to override)" >&2
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
    # shellcheck disable=SC1090
    source "${_INSTALL_DIR}/setup.bash"
    echo "house_cleaner_ws environment loaded"
    echo "  Workspace: ${_WS_DIR}"
    echo "  Distro:    ROS 2 ${ROS_DISTRO} (${ROS_ROOT})"
    echo "  Robot:     ${TURTLEBOT3_MODEL}"
    echo "  Domain ID: ${ROS_DOMAIN_ID}"
else
    echo "WARNING: workspace not built yet. Run 'colcon build' first in ${_WS_DIR}" >&2
    echo "  Workspace: ${_WS_DIR}"
    echo "  Distro:    ROS 2 ${ROS_DISTRO} (${ROS_ROOT})"
fi
