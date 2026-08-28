#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash
export AMENT_PREFIX_PATH=/workspace/install/house_cleaner_bringup:/workspace/install:/opt/ros/jazzy

HEADLESS=false
CUSTOM_LAUNCH=""

for arg in "$@"; do
    case $arg in
        --headless) HEADLESS=true ;;
        --launch=*) CUSTOM_LAUNCH="${arg#*=}" ;;
    esac
done

if [ -n "$CUSTOM_LAUNCH" ]; then
    exec ros2 launch "$CUSTOM_LAUNCH"
elif [ "$HEADLESS" = true ]; then
    exec ros2 launch house_cleaner_bringup house_cleaning_headless.launch.py use_sim_time:=true
else
    exec ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py use_sim_time:=true
fi
