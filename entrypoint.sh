#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh - Entrypoint for House Cleaner Robot Docker Container
# =============================================================================
# This script starts the complete house cleaner robot simulation.
#
# Usage:
#   docker run house_cleaner:jazzy                    # Full stack with GUI
#   docker run house_cleaner:jazzy --headless         # No GUI
#   docker run house_cleaner:jazzy --launch <file>    # Custom launch file
# =============================================================================

set -e

# Source ROS2 Jazzy base
source /opt/ros/jazzy/setup.bash

# Source workspace install if it exists
if [ -f /workspace/install/setup.bash ]; then
    source /workspace/install/setup.bash
fi

# Ensure workspace install is in AMENT_PREFIX_PATH
if [[ ":$AMENT_PREFIX_PATH:" != *":/workspace/install:"* ]]; then
    export AMENT_PREFIX_PATH="/workspace/install:${AMENT_PREFIX_PATH}"
fi
if [[ ":$AMENT_PREFIX_PATH:" != *":/workspace/install/house_cleaner_bringup:"* ]]; then
    export AMENT_PREFIX_PATH="/workspace/install/house_cleaner_bringup:${AMENT_PREFIX_PATH}"
fi

# Parse arguments
HEADLESS=false
CUSTOM_LAUNCH=""

for arg in "$@"; do
    case $arg in
        --headless)
            HEADLESS=true
            ;;
        --launch=*)
            CUSTOM_LAUNCH="${arg#*=}"
            ;;
    esac
done

echo "=== House Cleaner Robot ==="
echo "ROS2 Jazzy environment loaded"
echo "Robot model: ${TURTLEBOT3_MODEL:-burger}"
echo "Domain ID: ${ROS_DOMAIN_ID:-30}"
echo "Headless: $HEADLESS"

# Launch the appropriate stack
if [ -n "$CUSTOM_LAUNCH" ]; then
    echo "Launching custom file: $CUSTOM_LAUNCH"
    exec ros2 launch "$CUSTOM_LAUNCH"
elif [ "$HEADLESS" = true ]; then
    echo "Launching in headless mode (no Gazebo GUI)..."
    # Use headless gazebo launch + Nav2 + assistant + foxglove
    exec ros2 launch house_cleaner_bringup house_cleaning_headless.launch.py use_sim_time:=true
else
    echo "Launching full stack with GUI..."
    exec ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py use_sim_time:=true
fi