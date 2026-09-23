# =============================================================================
# Dockerfile - House Cleaner Robot ROS2 Jazzy Docker Image
# =============================================================================
# ROS2 Jazzy + Gazebo Harmonic simulation image for the house cleaner robot.
# GUI: Linux X11 + Wayland (Xwayland) — see run_docker.sh.
#
# Build:
#   docker build -t house_cleaner:jazzy .
#
# Run:
#   ./run_docker.sh            # GUI
#   ./run_docker.sh --headless
# =============================================================================

FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# GUI runtime deps: X11 + Wayland forwarding (no VNC), xauth for the X11
# cookie, and Qt/EGL/GL fallbacks so Gazebo + RViz render under llvmpipe.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    python3-pytest \
    ros-jazzy-slam-toolbox \
    ros-jazzy-turtlebot3-gazebo \
    ros-jazzy-turtlebot3-description \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-nav2-msgs \
    ros-jazzy-nav2-core \
    ros-jazzy-nav2-common \
    ros-jazzy-nav2-util \
    ros-jazzy-nav2-costmap-2d \
    ros-jazzy-nav2-behavior-tree \
    ros-jazzy-nav2-map-server \
    ros-jazzy-nav2-amcl \
    ros-jazzy-nav2-planner \
    ros-jazzy-nav2-controller \
    ros-jazzy-nav2-behaviors \
    ros-jazzy-nav2-bt-navigator \
    ros-jazzy-nav2-waypoint-follower \
    ros-jazzy-nav2-velocity-smoother \
    ros-jazzy-nav2-collision-monitor \
    ros-jazzy-nav2-lifecycle-manager \
    ros-jazzy-nav2-navfn-planner \
    ros-jazzy-nav2-mppi-controller \
    ros-jazzy-nav2-smoother \
    ros-jazzy-nav2-bringup \
    ros-jazzy-rviz2 \
    ros-jazzy-foxglove-bridge \
    ros-jazzy-teleop-twist-keyboard \
    xauth \
    x11-xserver-utils \
    libgl1 \
    libgl1-mesa-dri \
    mesa-utils \
    libglx-mesa0 \
    libqt5gui5 \
    qtwayland5 \
    libqt5waylandclient5 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libegl1 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-server0 \
    libsdl2-2.0-0 \
    libassimp5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY src/ src/
COPY LICENSE LICENSE

RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --symlink-install --event-handlers console_direct-

# .bashrc order matters: /opt/ros must come BEFORE the workspace overlay so
# the overlay's packages take precedence.
RUN echo 'source /opt/ros/jazzy/setup.bash' > /root/.bashrc && \
    echo 'source /workspace/install/setup.bash' >> /root/.bashrc

ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=30
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV QT_X11_NO_MITSHM=1

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]