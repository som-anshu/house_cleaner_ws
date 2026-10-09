# =============================================================================
# Dockerfile - House Cleaner Robot ROS 2 simulation image
# =============================================================================
# ROS 2 + Gazebo simulation image for the house cleaner robot.
# GUI: Linux X11 + Wayland (Xwayland) - see run_docker.sh.
#
# The distro is a build argument, so the same image builds on Ubuntu 26.04
# (lyrical / Gazebo Jetty), 24.04 (jazzy / Gazebo Harmonic) or 22.04
# (humble / Gazebo Fortress) without editing this file:
#
#   docker build -t house_cleaner:lyrical --build-arg ROS_DISTRO=lyrical .
#
# run_docker.sh auto-detects and passes the right value.
#
# Gazebo pairing (the simulator version follows the distro):
#   lyrical -> Gazebo Jetty  (gz-sim 10)
#   jazzy   -> Gazebo Harmonic (gz-sim 8)
#   humble  -> Gazebo Fortress (gz-sim 6)
# =============================================================================

ARG ROS_DISTRO=lyrical
FROM ros:${ROS_DISTRO}-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# Re-declare the build arg: a global ARG is not visible inside a build stage
# unless it is repeated after FROM.
ARG ROS_DISTRO
ARG ROS_PACKAGE_SET=

ENV ROS_DISTRO=${ROS_DISTRO}

# Nav2 stack. Named packages rather than the ros-<distro>-navigation2
# metapackage so that a missing component in a new distro fails loudly at
# build time instead of silently dropping behaviour at run time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-${ROS_DISTRO}-slam-toolbox \
    ros-${ROS_DISTRO}-turtlebot3-gazebo \
    ros-${ROS_DISTRO}-turtlebot3-description \
    ros-${ROS_DISTRO}-ros-gz-sim \
    ros-${ROS_DISTRO}-ros-gz-bridge \
    ros-${ROS_DISTRO}-nav2-msgs \
    ros-${ROS_DISTRO}-nav2-core \
    ros-${ROS_DISTRO}-nav2-common \
    ros-${ROS_DISTRO}-nav2-util \
    ros-${ROS_DISTRO}-nav2-costmap-2d \
    ros-${ROS_DISTRO}-nav2-behavior-tree \
    ros-${ROS_DISTRO}-nav2-map-server \
    ros-${ROS_DISTRO}-nav2-amcl \
    ros-${ROS_DISTRO}-nav2-planner \
    ros-${ROS_DISTRO}-nav2-controller \
    ros-${ROS_DISTRO}-nav2-behaviors \
    ros-${ROS_DISTRO}-nav2-bt-navigator \
    ros-${ROS_DISTRO}-nav2-waypoint-follower \
    ros-${ROS_DISTRO}-nav2-velocity-smoother \
    ros-${ROS_DISTRO}-nav2-collision-monitor \
    ros-${ROS_DISTRO}-nav2-lifecycle-manager \
    ros-${ROS_DISTRO}-nav2-navfn-planner \
    ros-${ROS_DISTRO}-nav2-mppi-controller \
    ros-${ROS_DISTRO}-nav2-smoother \
    ros-${ROS_DISTRO}-nav2-bringup \
    ros-${ROS_DISTRO}-rviz2 \
    ros-${ROS_DISTRO}-foxglove-bridge \
    ros-${ROS_DISTRO}-teleop-twist-keyboard \
    ${ROS_PACKAGE_SET} \
    \
    python3-colcon-common-extensions \
    python3-pytest \
    \
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

# Ament genversionh style note: ROS_PACKAGE_VERSION is not set, so packages
# build with the version from package.xml only.
RUN . /opt/ros/${ROS_DISTRO}/setup.sh && \
    colcon build --symlink-install --event-handlers console_direct-

# .bashrc order matters: /opt/ros must come BEFORE the workspace overlay so
# the overlay's packages take precedence.
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" > /root/.bashrc && \
    echo 'source /workspace/install/setup.bash' >> /root/.bashrc

ENV TURTLEBOT3_MODEL=burger
ENV ROS_DOMAIN_ID=30
ENV QT_X11_NO_MITSHM=1

# LIBGL_ALWAYS_SOFTWARE is deliberately NOT baked in. It used to default to 1,
# which forced llvmpipe software rendering even on hosts with a working GPU and
# was a major contributor to the ~0.5 real-time factor this project suffered.
# run_docker.sh now sets it at run time based on what it detects. Set
#   LIBGL_ALWAYS_SOFTWARE=1 ./run_docker.sh
# to force software rendering when there is no GPU.

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
