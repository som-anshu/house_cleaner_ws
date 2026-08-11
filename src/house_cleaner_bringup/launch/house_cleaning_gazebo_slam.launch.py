#!/usr/bin/env python3
#
# house_cleaning_gazebo_slam.launch.py
#
# Mapping phase for the Gazebo stack: real-sensor simulation + slam_toolbox.
# Mirrors the ROBOTIS tutorial flow (Gazebo -> SLAM -> save map -> navigate).
#
#   export TURTLEBOT3_MODEL=burger
#   ros2 launch house_cleaner_bringup house_cleaning_gazebo_slam.launch.py
#
# After mapping:
#   ros2 run nav2_map_server map_saver_cli -f /home/koko/house_map
#
# Then navigate on the saved map with house_cleaning_fake_sim.launch.py
# (repoint its map yaml) — or run the nav stack against this sim.

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

BRINGUP = '/home/koko/house_cleaner_ws/src/house_cleaner_bringup'


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    headless = LaunchConfiguration('headless', default='true')

    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'headless': headless,
        }.items()
    )

    # slam_toolbox async mapping on the real LDS data
    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            os.path.join(BRINGUP, 'config', 'slam_toolbox_gazebo_params.yaml')
        ],
    )

    # slam_toolbox is a lifecycle node — autostart it.
    # bond_timeout raised: Gazebo boots slower than fake_sim, and the default
    # 4s bond check aborts bringup before slam_toolbox registers.
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_slam',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'node_names': ['slam_toolbox'],
            'bond_timeout': 20.0,
        }],
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock (must be true with Gazebo)'))
    ld.add_action(DeclareLaunchArgument(
        'headless', default_value='true',
        description='true = no Gazebo GUI'))

    ld.add_action(gazebo_sim)
    ld.add_action(slam_toolbox)
    ld.add_action(lifecycle_manager)

    return ld
