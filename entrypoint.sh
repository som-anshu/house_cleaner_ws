#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh - Entrypoint for House Cleaner Robot Docker Container
# =============================================================================
# Sources the ROS + workspace overlay and launches the unified
# house_cleaning.launch.py.
#
# Usage:
#   docker run house_cleaner:jazzy                       # Full stack, GUI
#   docker run house_cleaner:jazzy --headless            # Gazebo server-only
#   docker run house_cleaner:jazzy --launch <pkg> <file> # Custom launch file
#   docker run house_cleaner:jazzy bash                  # Interactive shell
# =============================================================================

set -e

# Source ROS2 Jazzy base, then the workspace overlay (order matters: the
# overlay must win over /opt/ros for our packages to resolve).
source /opt/ros/jazzy/setup.bash
if [ -f /workspace/install/setup.bash ]; then
    source /workspace/install/setup.bash
fi

# Parse arguments once.  `--launch PKG FILE...` must consume PKG/FILE from
# the same stream the for-loop walks — shifting inside the case while the
# for-loop still visits the original argv used to double-shift and also
# append PKG into LAUNCH_ARGS (`ros2 launch pkg pkg file`).
ARGS=("$@")
HEADLESS=false
CUSTOM_LAUNCH=""
LAUNCH_ARGS=()
i=0
while [ $i -lt ${#ARGS[@]} ]; do
    arg="${ARGS[$i]}"
    case "$arg" in
        --headless)
            HEADLESS=true
            ;;
        --launch)
            i=$((i + 1))
            if [ $i -ge ${#ARGS[@]} ]; then
                echo "ERROR: --launch requires a package name" >&2
                exit 2
            fi
            CUSTOM_LAUNCH="${ARGS[$i]}"
            ;;
        *)
            if [ -z "$CUSTOM_LAUNCH" ] && [ "$arg" != "--headless" ]; then
                # First non-flag token with no --launch: run as a command.
                exec "$@"
            fi
            LAUNCH_ARGS+=("$arg")
            ;;
    esac
    i=$((i + 1))
done

echo "=== House Cleaner Robot ==="
echo "ROS2 Jazzy environment loaded"
echo "Robot model: ${TURTLEBOT3_MODEL:-burger}"
echo "Domain ID: ${ROS_DOMAIN_ID:-30}"
echo "Headless: $HEADLESS"

if [ -n "$CUSTOM_LAUNCH" ]; then
    echo "Launching custom: $CUSTOM_LAUNCH ${LAUNCH_ARGS[*]}"
    exec ros2 launch "$CUSTOM_LAUNCH" ${LAUNCH_ARGS[@]+"${LAUNCH_ARGS[@]}"}
fi

if [ "$HEADLESS" = true ]; then
    echo "Launching in headless mode (no Gazebo GUI)..."
    exec ros2 launch house_cleaner_bringup house_cleaning.launch.py \
        mode:=sim headless:=true use_sim_time:=true
else
    echo "Launching full stack with GUI..."
    exec ros2 launch house_cleaner_bringup house_cleaning.launch.py \
        mode:=sim headless:=false use_sim_time:=true
fi