#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh - Entrypoint for the House Cleaner Robot container
# =============================================================================
# Sources the ROS distro + workspace overlay and launches
# house_cleaning.launch.py.
#
# Usage:
#   docker run house_cleaner:lyrical                       # Full stack, GUI
#   docker run house_cleaner:lyrical --headless            # Gazebo server-only
#   docker run house_cleaner:lyrical --launch <pkg> <file> # Custom launch file
#   docker run house_cleaner:lyrical bash                  # Interactive shell
#
# The distro comes from the image's ROS_DISTRO environment variable, so this
# file is identical for lyrical, jazzy and humble images.
#
# NOTE: `set -u` is deliberately NOT used. setup.bash dereferences some
# AMENT_TRACE_* variables that are legitimately unset, and with set -u the
# whole entrypoint aborts before ROS is even sourced.
# =============================================================================

set -e

# The image sets ROS_DISTRO (see Dockerfile ENV). Fall back to the single
# installed distro if it is somehow unset.
if [ -z "${ROS_DISTRO:-}" ]; then
    ROS_DISTRO="$(set -- /opt/ros/*/setup.bash; [ -f "${1:-}" ] && basename "$(dirname "$1")" || echo "")"
    if [ -z "$ROS_DISTRO" ]; then
        echo "ERROR: no ROS distro found under /opt/ros and ROS_DISTRO is unset" >&2
        exit 2
    fi
fi
echo "ROS distro: ${ROS_DISTRO}"

# Order matters: /opt/ros first, then the workspace overlay, so the overlay's
# packages resolve ahead of the distro ones.
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [ -f /workspace/install/setup.bash ]; then
    source /workspace/install/setup.bash
fi

# Parse arguments once. `--launch PKG FILE...` must consume PKG/FILE from the
# same stream the while-loop walks - shifting inside a case while a for-loop
# still visited the original argv used to double-shift and also append PKG
# into LAUNCH_ARGS (`ros2 launch pkg pkg file`).
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
echo "ROS 2 ${ROS_DISTRO} environment loaded"
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
