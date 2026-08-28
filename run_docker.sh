#!/usr/bin/env bash
# =============================================================================
# run_docker.sh - House Cleaner Robot Docker Launcher
# =============================================================================
# This script launches the house cleaner robot simulation in Docker with GUI
# support. It handles X11 forwarding, builds the image if needed, and cleans
# up any previous instances.
#
# Usage:
#   ./run_docker.sh              # Run with GUI (default)
#   ./run_docker.sh --build      # Force rebuild the Docker image
#   ./run_docker.sh --headless   # Run without GUI (server only)
#
# Prerequisites:
#   1. Docker installed and running
#   2. X11 server running on host (for GUI mode)
#   3. Run 'xhost +local:docker' before first run
#
# What it does:
#   1. Checks for Docker and X11
#   2. Cleans up any previous house_cleaner instances
#   3. Builds the Docker image if it doesn't exist
#   4. Launches the container with proper GUI forwarding
# =============================================================================

set -e

# Determine script directory (works regardless of where script is called from)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# Docker Detection
# =============================================================================
# Check if Docker is available, try sudo if needed
DOCKER="docker"
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo -n docker"
fi
if ! $DOCKER info >/dev/null 2>&1; then
    DOCKER="sudo docker"
fi

echo "=== House Cleaner Robot - Docker Launcher ==="
echo "Workspace: $DIR"

# =============================================================================
# X11 Setup (for GUI mode)
# =============================================================================
# Check if we're in headless mode
HEADLESS=false
if [ "$1" = "--headless" ]; then
    HEADLESS=true
    echo "Running in headless mode (no GUI)"
else
    # GUI mode: Check for X11 and set up forwarding
    if [ -z "$DISPLAY" ]; then
        echo "WARNING: DISPLAY environment variable not set"
        echo "  For GUI mode, ensure X11 server is running"
        echo "  For headless mode, use: ./run_docker.sh --headless"
    else
        echo "Display: $DISPLAY"
        # Grant Docker access to X11 (required for GUI forwarding)
        xhost +local:docker 2>/dev/null || true
    fi
fi

# =============================================================================
# Cleanup Previous Instances
# =============================================================================
echo "Cleaning up previous instances..."

# Kill host-side ROS2/Gazebo/RViz processes (native sim leftovers)
pkill -f "gz sim" 2>/dev/null || true
pkill -f "ros2 launch house_cleaner_bringup" 2>/dev/null || true
pkill -f "house_cleaner_assistant" 2>/dev/null || true
pkill -f "fake_sim" 2>/dev/null || true
pkill -f "async_slam_toolbox_node" 2>/dev/null || true
pkill -f "rviz2" 2>/dev/null || true

# Remove previous Docker container
$DOCKER rm -f house_cleaner_jazzy 2>/dev/null || true

sleep 1

# =============================================================================
# Build Docker Image (if needed)
# =============================================================================
# Force rebuild if --build flag is passed
if [ "$1" = "--build" ]; then
    echo "Building Docker image..."
    $DOCKER build -t house_cleaner:jazzy "$DIR"
fi

# Build if image doesn't exist
if ! $DOCKER image inspect house_cleaner:jazzy >/dev/null 2>&1; then
    echo "Docker image not found. Building..."
    $DOCKER build -t house_cleaner:jazzy "$DIR"
fi

# =============================================================================
# Launch Container
# =============================================================================
echo "Starting house cleaner simulation..."

# Build Docker run command
DOCKER_CMD="$DOCKER run -d --rm --name house_cleaner_jazzy"

# Add GUI forwarding if not headless
if [ "$HEADLESS" = false ]; then
    DOCKER_CMD="$DOCKER_CMD \
        -e DISPLAY=$DISPLAY \
        -e LIBGL_ALWAYS_SOFTWARE=1 \
        -e MESA_GL_VERSION_OVERRIDE=3.3 \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw"
fi

# Add shared memory for Gazebo
DOCKER_CMD="$DOCKER_CMD -v /dev/shm:/dev/shm"

# Add workspace volume mount
DOCKER_CMD="$DOCKER_CMD -v $DIR:/workspace"

# Add Foxglove port mapping
DOCKER_CMD="$DOCKER_CMD -p 8765:8765"

# Add robot configuration
DOCKER_CMD="$DOCKER_CMD \
    -e TURTLEBOT3_MODEL=burger \
    -e ROS_DOMAIN_ID=30"

# Add image name
DOCKER_CMD="$DOCKER_CMD house_cleaner:jazzy"

# Execute the command
$DOCKER_CMD

# =============================================================================
# Status Output
# =============================================================================
echo ""
echo "=== Container Started ==="
echo "Container name: house_cleaner_jazzy"
echo ""
echo "Useful commands:"
echo "  View logs:     docker logs -f house_cleaner_jazzy"
echo "  Enter shell:   docker exec -it house_cleaner_jazzy bash"
echo "  Stop:          docker stop house_cleaner_jazzy"
echo ""
if [ "$HEADLESS" = false ]; then
    echo "GUI Access:"
    echo "  Gazebo: Should open automatically"
    echo "  RViz2:  docker exec house_cleaner_jazzy rviz2"
    echo ""
    echo "Foxglove Access:"
    echo "  Open browser to: http://localhost:8765"
    echo "  Or use Foxglove app: ws://localhost:8765"
fi
echo ""
echo "Teleop Control (in another terminal):"
echo "  docker exec -it house_cleaner_jazzy ros2 run teleop_twist_keyboard teleop_twist_keyboard"
