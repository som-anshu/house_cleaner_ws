#!/usr/bin/env python3
#
# house_cleaning_gazebo_nav.launch.py
#
# Full Nav2 stack on Gazebo: localize on the saved single-room SLAM map and
# navigate. This is the "return to dock" backbone — navigate_to_pose /
# navigate_through_poses / docking all build on this.
#
#   export TURTLEBOT3_MODEL=burger
#   ros2 launch house_cleaner_bringup house_cleaning_gazebo_nav.launch.py
#
# Nodes brought up:
#   gazebo_house_cleaning.launch.py  (world, burger, plain-Twist bridge)
#   nav2 bringup_launch.py           (map_server, amcl, planner, controller,
#                                     bt_navigator, behavior_server, ...)
#
# The map is the SLAM result saved earlier; it now ships with the package
# at config/house_room_map.yaml (copy of the SLAM save). The robot spawns at
# world (0,0) yaw 0, which is also its start pose in the map frame, so amcl
# initial_pose matches the spawn. Override with map:=/path/to/other_map.yaml.

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

BRINGUP = get_package_share_directory('house_cleaner_bringup')
NAV2_BRINGUP = get_package_share_directory('nav2_bringup')


def generate_launch_description():
    headless = LaunchConfiguration('headless', default='true')
    map_yaml = LaunchConfiguration(
        'map',
        default=os.path.join(BRINGUP, 'config', 'single_room_map.yaml'),
    )

    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning.launch.py')
        ),
        launch_arguments={
            'headless': headless,
            'x_pose': '0.0',
            'y_pose': '0.0',
        }.items()
    )

    nav2_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(NAV2_BRINGUP, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'map': map_yaml,
            'use_sim_time': 'true',
            'params_file': os.path.join(BRINGUP, 'config', 'nav2_params.yaml'),
            'autostart': 'true',
            'slam': 'False',
            'use_localization': 'True',
            'use_composition': 'True',
        }.items()
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'headless', default_value='true',
        description='true = no Gazebo GUI'))
    ld.add_action(DeclareLaunchArgument(
        'map', default_value=os.path.join(BRINGUP, 'config', 'single_room_map.yaml'),
        description='Saved SLAM map yaml for localization'))

    ld.add_action(gazebo_sim)
    ld.add_action(nav2_stack)

    return ld
