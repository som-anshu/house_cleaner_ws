#!/usr/bin/env bash
# =============================================================================
# run_docker.sh - Docker launcher for the House Cleaner Robot
# =============================================================================
# Launches the house cleaner simulation in Docker with GUI forwarding,
# GPU acceleration when available, and a software-rendering fallback.
#
# Usage:
#   ./run_docker.sh                 # Run with GUI (X11 or Wayland)
#   ./run_docker.sh --build         # Force rebuild
#   ./run_docker.sh --headless      # Run without GUI (Foxglove still up)
#   ./run_docker.sh --shell         # Drop into an interactive bash shell
#
# Everything distro- and machine-specific is detected at run time:
#
#   * ROS distro    - lyrical / jazzy / humble, whichever is installed
#   * Docker flavour - native Linux engine vs Docker Desktop (they need
#                    completely different display forwarding)
#   * Display server - Wayland preferred, X11 fallback, headless otherwise
#   * GPU           - NVIDIA runtime if present, then /dev/dri, then software
#
# There are no hardcoded paths, usernames or distro names in this file.
# =============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -----------------------------------------------------------------------------
# Never run this as root
# -----------------------------------------------------------------------------
# `sudo bash run_docker.sh` is an easy thing to type, and it fails in a way
# that is hard to debug: HOME becomes /root, `id -u` becomes 0, so the
# Wayland/X11 mounts point at /root and /run/user/0 instead of the real user's
# display, and the docker group check is meaningless. Docker never needs sudo
# to *invoke* - only the daemon must be running, and that is handled by
# systemctl.
if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: do not run this script with sudo." >&2
    echo "" >&2
    echo "  Run it as your normal user instead:" >&2
    echo "      $0 $*" >&2
    echo "" >&2
    echo "  Docker only needs sudo to START the daemon once:" >&2
    echo "      sudo systemctl start docker" >&2
    echo "  After that, ./run_docker.sh works without sudo, provided you are" >&2
    echo "  in the docker group:  sudo usermod -aG docker \"\$USER\"" >&2
    exit 1
fi

# ros-distro.sh resolves IMAGE_NAME, CONTAINER_NAME and ROS_DISTRO from what
# is actually installed, rather than from a hardcoded string.
# shellcheck disable=SC1091
source "$DIR/ros-distro.sh"

IMAGE="$IMAGE_NAME"
NAME="$CONTAINER_NAME"

BUILD=false
HEADLESS=false
SHELL_MODE=false
for arg in "$@"; do
    case "$arg" in
        --build)    BUILD=true ;;
        --headless) HEADLESS=true ;;
        --shell)    SHELL_MODE=true ;;
    esac
done

# -----------------------------------------------------------------------------
# Docker flavour
# -----------------------------------------------------------------------------
# This matters enormously and is the thing that used to break portability.
#
#   * Docker Desktop on Linux runs containers inside a VM. A bind-mounted
#     /tmp/.X11-unix does NOT work inside that VM (connect() -> ECONNREFUSED),
#     so display forwarding has to be tunneled over TCP and requires a
#     wildcard X authorisation cookie. That is what the original script did.
#
#   * A native Linux engine runs containers directly on the host. Mounting
#     /tmp/.X11-unix, the Wayland socket and /dev/shm just works, and is
#     faster and simpler - no socat, no wildcard cookie, no host.docker.internal.
#
# Detecting the flavour lets one script serve both.
# -----------------------------------------------------------------------------
DOCKER_FLAVOUR="native"
if [ -n "${DOCKER_HOST:-}" ]; then
    case "$DOCKER_HOST" in
        *desktop*) DOCKER_FLAVOUR="desktop" ;;
        *)         DOCKER_FLAVOUR="native" ;;
    esac
elif command -v docker >/dev/null 2>&1; then
    CTX="$(docker context show 2>/dev/null || echo "")"
    case "$CTX" in
        desktop*|*desktop-linux*) DOCKER_FLAVOUR="desktop" ;;
    esac
fi

# -----------------------------------------------------------------------------
# Daemon preflight
# -----------------------------------------------------------------------------
# Give a recovery hint that matches the flavour, instead of the old message
# which only ever mentioned Docker Desktop and was useless on a native install.
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon not reachable (context: $(docker context show 2>/dev/null || echo unknown), flavour: ${DOCKER_FLAVOUR})."
    if [ "$DOCKER_FLAVOUR" = "desktop" ]; then
        echo "       Recover with:  systemctl --user start docker-desktop"
    else
        echo "       Recover with:  sudo systemctl start docker"
        echo "       (or add yourself to the docker group once, then log out and back in:"
        echo "          sudo usermod -aG docker \"\$USER\" )"
    fi
    echo "       then re-run:   $0 $*"
    exit 1
fi

if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${NAME}$"; then
    echo "Removing previous container ${NAME}..."
    docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
if [ "$BUILD" = true ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building image ${IMAGE} (ROS distro: ${ROS_DISTRO})..."
    docker build --build-arg "ROS_DISTRO=${ROS_DISTRO}" -t "$IMAGE" "$DIR"
fi

# -----------------------------------------------------------------------------
# Detect GUI backend and GPU
# -----------------------------------------------------------------------------
GUI_ARGS=()
GPU_MODE="software"      # software | dri | nvidia
SESSION_TYPE="none"

if [ "$HEADLESS" = false ] && [ "$SHELL_MODE" = false ]; then
    # ---- Display server ----------------------------------------------------
    UID_NUM="$(id -u)"
    RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${UID_NUM}}"

    # Prefer X11 over Wayland: rviz2 and Gazebo's OGRE renderer need GLX (X11),
    # which does not work under Wayland inside a container.
    if [ -n "${DISPLAY:-}" ]; then
        # ---- X11 ------------------------------------------------------------
        X_DISPLAY_NUM="${DISPLAY#*:}"
        X_DISPLAY_NUM="${X_DISPLAY_NUM%%.*}"
        X_DISPLAY_NUM="${X_DISPLAY_NUM:-0}"
        X_UNIX_SOCKET="/tmp/.X11-unix/X${X_DISPLAY_NUM}"

        if [ -S "$X_UNIX_SOCKET" ]; then
            if [ "$DOCKER_FLAVOUR" = "native" ]; then
                # The simple, correct path for a native engine.
                SESSION_TYPE="x11"
                echo "Display server: X11 (unix socket ${X_UNIX_SOCKET})"

                # Let local clients connect. Harmless (unix-family only) and it
                # covers the case where the host runs an xauth-based X server.
                if command -v xhost >/dev/null 2>&1; then
                    xhost +local: >/dev/null 2>&1 || true
                fi

                GUI_ARGS+=(
                    -e "DISPLAY=:${X_DISPLAY_NUM}"
                    -v "/tmp/.X11-unix:/tmp/.X11-unix"
                    -e "QT_X11_NO_MITSHM=1"
                    -e "__GLX_VENDOR_LIBRARY_NAME=nvidia"
                    -e "LIBGL_ALWAYS_SOFTWARE=0"
                    # NVIDIA GLX vblank bug makes RViz/Gazebo panes flicker
                    # inside containers; xpresent presents every frame
                    # immediately instead of waiting on a broken vblank.
                    -e "vblank_mode=xpresent"
                    -e "__GL_SYNC_TO_VBLANK=0"
                )
            else
                # Docker Desktop: tunnel the host X socket to a TCP port and
                # point the container at it through host.docker.internal.
                X_TCP_PORT=$(( 6000 + 10#${X_DISPLAY_NUM} ))
                SOCAT="$(command -v socat || true)"
                if [ -z "$SOCAT" ]; then
                    echo "ERROR: GUI over Docker Desktop requires 'socat' on the host"
                    echo "       (to forward ${X_UNIX_SOCKET} to TCP ${X_TCP_PORT})."
                    echo "       Install it or run with --headless."
                    exit 1
                fi
                if ! ss -ltn 2>/dev/null | grep -q ":${X_TCP_PORT} "; then
                    echo "Forwarding ${X_UNIX_SOCKET} -> TCP ${X_TCP_PORT} (socat)"
                    mkdir -p /tmp/opencode
                    setsid nohup "$SOCAT" \
                        "TCP-LISTEN:${X_TCP_PORT},reuseaddr,fork" \
                        "UNIX-CONNECT:${X_UNIX_SOCKET}" \
                        >"/tmp/opencode/x11_socat_${X_DISPLAY_NUM}.log" 2>&1 &
                    sleep 1
                fi
                # The live cookie only carries a unix-family entry, and a
                # TCP-forwarded client is not unix-family, so a wildcard
                # cookie has to be built. This only applies to Docker Desktop.
                XAUTH_SRC="${XAUTHORITY:-${RUNTIME_DIR}/.mutter-Xwaylandauth.}"
                XAUTH_SRC="$(ls -t ${RUNTIME_DIR}/.mutter-Xwaylandauth.* "$HOME/.Xauthority" 2>/dev/null | head -1 || true)"
                WORK_COOKIE=""
                if [ -n "$XAUTH_SRC" ] && [ -s "$XAUTH_SRC" ]; then
                    rm -f /tmp/xauth_docker; touch /tmp/xauth_docker
                    xauth -f "$XAUTH_SRC" nlist ":${X_DISPLAY_NUM}" 2>/dev/null > /tmp/opencode/xn.txt || true
                    [ -s /tmp/opencode/xn.txt ] || \
                        xauth -f "$XAUTH_SRC" nlist 2>/dev/null > /tmp/opencode/xn.txt || true
                    if [ -s /tmp/opencode/xn.txt ]; then
                        sed -e 's/^..../ffff/' /tmp/opencode/xn.txt > /tmp/opencode/xf.txt
                        xauth -f /tmp/xauth_docker nmerge - < /tmp/opencode/xf.txt || true
                    fi
                    chmod 644 /tmp/xauth_docker
                    [ -s /tmp/xauth_docker ] && WORK_COOKIE=/tmp/xauth_docker
                fi
                if [ -z "$WORK_COOKIE" ]; then
                    echo "ERROR: could not build an X authorisation cookie for the" >&2
                    echo "       Docker Desktop VM. Run ./run_docker.sh --headless or" >&2
                    echo "       build the cookie manually (see AGENTS.md)." >&2
                    exit 1
                fi

                SESSION_TYPE="x11-tcp"
                echo "Display server: X11 via TCP (host.docker.internal:${X_TCP_PORT})"
                GUI_ARGS+=(
                    -e "DISPLAY=host.docker.internal:${X_DISPLAY_NUM}"
                    -e "XAUTHORITY=/tmp/xauth_cookie"
                    -v "${WORK_COOKIE}:/tmp/xauth_cookie:ro"
                    -e "QT_X11_NO_MITSHM=1"
                    --add-host "host.docker.internal:host-gateway"
                )
            fi
        else
            echo "WARNING: X socket ${X_UNIX_SOCKET} not found; continuing without GUI"
        fi
    fi

    # ---- GPU ---------------------------------------------------------------
    # Order of preference: NVIDIA runtime, then Mesa /dev/dri, then software.
    # The old script always mounted /dev/dri and always set
    # LIBGL_ALWAYS_SOFTWARE=1, which meant a host GPU was never used and the
    # simulation crawled. On a native engine with nvidia-container-toolkit the
    # right answer is --gpus all.
    HAS_NVIDIA_RUNTIME=false
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        if docker info 2>/dev/null | grep -qi 'nvidia'; then
            HAS_NVIDIA_RUNTIME=true
        fi
    fi

    if [ "$HAS_NVIDIA_RUNTIME" = true ]; then
        GPU_MODE="nvidia"
        echo "GPU: NVIDIA via nvidia-container-toolkit (--gpus all)"
        GUI_ARGS+=(--gpus all)
        GUI_ARGS+=(-e "NVIDIA_DRIVER_CAPABILITIES=all")
    elif [ -d /dev/dri ]; then
        GPU_MODE="dri"
        echo "GPU: forwarding /dev/dri (Mesa)"
        GUI_ARGS+=(-v /dev/dri:/dev/dri:rw)
    else
        GPU_MODE="software"
        echo "GPU: none available (llvmpipe software rendering)"
    fi

    # Shared memory. Gazebo, rviz2 and friends need more than Docker's 64 MB
    # default and fail in confusing ways when they run out.
    GUI_ARGS+=(--ipc host --shm-size 2gb)
else
    echo "Headless / shell mode: no display or GPU forwarding."
fi

# Software rendering only when there is genuinely no usable GPU. Honour an
# explicit override in the environment.
if [ -n "${LIBGL_ALWAYS_SOFTWARE:-}" ]; then
    SOFTWARE="$LIBGL_ALWAYS_SOFTWARE"
elif [ "$GPU_MODE" = "software" ]; then
    SOFTWARE=1
else
    SOFTWARE=0
fi

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if [ "$SHELL_MODE" = true ]; then
    echo "Starting interactive shell..."
    exec docker run -it --rm --name "$NAME" \
        --cpus=0 \
        "${GUI_ARGS[@]}" \
        -e "TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL}" \
        -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" \
        -e "LIBGL_ALWAYS_SOFTWARE=${SOFTWARE}" \
        -e "QT_X11_NO_MITSHM=1" \
        -v /dev/shm:/dev/shm \
        --shm-size=2gb \
        -v "$DIR/src:/workspace/src:rw" \
        -p 8765:8765 \
        --entrypoint /bin/bash \
        "$IMAGE"
fi

# Strip launcher-only flags so they never reach the container entrypoint
# (entrypoint exec's the first unknown token - `--build` used to do that).
CONTAINER_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --build|--headless|--shell) ;;  # host-side only
        *) CONTAINER_ARGS+=("$arg") ;;
    esac
done

if [ "$HEADLESS" = true ]; then
    echo "Running in headless mode..."
    set -- --headless
elif [ ${#CONTAINER_ARGS[@]} -gt 0 ]; then
    set -- "${CONTAINER_ARGS[@]}"
else
    echo "Running with GUI..."
    set --
fi

# Bounded json-file logs: ROS nodes log at a high rate, and without rotation
# the log file grows unbounded inside the Docker storage volume.
docker run -d --name "$NAME" \
    --log-opt max-size=50m --log-opt max-file=5 \
    --cpus=0 \
    "${GUI_ARGS[@]}" \
    -e "TURTLEBOT3_MODEL=${TURTLEBOT3_MODEL}" \
    -e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" \
    -e "LIBGL_ALWAYS_SOFTWARE=${SOFTWARE}" \
    -e "QT_X11_NO_MITSHM=1" \
    -v /dev/shm:/dev/shm \
    --shm-size=2gb \
    -v "$DIR/src:/workspace/src:rw" \
    -p 8765:8765 \
    "$IMAGE" "$@"

echo
echo "Container started: ${NAME}"
echo "  Distro:  ROS 2 ${ROS_DISTRO}"
echo "  Display: ${SESSION_TYPE}   GPU: ${GPU_MODE}   software-render: ${SOFTWARE}"
echo "  Logs:    docker logs -f ${NAME}"

# Wait for the container to either become READY or exit; preserve logs on exit.
echo "Waiting for stack to become READY (Nav2 + battery + supervisor)..."
READY=false
for _ in $(seq 1 90); do
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
        echo "FAIL: container exited during startup (see logs below)."
        docker logs "$NAME" 2>&1 | tail -80 || true
        docker rm "$NAME" >/dev/null 2>&1 || true
        exit 1
    fi
    if docker logs "$NAME" 2>&1 | grep -q "Nav2 lifecycle bringup complete"; then
        READY=true
        break
    fi
    sleep 2
done

if [ "$READY" = true ]; then
    echo "READY: Nav2 lifecycle bringup complete."
else
    echo "WARN: readiness marker not seen after 180s — check docker logs -f ${NAME}"
fi
echo "  Foxglove: open https://app.foxglove.dev and connect to ws://localhost:8765"
echo "            (the bridge is a WebSocket server, not a web page; layout:"
echo "            src/house_cleaner_bringup/config/foxglove_layout.json)"
echo "  Stop:     docker stop ${NAME}"
