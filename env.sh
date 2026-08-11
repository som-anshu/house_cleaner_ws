#!/usr/bin/env bash
# house_cleaner_ws — canonical environment
#
# WHY THIS EXISTS:
# colcon on this host is old (<1.5): it writes hook-style package.dsv files
# (listing hook/*.sh directly) instead of the modern local_setup.* chain, so
# the ament_prefix_path hook is never invoked and package prefixes never enter
# AMENT_PREFIX_PATH. Result: `ros2 launch house_cleaner_bringup ...` and
# `ros2 run house_cleaner_bringup ...` fail with "package not found" even
# after sourcing install/setup.bash. This file sets the prefix path explicitly
# in the verified order (workspace packages first, Jazzy base last).
#
# Usage:
#   source /home/koko/house_cleaner_ws/env.sh
set +u
source /opt/ros/jazzy/setup.bash
set -u

export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
export AMENT_PREFIX_PATH="\
/home/koko/house_cleaner_ws/install/house_cleaner_bringup:\
/home/koko/house_cleaner_ws/install:\
/opt/ros/jazzy"
