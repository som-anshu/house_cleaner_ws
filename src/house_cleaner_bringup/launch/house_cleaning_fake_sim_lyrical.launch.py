"""Minimal launch file for ROS2 Lyrical (no Nav2 dependencies).

This provides a basic simulation with:
- fake_sim: synthetic odom + laser scan
- TF transforms
- Basic topic publishers
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os


def generate_launch_description():
    """Generate launch description for minimal fake_sim (Lyrical-compatible)."""
    BRINGUP = get_package_share_directory('house_cleaner_bringup')

    use_sim_time = False

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('room_width', default_value='4.65'),
        DeclareLaunchArgument('room_height', default_value='5.75'),

        # Run fake_sim with room parameters
        Node(
            package='house_cleaner_bringup',
            executable='fake_sim_lyrical',
            name='house_cleaning_fake_sim',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                {'room_width': LaunchConfiguration('room_width')},
                {'room_height': LaunchConfiguration('room_height')},
            ],
        ),
    ])