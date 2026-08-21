#!/usr/bin/env bash
# Docker entrypoint for house_cleaner robot simulation.
# Launches the full stack: Gazebo (with GUI) + SLAM + Nav2 + house cleaner assistant.
#
# Usage:
#   docker run [options] house_cleaner:jazzy [extra ros2 launch args]
#
# Default ros2 launch args passed to house_cleaning_auto.launch.py.
# These can be overridden by passing args on the docker command line.
set -e
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

# Launch the full sim with the Gazebo GUI
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py "$@"
