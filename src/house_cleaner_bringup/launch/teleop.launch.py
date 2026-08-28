#!/usr/bin/env python3
# =============================================================================
# teleop.launch.py - Teleop Control Launch File
# =============================================================================
# This launch file starts teleop_twist_keyboard for manual robot control.
# Use this to manually drive the robot in Gazebo for testing.
#
# Usage:
#   ros2 launch house_cleaner_bringup teleop.launch.py
#
# Controls:
#   i - Move forward
#   k - Stop
#   j - Turn left
#   l - Turn right
#   u - Move forward + turn left
#   o - Move forward + turn right
#   , - Move backward
#   . - Increase speed
#   - - Decrease speed
#
# Tips:
#   - Keep the terminal window focused for keyboard input to work
#   - Press 'q' to quit teleop
#   - Speed is shown in the terminal output
# =============================================================================

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for teleop control."""

    # Teleop Twist Keyboard node
    # This allows you to control the robot using keyboard input
    teleop_node = Node(
        package='teleop_twist_keyboard',
        executable='teleop_twist_keyboard',
        name='teleop_twist_keyboard',
        output='screen',
        prefix='xterm -e',  # Open in new terminal window
        parameters=[{
            'use_sim_time': True,
            # Scale for linear velocity (m/s)
            'scale_linear': 0.5,
            # Scale for angular velocity (rad/s)
            'scale_angular': 1.0,
        }],
        # Remap to /cmd_vel if needed (default is /cmd_vel)
        remappings=[],
    )

    return LaunchDescription([
        teleop_node,
    ])
