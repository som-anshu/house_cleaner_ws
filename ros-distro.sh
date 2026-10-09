#!/usr/bin/env bash
# =============================================================================
# ros-distro.sh - portable ROS 2 distro and layout detection
# =============================================================================
# The single source of truth for "which ROS 2 distro and where are things".
# Source this from every script in this repo instead of hardcoding distro
# names or absolute paths:
#
#     source "$(dirname "$0")/ros-distro.sh"
#
# It works both on the host and inside a container, and never hardcodes a
# distro, a username or an install path.
#
# Exports:
#   ROS_DISTRO        lyrical | jazzy | iron | humble | ...
#   ROS_ROOT          /opt/ros/<distro>
#   ROS_SETUP         path to setup.bash for the distro
#   ROS_DISTRO_SORT   candidates found on this machine, in preference order
#
# Also sets these convenience vars when they are not already set:
#   WS_DIR            repository root (the directory containing this script)
#   CONTAINER_NAME    house_cleaner_<distro>
#   IMAGE_NAME        house_cleaner:<distro>
#   ROS_DOMAIN_ID     30 unless already set
#   TURTLEBOT3_MODEL  burger unless already set
# =============================================================================

# Resolve the repo root from this file's own location, so it does not matter
# where it is sourced from or what the workspace directory is called.
_ROS_DISTRO_SH_PATH="${BASH_SOURCE[0]}"
WS_DIR="${WS_DIR:-$(cd "$(dirname "$_ROS_DISTRO_SH_PATH")" && pwd)}"

# --- Pick a distro ----------------------------------------------------------
# An explicit ROS_DISTRO is authoritative: inside a container it is set by the
# image and always correct, and a user who exports it wants it honoured. Only
# auto-detect when it is unset or empty.
if [ -n "${ROS_DISTRO:-}" ]; then
    if [ ! -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
        echo "WARNING: ROS_DISTRO=${ROS_DISTRO} is set but /opt/ros/${ROS_DISTRO} does not exist." >&2
    fi
else
    # Preference order: LTS distros newest first, then anything else that
    # happens to be installed. Lyrical pairs with Ubuntu 26.04, Jazzy with
    # 24.04, Humble with 22.04. Adding a distro here is the only edit needed
    # when a new one appears.
    _rd_candidates="lyrical jazzy humble"
    for _rd in $(ls -1 /opt/ros 2>/dev/null); do
        case " ${_rd_candidates} " in *" ${_rd} "*) ;; *) _rd_candidates="${_rd_candidates} ${_rd}" ;; esac
    done

    ROS_DISTRO=""
    for _rd in ${_rd_candidates}; do
        if [ -f "/opt/ros/${_rd}/setup.bash" ]; then
            ROS_DISTRO="${_rd}"
            break
        fi
    done

    # Nothing installed: fall back to the best guess for this OS so that error
    # messages and documentation can still name the right distro.
    if [ -z "$ROS_DISTRO" ]; then
        OS_CODENAME="$(. /etc/os-release 2>/dev/null; echo "${VERSION_CODENAME:-unknown}")"
        case "$OS_CODENAME" in
            resolute)                          ROS_DISTRO="lyrical" ;;
            noble|plucky|questing|oracular)    ROS_DISTRO="jazzy"   ;;
            jammy)                             ROS_DISTRO="humble" ;;
            *)                                 ROS_DISTRO="lyrical" ;;
        esac
        echo "WARNING: no ROS 2 installation found under /opt/ros." >&2
        echo "         Ubuntu codename: ${OS_CODENAME}. Assuming '${ROS_DISTRO}'." >&2
        echo "         Install it from https://docs.ros.org/en/${ROS_DISTRO}/Installation.html" >&2
    fi
fi

export ROS_DISTRO
ROS_ROOT="/opt/ros/${ROS_DISTRO}"
ROS_SETUP="${ROS_ROOT}/setup.bash"
export ROS_ROOT

# --- Convenience defaults ---------------------------------------------------
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-burger}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"

CONTAINER_NAME="${CONTAINER_NAME:-house_cleaner_${ROS_DISTRO}}"
IMAGE_NAME="${IMAGE_NAME:-house_cleaner:${ROS_DISTRO}}"
