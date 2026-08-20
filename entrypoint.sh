#!/usr/bin/env bash
# House cleaner Docker entrypoint.
# Always launches the Gazebo GUI (headless:=false) AND the battery monitor,
# so the robot is visible and its charge is tracked together.
#
# Usage:
#   ./run_docker.sh                           # default: GUI + default params
#   ./run_docker.sh --battery_drain_rate 0.3  # custom battery drain
#   ./run_docker.sh mission_strip_width:=0.4  # tighter coverage spacing
#
# Additional launch args: pass any ROS2 launch argument after --

set -e
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

# Build launch command with all arguments passed to this script
LAUNCH_ARGS="headless:=false"

# Convert Docker args to ROS2 launch args
# e.g., --battery_drain_rate 0.3 -> battery_drain_rate:=0.3
while [[ $# -gt 0 ]]; do
    case "$1" in
        --*)
            # Handle --param value or --param:=value format
            arg="${1#--}"
            if [[ "$arg" == *":="* ]]; then
                # Already has := format, use as-is
                LAUNCH_ARGS="$LAUNCH_ARGS $arg"
            elif [[ -n "$2" && "$2" != --* ]]; then
                # --param value format
                LAUNCH_ARGS="$LAUNCH_ARGS ${arg}:=$2"
                shift 2
                continue
            else
                # Just --param (keep as-is, will use default)
                LAUNCH_ARGS="$LAUNCH_ARGS $arg"
            fi
            ;;
        *)
            # Pass through any other arguments
            LAUNCH_ARGS="$LAUNCH_ARGS $1"
            ;;
    esac
    shift
done

echo "=== Launching house cleaner with args: $LAUNCH_ARGS ==="

# Launch the full sim with the Gazebo GUI in the background...
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py $LAUNCH_ARGS &
SIM_PID=$!

# ...and run the battery monitor in the foreground so `docker logs` shows it.
# Run from the source tree: the script is not installed into the image.
python3 /workspace/src/house_cleaner_bringup/scripts/battery_monitor.py &
MON_PID=$!

trap 'kill $SIM_PID $MON_PID 2>/dev/null' EXIT
wait -n $SIM_PID $MON_PID