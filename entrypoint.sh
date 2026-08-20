#!/usr/bin/env bash
# House cleaner Docker entrypoint.
# Always launches the Gazebo GUI (headless:=false) AND the battery monitor,
# so the robot is visible and its charge is tracked together.

set -e
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

# Launch the full sim with the Gazebo GUI in the background...
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py headless:=false &
SIM_PID=$!

# ...and run the battery monitor in the foreground so `docker logs` shows it.
# Run from the source tree: the script is not installed into the image.
python3 /workspace/src/house_cleaner_bringup/scripts/battery_monitor.py &
MON_PID=$!

trap 'kill $SIM_PID $MON_PID 2>/dev/null' EXIT
wait -n $SIM_PID $MON_PID