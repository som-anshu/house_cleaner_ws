#!/usr/bin/env bash
# One-shot launcher: kills every previous house-cleaner instance (host AND
# container) then starts a fresh sim WITH GUI.
#
# Usage:
#   ./run_docker.sh            # build if needed, then run with GUI
#   ./run_docker.sh --build    # force rebuild
#
# Prerequisites:
#   - X11 running on host display
#   - xhost permission: xhost +local:docker
#   - GPU with OpenGL OR software rendering fallback (LIBGL_ALWAYS_SOFTWARE=1)
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

echo "=== Starting fresh sim WITH GUI ==="
cd "$DIR"

# Build if needed
if [ "$1" = "--build" ]; then
    $DOCKER build -t house_cleaner:jazzy .
fi

if ! $DOCKER image inspect house_cleaner:jazzy >/dev/null 2>&1; then
    $DOCKER build -t house_cleaner:jazzy .
fi

# Run with GUI mode.
#
# Rendering strategy:
#   - LIBGL_ALWAYS_SOFTWARE=1 forces Mesa software rendering (llvmpipe),
#     which works in any environment with X11 but no host GPU drivers.
#   - MESA_GL_VERSION_OVERRIDE=3.3 ensures compatibility with Gazebo's
#     OpenGL 3.3 requirement when running on llvmpipe.
#   - --device /dev/dri is omitted because on hosts with NVIDIA GPUs,
#     passing the device causes an EGL conflict: the container detects
#     the NVIDIA PCI ID but has no nvidia driver, leading to a segfault
#     in gz-sim's render thread. Software rendering alone via Mesa is
#     more reliable for containerized Gazebo.
#   - If you have a working GPU passthrough (e.g. NVIDIA Container Toolkit),
#     you can add --gpus all and remove LIBGL_ALWAYS_SOFTWARE=1.
$DOCKER run -d --rm \
    --name house_cleaner_jazzy \
    -e TURTLEBOT3_MODEL=burger \
    -e ROS_DOMAIN_ID=30 \
    -e DISPLAY=$DISPLAY \
    -e LIBGL_ALWAYS_SOFTWARE=1 \
    -e MESA_GL_VERSION_OVERRIDE=3.3 \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v /dev/shm:/dev/shm \
    -v "$DIR:/workspace" \
    house_cleaner:jazzy

echo "=== Container started in detached mode ==="
echo "Check logs with: docker logs -f house_cleaner_jazzy"
