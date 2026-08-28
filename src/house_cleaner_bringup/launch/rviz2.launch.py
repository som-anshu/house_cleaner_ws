#!/usr/bin/env python3
# =============================================================================
# rviz2.launch.py - RViz2 Visualization Launch File
# =============================================================================
# This launch file starts RViz2 with the house cleaner robot configuration.
# RViz2 is a 3D visualization tool for ROS2 that shows:
#   - Robot model and TF frames
#   - Laser scan data
#   - Map and costmap
#   - Navigation goals and paths
#   - Battery state
#
# Usage:
#   ros2 launch house_cleaner_bringup rviz2.launch.py
#
# Features:
#   - Automatic display configuration for house cleaner topics
#   - Robot model visualization
#   - Map and costmap display
#   - Laser scan visualization
#   - Navigation path display
# =============================================================================

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for RViz2."""

    # Get package share directory for config files
    bringup_dir = get_package_share_directory('house_cleaner_bringup')

    # RViz2 node with default configuration
    # The -d flag loads a default display configuration
    rviz2_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(bringup_dir, 'config', 'nav2_params.yaml')],
        parameters=[{
            'use_sim_time': True,
        }],
    )

    return LaunchDescription([
        rviz2_node,
    ])
