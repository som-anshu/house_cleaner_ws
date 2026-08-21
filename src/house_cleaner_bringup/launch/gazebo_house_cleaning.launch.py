#!/usr/bin/env python3
#
# gazebo_house_cleaning.launch.py
#
# Real-sensor simulation wrapper: TurtleBot3 burger in a simple single-room
# Gazebo world: worlds/house_room.world (interior 4.65x5.75 m — furniture
# obstacles + charging dock, matching the shipped SLAM map). Override
# world:=<name> only with a file shipped inside BRINGUP/worlds — the path
# resolves exclusively under this package's share dir.
#
# Flow (mirrors ROBOTIS Gazebo simulation tutorial):
#   1. gz-sim server+GUI loads the world (GUI enabled by default)
#   2. robot_state_publisher publishes URDF TF (use_sim_time=true)
#   3. ros_gz_sim create spawns the burger
#   4. ros_gz_bridge parameter_bridge bridges /clock /odom /scan /tf /cmd_vel /imu
#
# Usage:
#   export TURTLEBOT3_MODEL=burger
#   ros2 launch house_cleaner_bringup gazebo_house_cleaning.launch.py
#
# NOTE on cmd_vel: the bridge maps /cmd_vel as plain geometry_msgs/Twist
# (config/burger_bridge.yaml), so Nav2's controller_server can drive directly.
# To drive manually:
#   ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \
#     "{linear: {x: 0.2}, angular: {z: 0.0}}"

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    tbg = get_package_share_directory('turtlebot3_gazebo')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    BRINGUP = get_package_share_directory('house_cleaner_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world = LaunchConfiguration('world', default='house_room.world')
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')

    world_path = PathJoinSubstitution([BRINGUP, 'worlds', world])

    # 1. Gazebo: house room with obstacles + charging dock (GUI enabled)
    # -r runs immediately, -s = server only, -v2 = verbose level 2
    # GUI is always started (no headless mode)
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r -s -v2 ', world_path], 'on_exit_shutdown': 'true'}.items()
    )

    # 1b. GUI client — always enabled
    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-g -v2 ', 'on_exit_shutdown': 'true'}.items()
    )

    # 2. URDF -> TF (sim time so TF follows the Gazebo clock)
    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tbg, 'launch', 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    # 3+4. Spawn burger + start topic bridge.
    # Not via turtlebot3_gazebo's spawn_turtlebot3.launch.py: its bridge config
    # is hardcoded to the stock turtlebot3_burger_bridge.yaml, which maps
    # /cmd_vel as TwistStamped — Nav2 controller_server cannot publish that.
    # We spawn explicitly and run our own parameter_bridge with
    # config/burger_bridge.yaml (cmd_vel = plain geometry_msgs/Twist).
    spawn_turtlebot_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'turtlebot3_burger',
            '-file', os.path.join(tbg, 'models', 'turtlebot3_burger', 'model.sdf'),
            '-x', x_pose,
            '-y', y_pose,
            '-z', '0.01',
        ],
        output='screen',
    )

    bridge_cmd = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '--ros-args',
            '-p',
            f'config_file:={os.path.join(BRINGUP, "config", "burger_bridge.yaml")}',
        ],
        output='screen',
    )

    # House model must resolve from the local share dir, not fuel.gazebosim.org
    set_env_resources = SetEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(tbg, 'models')
    )
    set_env_model = SetEnvironmentVariable(
        'GZ_SIM_SYSTEM_RESOURCE_PATH',
        os.path.join(tbg, 'models')
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock for all nodes (must be true with Gazebo)'))
    ld.add_action(DeclareLaunchArgument(
        'world', default_value='house_room.world',
        description='World file under house_cleaner_bringup/worlds'))
    ld.add_action(DeclareLaunchArgument(
        'x_pose', default_value='0.0', description='Spawn x (m)'))
    ld.add_action(DeclareLaunchArgument(
        'y_pose', default_value='0.0', description='Spawn y (m)'))

    ld.add_action(set_env_resources)
    ld.add_action(set_env_model)
    ld.add_action(gzserver_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)
    ld.add_action(bridge_cmd)
    ld.add_action(gzclient_cmd)

    return ld
