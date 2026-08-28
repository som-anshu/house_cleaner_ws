#!/usr/bin/env bash
# =============================================================================
# run_docker.sh - Docker Launcher for House Cleaner Robot
# =============================================================================
# This script launches the house cleaner robot simulation in Docker.
# It handles Docker Desktop compatibility and GUI forwarding.
#
# Usage:
#   ./run_docker.sh              # Run with GUI
#   ./run_docker.sh --build      # Force rebuild
#   ./run_docker.sh --headless   # Run without GUI
# =============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Determine Docker command (works with Docker Desktop and native Docker)
DOCKER="docker"

# Check if container exists
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "house_cleaner_jazzy"; then
    echo "Removing previous container..."
    docker rm -f house_cleaner_jazzy 2>/dev/null || true
fi

# Kill any existing ROS2/Gazebo processes on host
pkill -f "gz sim" 2>/dev/null || true
pkill -f "ros2 launch house_cleaner_bringup" 2>/dev/null || true
pkill -f "house_cleaner_assistant" 2>/dev/null || true
pkill -f "fake_sim" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "rviz2" 2>/dev/null || true

sleep 1

# Build if needed
if [ "$1" = "--build" ]; then
    echo "Building Docker image..."
    docker build -t house_cleaner:jazzy "$DIR"
fi

if ! docker image inspect house_cleaner:jazzy >/dev/null 2>&1; then
    echo "Docker image not found. Building..."
    docker build -t house_cleaner:jazzy "$DIR"
fi

# Launch container
HEADLESS=false
if [ "$1" = "--headless" ]; then
    HEADLESS=true
    echo "Running in headless mode..."
    docker run -d --rm --name house_cleaner_jazzy \
        -e TURTLEBOT3_MODEL=burger \
        -e ROS_DOMAIN_ID=30 \
        -v /dev/shm:/dev/shm \
        -v "$DIR:/workspace" \
        -p 8765:8765 \
        house_cleaner:jazzy --headless
else
    echo "Running with GUI..."
    # Set up X11 (may fail on Docker Desktop - that's OK)
    xhost +local:docker 2>/dev/null || true
    
    docker run -d --rm --name house_cleaner_jazzy \
        -e TURTLEBOT3_MODEL=burger \
        -e ROS_DOMAIN_ID=30 \
        -e LIBGL_ALWAYS_SOFTWARE=1 \
        -e MESA_GL_VERSION_OVERRIDE=3.3 \
        -v /dev/shm:/dev/shm \
        -v "$DIR:/workspace" \
        -p 8765:8765 \
        house_cleaner:jazzy
fi

echo "Container started!"
echo "  Logs: docker logs -f house_cleaner_jazzy"
echo "  foxglove: http://localhost:8765"