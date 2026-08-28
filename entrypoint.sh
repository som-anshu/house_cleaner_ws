#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh - Docker Entrypoint for House Cleaner Robot
# =============================================================================
# This script starts the complete house cleaner robot simulation.
# It launches the Gazebo simulation, SLAM, Nav2, and cleaning assistant.
#
# Usage:
#   docker run house_cleaner:jazzy                    # Full stack
#   docker run house_cleaner:jazzy --headless         # No GUI
#   docker run house_cleaner:jazzy --launch <file>    # Custom launch file
# =============================================================================

set -e

# Source ROS2 and workspace
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

# Parse arguments
HEADLESS=false
CUSTOM_LAUNCH=""

# Check for --headless flag
if [[ "$*" == *"--headless"* ]]; then
    HEADLESS=true
fi

# Check for custom launch file
if [[ "$*" == *"--launch="* ]]; then
    CUSTOM_LAUNCH=$(echo "$*" | sed -n 's/.*--launch=\([^ ]*\).*/\1/p')
fi

echo "=== House Cleaner Robot ==="
echo "ROS2 Jazzy environment loaded"
echo "Robot model: ${TURTLEBOT3_MODEL:-burger}"
echo "Domain ID: ${ROS_DOMAIN_ID:-30}"

# Launch the main stack
if [ -n "$CUSTOM_LAUNCH" ]; then
    echo "Launching custom file: $CUSTOM_LAUNCH"
    exec ros2 launch "$CUSTOM_LAUNCH"
elif [ "$HEADLESS" = true ]; then
    echo "Launching in headless mode..."
    exec ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py use_sim_time:=true
else
    echo "Launching full stack..."
    exec ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py use_sim_time:=true
fi