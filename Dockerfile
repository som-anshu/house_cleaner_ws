# =============================================================================
# Dockerfile - House Cleaner Robot ROS2 Jazzy Docker Image
# =============================================================================
# This Dockerfile creates a complete ROS2 Jazzy environment.
#
# Build:
#   docker build -t house_cleaner:jazzy .
#
# Run (headless, no GUI):
#   docker run -it --rm house_cleaner:jazzy --headless
# =============================================================================

FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
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
    ros-jazzy-rviz2 \
    ros-jazzy-foxglove-bridge \
    ros-jazzy-teleop-twist-keyboard \
    libglu1-mesa-dev \
    libgl1 \
    libgl1-mesa-dri \
    mesa-utils \
    x11-xserver-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY src/ src/
COPY LICENSE .

RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --symlink-install --event-handlers console_direct-

RUN echo 'source /workspace/install/setup.bash' >> /root/.bashrc && \
    echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc

ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=30

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
