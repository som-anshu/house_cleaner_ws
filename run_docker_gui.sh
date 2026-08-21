#!/usr/bin/env bash
# One-shot launcher for GUI mode: kills every previous house-cleaner instance 
# then starts a fresh sim WITH GAZEBO GUI.
#
# Usage:
#   ./run_docker_gui.sh            # build if needed, then run with GUI
#   ./run_docker_gui.sh --build    # force rebuild
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

echo "=== Setting up X11 access for GUI mode ==="
xhost +local:docker 2>/dev/null || true

echo "=== Killing previous house-cleaner instances ==="
pkill -f "gz sim" 2>/dev/null || true
pkill -f "ros2 launch house_cleaner_bringup" 2>/dev/null || true
pkill -f "house_cleaner_assistant" 2>/dev/null || true
pkill -f "fake_sim" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "rviz2" 2>/dev/null || true
$DOCKER rm -f house_cleaner_jazzy 2>/dev/null || true

sleep 1

echo "=== Starting fresh sim WITH GUI ==="
cd "$DIR"

# Use docker run directly to pass extra args to entrypoint
# Override the entrypoint to pass headless:=false
if [ "$1" = "--build" ]; then
    $DOCKER build -t house_cleaner:jazzy .
fi

# Check if we need to rebuild the image
if ! $DOCKER image inspect house_cleaner:jazzy >/dev/null 2>&1; then
    $DOCKER build -t house_cleaner:jazzy .
fi

# Run with GUI mode - use -d for detached mode (no TTY required)
# Pass headless:=false to enable Gazebo GUI
# Map workspace volume for live code updates
$DOCKER run -d --rm \
    --name house_cleaner_jazzy \
    -e TURTLEBOT3_MODEL=burger \
    -e ROS_DOMAIN_ID=30 \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v /dev/shm:/dev/shm \
    -v "$HOME/house_cleaner_ws:/workspace" \
    --device /dev/dri \
    house_cleaner:jazzy \
    headless:=false

echo "=== Container started in detached mode ==="
echo "Check logs with: docker logs -f house_cleaner_jazzy"