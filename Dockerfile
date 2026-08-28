# =============================================================================
# Dockerfile - House Cleaner Robot ROS2 Jazzy Docker Image
# =============================================================================
# This Dockerfile creates a complete ROS2 Jazzy environment with:
#   - Gazebo Harmonic (physics simulation)
#   - Nav2 (autonomous navigation)
#   - slam_toolbox (SLAM mapping)
#   - TurtleBot3 Burger (robot model)
#   - Foxglove Bridge (web visualization)
#   - RViz2 (local visualization)
#   - Teleop (keyboard control)
#
# Build:
#   docker build -t house_cleaner:jazzy .
#
# Run (with GUI):
#   docker run -it --rm \
#     -e DISPLAY=$DISPLAY \
#     -v /tmp/.X11-unix:/tmp/.X11-unix \
#     house_cleaner:jazzy
#
# Run (headless, no GUI):
#   docker run -it --rm house_cleaner:jazzy --headless
# =============================================================================

# Base image: ROS2 Jazzy with core tools
# Using ros-base (not desktop) to keep image smaller, we add GUI tools manually
FROM ros:jazzy-ros-base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# =============================================================================
# System Dependencies
# =============================================================================
# Install all required packages in a single RUN layer to minimize image size
# Each package group is commented with its purpose
RUN apt-get update && apt-get install -y --no-install-recommends \
    # --- Build tools ---
    python3-colcon-common-extensions \
    # --- SLAM (Simultaneous Localization and Mapping) ---
    ros-jazzy-slam-toolbox \
    # --- TurtleBot3 simulation packages ---
    ros-jazzy-turtlebot3-gazebo \
    ros-jazzy-turtlebot3-description \
    # --- Gazebo Harmonic integration with ROS2 ---
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    # --- Navigation2 (Nav2) stack ---
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
    # --- Visualization ---
    ros-jazzy-rviz2 \
    ros-jazzy-foxglove-bridge \
    # --- Teleop control ---
    ros-jazzy-teleop-twist-keyboard \
    # --- OpenGL/Mesa for GUI rendering in container ---
    # Required for Gazebo GUI to work without GPU drivers
    libglu1-mesa-dev \
    libgl1 \
    libgl1-mesa-dri \
    mesa-utils \
    # --- X11 utilities for GUI forwarding ---
    x11-xserver-utils \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Workspace Setup
# =============================================================================
# Set working directory for the workspace
WORKDIR /workspace

# Copy source code and build
COPY src/ src/
COPY LICENSE .

# Build the workspace
# --symlink-install: Creates symlinks instead of copying files (faster development)
# --event-handlers console_direct+: Show build output in terminal
RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --symlink-install --event-handlers console_direct-

# =============================================================================
# Environment Configuration
# =============================================================================
# Source workspace in bashrc so it's available in every shell
# Order matters: workspace first, then ROS base
RUN echo 'source /workspace/install/setup.bash' >> /root/.bashrc && \
    echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc

# Robot configuration
ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=30

# Fix for colcon hook issue: AMENT_PREFIX_PATH must be set explicitly
# because older colcon versions don't populate it correctly from hooks
ENV AMENT_PREFIX_PATH=/workspace/install/house_cleaner_bringup:/workspace/install:/opt/ros/jazzy

# =============================================================================
# Entrypoint
# =============================================================================
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
