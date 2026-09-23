#!/usr/bin/env bash
# =============================================================================
# run_docker.sh - Docker Launcher for House Cleaner Robot
# =============================================================================
# Launches the house cleaner robot simulation in Docker with GUI forwarding
# on Linux.  Supports both X11 and Wayland sessions (auto-detected), GPU
# acceleration when available, and a software-rendering fallback.
#
# Usage:
#   ./run_docker.sh                 # Run with GUI (X11 or Wayland)
#   ./run_docker.sh --build         # Force rebuild
#   ./run_docker.sh --headless      # Run without GUI (Foxglove still up)
#   ./run_docker.sh --shell         # Drop into an interactive bash shell
# =============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="house_cleaner:jazzy"
NAME="house_cleaner_jazzy"

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

# Clean up any previous container (no lingering state).
# Daemon preflight: Docker Desktop (desktop-linux context) is a user service
# that session lifecycle events can stop (SIGTERM from user systemd / explicit
# backend cancel — see journal: "terminating on signal 15", "explicit cancel").
# Fail fast with the recovery command instead of cryptic "Cannot connect"
# errors halfway through the launch.
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon not reachable (context: $(docker context show 2>/dev/null || echo unknown))."
    echo "       Recover with:  systemctl --user start docker-desktop"
    echo "       then re-run:   $0 $*"
    exit 1
fi
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${NAME}$"; then
    echo "Removing previous container..."
    docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

# ---- Build -----------------------------------------------------------------
if [ "$BUILD" = true ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Building Docker image $IMAGE ..."
    docker build -t "$IMAGE" "$DIR"
fi

# ---- Detect GUI backend -----------------------------------------------------
GUI_ARGS=()
USE_GPU=false
if [ "$HEADLESS" = false ] && [ "$SHELL_MODE" = false ]; then
    # Docker Desktop (Linux) runs containers inside a qemu VM, so bind-mounting
    # /tmp/.X11-unix does NOT produce a working unix socket inside the
    # container (connect() gets ECONNREFUSED).  The X server (Xwayland on
    # Gnome, or Xorg) listens only on the host unix socket, so we forward it
    # to a TCP port with socat on the host and point the container at
    # host.docker.internal:<DISPLAY_NUM>.
    X_DISPLAY_NUM="${DISPLAY#*:}"
    X_DISPLAY_NUM="${X_DISPLAY_NUM%%.*}"
    X_DISPLAY_NUM="${X_DISPLAY_NUM:-0}"
    X_UNIX_SOCKET="/tmp/.X11-unix/X${X_DISPLAY_NUM}"
    X_TCP_PORT=$(( 6000 + 10#${X_DISPLAY_NUM} ))
    SOCAT="$(command -v socat || true)"

    if [ -S "$X_UNIX_SOCKET" ]; then
        if [ -z "$SOCAT" ]; then
            echo "ERROR: GUI over Docker Desktop requires 'socat' on the host"
            echo "       (to forward X socket ${X_UNIX_SOCKET} to TCP ${X_TCP_PORT})."
            echo "       Install it or run with --headless."
            exit 1
        fi
        if ! ss -ltn 2>/dev/null | grep -q ":${X_TCP_PORT} "; then
            echo "Forwarding ${X_UNIX_SOCKET} -> TCP ${X_TCP_PORT} (socat)"
            setsid nohup "$SOCAT" \
                "TCP-LISTEN:${X_TCP_PORT},reuseaddr,fork" \
                "UNIX-CONNECT:${X_UNIX_SOCKET}" \
                >/tmp/opencode/x11_socat_${X_DISPLAY_NUM}.log 2>&1 &
            sleep 1
        fi
        echo "GUI backend: X11 via TCP (host.docker.internal:${X_TCP_PORT})"
        GUI_ARGS+=(
            -e DISPLAY="host.docker.internal:$(( X_TCP_PORT - 6000 ))"
            -e XAUTHORITY=/tmp/xauth_cookie
            -v "${XAUTHORITY:-$HOME/.Xauthority}:/tmp/xauth_cookie:ro"
            -e QT_X11_NO_MITSHM=1
        )
    else
        echo "WARNING: X socket ${X_UNIX_SOCKET} not found; continuing without GUI"
    fi

    # GPU acceleration: forward /dev/dri when the host has it.
    if [ -d /dev/dri ]; then
        echo "GPU devices found — forwarding /dev/dri"
        GUI_ARGS+=(-v /dev/dri:/dev/dri:rw)
        USE_GPU=true
    else
        echo "No /dev/dri on host — using software rendering (llvmpipe)"
    fi
fi

# Software rendering fallback is the default (works on every machine); disable
# it explicitly with LIBGL_ALWAYS_SOFTWARE=0 to use a GPU driver.
SOFTWARE=${LIBGL_ALWAYS_SOFTWARE:-1}

# ---- Run --------------------------------------------------------------------
if [ "$SHELL_MODE" = true ]; then
    echo "Starting interactive shell..."
    exec docker run -it --rm --name "$NAME" \
        "${GUI_ARGS[@]}" \
        -e TURTLEBOT3_MODEL=burger \
        -e ROS_DOMAIN_ID=30 \
        -e LIBGL_ALWAYS_SOFTWARE="$SOFTWARE" \
        -e QT_X11_NO_MITSHM=1 \
        -v /dev/shm:/dev/shm \
        --shm-size=2gb \
        -v "$DIR/src:/workspace/src:rw" \
        -p 8765:8765 \
        --entrypoint /bin/bash \
        "$IMAGE"
fi

# Strip launcher-only flags so they never reach the container entrypoint
# (entrypoint exec's the first unknown token — `--build` used to do that).
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

# Bounded json-file logs: ROS nodes log at high rate (MPPI ~20 Hz); without
# rotation the log file grows unbounded inside the Docker Desktop VM disk
# (Docker.raw, already 288 GB on a 98%-full host disk — see CONTEXT.md §1).
docker run -d --name "$NAME" \
    --log-opt max-size=50m --log-opt max-file=5 \
    "${GUI_ARGS[@]}" \
    -e TURTLEBOT3_MODEL=burger \
    -e ROS_DOMAIN_ID=30 \
    -e LIBGL_ALWAYS_SOFTWARE="$SOFTWARE" \
    -e QT_X11_NO_MITSHM=1 \
    -v /dev/shm:/dev/shm \
    --shm-size=2gb \
    -v "$DIR/src:/workspace/src:rw" \
    -p 8765:8765 \
    "$IMAGE" "$@"

echo "Container started: $NAME"
echo "  Logs:    docker logs -f $NAME"

# Wait for the container to either become READY or exit; preserve logs on exit.
echo "Waiting for stack to become READY (Nav2 + battery + supervisor)..."
READY=false
for i in $(seq 1 90); do
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
    echo "WARN: readiness marker not seen after 180s — check docker logs -f $NAME"
fi
echo "  Foxglove: http://localhost:8765"
echo "  Stop:    docker stop $NAME"