#!/usr/bin/env bash
# Run house cleaner simulation for Lyrical branch
# Uses direct Python execution (no colcon build required)
#
# Usage:
#   ./run_house_cleaner.sh           # Lyrical or Jazzy, whichever is installed
#   ./run_house_cleaner.sh jazzy     # Force Jazzy
#   ./run_house_cleaner.sh lyrical   # Force Lyrical

set +e

# Determine workspace root dynamically (this file lives at repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$SCRIPT_DIR"
SRC_DIR="$WS_DIR/src/house_cleaner_bringup/house_cleaner_bringup"

echo "=== House Cleaner - Direct Run (Lyrical/Jazzy) ==="
echo "Workspace: $WS_DIR"

# Source ROS2 Environment
ROS_OVERRIDE="${1:-}"
if [ "$ROS_OVERRIDE" = "lyrical" ] || { [ -z "$ROS_OVERRIDE" ] && [ -f /opt/ros/lyrical/setup.bash ]; }; then
    source /opt/ros/lyrical/setup.bash 2>/dev/null
elif [ "$ROS_OVERRIDE" = "jazzy" ] || { [ -z "$ROS_OVERRIDE" ] && [ -f /opt/ros/jazzy/setup.bash ]; }; then
    source /opt/ros/jazzy/setup.bash 2>/dev/null
else
    echo "Error: No ROS2 installation found"
    echo "Tried: /opt/ros/lyrical/setup.bash and /opt/ros/jazzy/setup.bash"
    exit 1
fi

# Source workspace environment if it exists
if [ -f "$WS_DIR/env.sh" ]; then
    source "$WS_DIR/env.sh" 2>/dev/null || true
fi

export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30

echo ""
echo "=== Running Full Cleaning Simulation ==="

# Kill any existing processes
pkill -f "fake_sim_lyrical" 2>/dev/null || true
pkill -f "house_cleaner_assistant_lyrical" 2>/dev/null || true
pkill -f "fake_sim" 2>/dev/null || true
pkill -f "house_cleaner_assistant" 2>/dev/null || true

sleep 1

# Run fake_sim in background (separate process to isolate rclpy context)
echo "Starting fake_sim (odom, scan, TF)..."
nohup python3 "$SRC_DIR/fake_sim_lyrical_standalone.py" > /tmp/fake_sim.log 2>&1 &
FAKE_SIM_PID=$!

sleep 1

# Run assistant in background (separate process to isolate rclpy context)
echo "Starting assistant (cleaning, battery, navigation)..."
nohup python3 "$SRC_DIR/house_cleaner_assistant_lyrical.py" > /tmp/assistant.log 2>&1 &
ASSISTANT_PID=$!

sleep 2

echo ""
echo "=== Running ==="
echo "fake_sim PID: $FAKE_SIM_PID"
echo "assistant PID: $ASSISTANT_PID"
echo ""
echo "Topics published:"
echo "  /odom          - Robot odometry"
echo "  /scan          - 360 Laser scan"
echo "  /cmd_vel      - Velocity control (to robot)"
echo "  /battery_state - Battery percentage"
echo ""
echo "Verify with:"
echo "  ros2 topic echo /odom --once"
echo "  ros2 topic echo /scan --once"
echo "  ros2 topic echo /battery_state --once"
echo ""
echo "Log files: /tmp/fake_sim.log, /tmp/assistant.log"
echo "Stop with: kill $FAKE_SIM_PID $ASSISTANT_PID"