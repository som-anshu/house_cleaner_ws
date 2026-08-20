# House Cleaner Robot - ROS2 Jazzy Docker image
#
# Full autonomous cleaning demo (Gazebo Harmonic + slam_toolbox + Nav2 +
# house_cleaner_assistant) inside a container. Headless by default.
#
# Build:    docker build -t house_cleaner:jazzy .
# Run:      docker compose up          # or:
#           docker run -it house_cleaner:jazzy ros2 launch \
#             house_cleaner_bringup house_cleaning_auto.launch.py

FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# Nav2 manual stack (verified package set for this project)
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY src/ src/
COPY LICENSE .

RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --symlink-install --event-handlers console_direct-

# Source order matters: workspace first, ROS base last
RUN echo 'source /workspace/install/setup.bash' >> /root/.bashrc && \
    echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc

ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=30
# colcon hook quirk (same as host env.sh): setup.bash never populates
# AMENT_PREFIX_PATH from hook-style package.dsv, so ros2 launch can't find
# the package. Set it explicitly.
ENV AMENT_PREFIX_PATH=/workspace/install/house_cleaner_bringup:/workspace/install:/opt/ros/jazzy

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["source /opt/ros/jazzy/setup.bash && source /workspace/install/setup.bash && ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py"]