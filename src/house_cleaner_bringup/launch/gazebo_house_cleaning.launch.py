#!/usr/bin/env python3
# =============================================================================
# gazebo_house_cleaning.launch.py
# =============================================================================
# Launches Gazebo Harmonic with the house room world and the TurtleBot3
# Burger (URDF TF, spawn, gz-ROS bridge).  The Gazebo GUI client is launched
# UNLESS ``headless:=true``.
#
# Usage:
#   ros2 launch house_cleaner_bringup gazebo_house_cleaning.launch.py
#   ros2 launch house_cleaner_bringup gazebo_house_cleaning.launch.py headless:=true
# =============================================================================

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.conditions import UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    tbg = get_package_share_directory('turtlebot3_gazebo')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    BRINGUP = get_package_share_directory('house_cleaner_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    headless = LaunchConfiguration('headless', default='false')
    world = LaunchConfiguration('world', default='house_room.world')
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')

    world_path = PathJoinSubstitution([BRINGUP, 'worlds', world])

    # Gazebo: server-only (-s) when headless; otherwise launch server + GUI
    # *in the same process* (no separate -g client).  A detached `gz sim -g`
    # client does not attach to the -s server (different transport/RESOURCE
    # URI), leaving the world stalled with 0 iterations on /world/.../clock.
    # Running a single `gz sim -r` instance gives both server and GUI window.
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': ['-r -v2 ', world_path],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=UnlessCondition(LaunchConfiguration('headless', default='false')),
    )
    gzheadless_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': ['-r -s -v2 ', world_path],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(LaunchConfiguration('headless', default='false')),
    )

    # URDF -> TF
    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tbg, 'launch', 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    # Spawn burger
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

    # gz <-> ROS bridge (clock, tf, odom, scan, imu, cmd_vel)
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

    # Resource paths so Gazebo can find the burger and custom dock models.
    set_env_resources = SetEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(tbg, 'models')
    )
    set_env_model = SetEnvironmentVariable(
        'GZ_SIM_SYSTEM_RESOURCE_PATH',
        os.path.join(tbg, 'models')
    )
    # Software-rendering fallback (llvmpipe) — set externally if needed;
    # default OFF so a real GPU is used when available.
    set_env_libgl = SetEnvironmentVariable(
        'LIBGL_ALWAYS_SOFTWARE',
        LaunchConfiguration('libgl_software', default='0')
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock for all nodes'))
    ld.add_action(DeclareLaunchArgument(
        'headless', default_value='false',
        description='Run without Gazebo GUI (server only)'))
    ld.add_action(DeclareLaunchArgument(
        'world', default_value='house_room.world',
        description='World file under house_cleaner_bringup/worlds'))
    ld.add_action(DeclareLaunchArgument(
        'x_pose', default_value='0.0', description='Spawn x (m)'))
    ld.add_action(DeclareLaunchArgument(
        'y_pose', default_value='0.0', description='Spawn y (m)'))
    ld.add_action(DeclareLaunchArgument(
        'libgl_software', default_value='1',
        description='Force Mesa llvmpipe software rendering (1, default)'))

    ld.add_action(set_env_resources)
    ld.add_action(set_env_model)
    ld.add_action(set_env_libgl)
    ld.add_action(gzserver_cmd)
    ld.add_action(gzheadless_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)
    ld.add_action(bridge_cmd)

    return ld