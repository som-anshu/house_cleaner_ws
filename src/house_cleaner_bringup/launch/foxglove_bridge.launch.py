#!/usr/bin/env python3
# =============================================================================
# foxglove_bridge.launch.py - Foxglove Bridge Launch File
# =============================================================================
# This launch file starts the Foxglove Bridge for web-based visualization.
# Foxglove Bridge allows you to view ROS2 topics in a web browser or the
# Foxglove desktop application.
#
# Usage:
#   ros2 launch house_cleaner_bringup foxglove_bridge.launch.py
#
# Access Foxglove:
#   1. Open browser to: http://localhost:8765
#   2. Or use Foxglove app: ws://localhost:8765
#   3. Select "Foxglove WebSocket" as the connection type
#   4. Enter: ws://localhost:8765
#
# Features:
#   - Real-time visualization of /map, /scan, /tf, /odom
#   - Battery state monitoring
#   - Robot model display
#   - Costmap visualization
# =============================================================================

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for Foxglove Bridge."""

    # Foxglove Bridge node
    # This creates a WebSocket server that Foxglove can connect to
    foxglove_node = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        output='screen',
        parameters=[{
            # Port for WebSocket server (default: 8765)
            'port': 8765,
            # Bind address (0.0.0.0 allows external connections)
            'address': '0.0.0.0',
            # Number of threads for handling connections
            'num_threads': 2,
            # Maximum QoS depth for topic subscriptions
            'max_qos_depth': 10,
            # Topics to exclude from publishing (optional)
            'exclude_topics': [],
            # Topics to include (empty = all topics)
            'include_topics': [],
            # Use compression for large messages
            'use_compression': True,
        }],
    )

    return LaunchDescription([
        foxglove_node,
    ])
