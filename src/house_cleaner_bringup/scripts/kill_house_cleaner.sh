#!/usr/bin/env bash
# Kill every stale house-cleaner sim process before a fresh launch.
#
# Patterns are deliberately specific so this script's own command line
# (scripts/kill_house_cleaner.sh) is never matched — a broad "house_cleaner"
# pattern would pkill this very shell.

set +e

pkill -f "gz sim" 2>/dev/null
pkill -f "ros2 launch house_cleaner_bringup" 2>/dev/null
pkill -f "house_cleaner_assistant" 2>/dev/null
pkill -f "fake_sim" 2>/dev/null
pkill -f "async_slam_toolbox_node" 2>/dev/null
pkill -f "rviz2" 2>/dev/null

sleep 1
echo "Cleaned stale house-cleaner instances."