#!/usr/bin/env python3
# =============================================================================
# gazebo_house_cleaning_headless.launch.py
# =============================================================================
# Headless version of gazebo_house_cleaning.launch.py - no GUI client.
# =============================================================================

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

    # Gazebo server only (no GUI client)
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r -s -v2 ', world_path], 'on_exit_shutdown': 'true'}.items()
    )

    # URDF -> TF
    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tbg, 'launch', 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
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

    # Bridge
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

    return ld