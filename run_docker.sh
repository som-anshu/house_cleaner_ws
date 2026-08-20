#!/usr/bin/env bash
# One-shot launcher: kills every previous house-cleaner instance (host AND
# container) then starts a fresh sim. This is the single entry point for the
# Docker path — run `./run_docker.sh` instead of raw `docker compose up`.
#
# Usage:
#   ./run_docker.sh            # build if needed, then run
#   ./run_docker.sh --build    # force rebuild
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# docker may need sudo until the user re-logs-in to pick up the docker group
DOCKER="docker"
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo -n docker"
fi
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

echo "=== Killing previous house-cleaner instances ==="
# Host-side ROS2/Gazebo/RViz processes (native sim leftovers)
pkill -f "gz sim" 2>/dev/null || true
pkill -f "ros2 launch house_cleaner_bringup" 2>/dev/null || true
pkill -f "house_cleaner_assistant" 2>/dev/null || true
pkill -f "fake_sim" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "rviz2" 2>/dev/null || true
# Previous docker container
$DOCKER rm -f house_cleaner_jazzy 2>/dev/null || true

sleep 1

echo "=== Starting fresh sim ==="
cd "$DIR"
if [ "$1" = "--build" ]; then
    $DOCKER compose up --build
else
    $DOCKER compose up
fi