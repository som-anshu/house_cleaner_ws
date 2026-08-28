#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh - House Cleaner Robot Docker Entrypoint
# =============================================================================
# This script is the main entry point for the Docker container.
# It launches the complete house cleaner robot simulation stack:
#
#   1. Gazebo Harmonic (physics simulation with house_room.world)
#   2. SLAM Toolbox (real-time mapping from laser scan)
#   3. Nav2 (autonomous navigation stack)
#   4. House Cleaner Assistant (cleaning + battery + docking)
#   5. Foxglove Bridge (web visualization on port 8765)
#   6. RViz2 (optional local visualization)
#
# Usage:
#   docker run house_cleaner:jazzy                    # Full stack with GUI
#   docker run house_cleaner:jazzy --headless         # No GUI (server only)
#   docker run house_cleaner:jazzy --no-rviz          # Skip RViz2 launch
#   docker run house_cleaner:jazzy --launch <file>    # Custom launch file
#
# Environment Variables:
#   TURTLEBOT3_MODEL=burger    Robot model (default: burger)
#   ROS_DOMAIN_ID=30           ROS2 domain ID for isolation
#   DISPLAY                    X11 display for GUI (set automatically)
# =============================================================================

set -e

# Source ROS2 and workspace environments
source /opt/ros/jazzy/setup.bash
source /workspace/install/setup.bash

echo "=== House Cleaner Robot - Starting ==="
echo "ROS2 Jazzy environment loaded"
echo "Robot model: $TURTLEBOT3_MODEL"
echo "Domain ID: $ROS_DOMAIN_ID"

# =============================================================================
# Parse Command Line Arguments
# =============================================================================
HEADLESS=false
NO_RVIZ=false
CUSTOM_LAUNCH=""

for arg in "$@"; do
    case $arg in
        --headless)
            HEADLESS=true
            echo "Running in headless mode (no GUI)"
            ;;
        --no-rviz)
            NO_RVIZ=true
            echo "Skipping RViz2 launch"
            ;;
        --launch=*)
            CUSTOM_LAUNCH="${arg#*=}"
            echo "Using custom launch file: $CUSTOM_LAUNCH"
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: entrypoint.sh [--headless] [--no-rviz] [--launch=<file>]"
            exit 1
            ;;
    esac
done

# =============================================================================
# Launch Foxglove Bridge (Web Visualization)
# =============================================================================
# Start Foxglove bridge in background for web-based visualization
echo "Starting Foxglove bridge on port 8765..."
ros2 run foxglove_bridge foxglove_bridge \
    --ros-args \
    -p port:=8765 \
    -p address:=0.0.0.0 \
    -p num_threads:=2 \
    -p max_qos_depth:=10 &
FOXGLOVE_PID=$!
sleep 2

# Check if Foxglove bridge started successfully
if kill -0 $FOXGLOVE_PID 2>/dev/null; then
    echo "Foxglove bridge started (PID: $FOXGLOVE_PID)"
    echo "  Access at: http://localhost:8765"
else
    echo "WARNING: Foxglove bridge failed to start"
fi

# =============================================================================
# Launch Main Stack
# =============================================================================
if [ -n "$CUSTOM_LAUNCH" ]; then
    # Custom launch file
    echo "Launching custom file: $CUSTOM_LAUNCH"
    ros2 launch "$CUSTOM_LAUNCH" &
elif [ "$HEADLESS" = true ]; then
    # Headless mode: Launch without Gazebo GUI
    echo "Launching in headless mode..."
    ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
        use_sim_time:=true &
else
    # Full GUI mode: Launch everything including Gazebo and RViz2
    echo "Launching full stack with GUI..."
    ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
        use_sim_time:=true &
fi

LAUNCH_PID=$!

# =============================================================================
# Launch RViz2 (Optional)
# =============================================================================
if [ "$NO_RVIZ" = false ] && [ "$HEADLESS" = false ]; then
    echo "Starting RViz2..."
    sleep 5  # Wait for other nodes to start
    ros2 run rviz2 rviz2 \
        --ros-args \
        -d /workspace/src/house_cleaner_bringup/config/nav2_params.yaml &
    RVIZ_PID=$!
    echo "RViz2 started (PID: $RVIZ_PID)"
fi

# =============================================================================
# Monitor and Wait
# =============================================================================
echo ""
echo "=== House Cleaner Robot - Running ==="
echo "Main launch PID: $LAUNCH_PID"
echo ""
echo "Useful commands (in another terminal):"
echo "  docker exec -it house_cleaner_jazzy bash"
echo "  docker exec house_cleaner_jazzy ros2 topic list"
echo "  docker exec house_cleaner_jazzy ros2 node list"
echo ""
echo "Press Ctrl+C to stop..."

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $LAUNCH_PID 2>/dev/null || true
    kill $FOXGLOVE_PID 2>/dev/null || true
    kill $RVIZ_PID 2>/dev/null || true
    echo "Stopped."
    exit 0
}

# Trap signals for cleanup
trap cleanup SIGINT SIGTERM

# Wait for launch to complete
wait $LAUNCH_PID
