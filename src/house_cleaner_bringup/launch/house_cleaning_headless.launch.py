#!/usr/bin/env python3
# =============================================================================
# house_cleaning_headless.launch.py
# =============================================================================
# Headless version of house_cleaning_auto.launch.py - no Gazebo GUI.
# Uses gazebo_house_cleaning_headless.launch.py for server-only Gazebo.
# =============================================================================

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

BRINGUP = get_package_share_directory('house_cleaner_bringup')
NAV2_PARAMS = os.path.join(BRINGUP, 'config', 'nav2_params.yaml')
SLAM_PARAMS = os.path.join(BRINGUP, 'config', 'slam_toolbox_gazebo_params.yaml')


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    drain = LaunchConfiguration('battery_drain_rate', default='0.20')
    charge = LaunchConfiguration('battery_charge_rate', default='0.80')
    low = LaunchConfiguration('battery_low_threshold', default='35.0')
    target = LaunchConfiguration('battery_charge_target', default='95.0')
    strip = LaunchConfiguration('mission_strip_width', default='0.35')

    # 1. Gazebo: server only (no GUI)
    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning_headless.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'world': 'house_room.world',
            'x_pose': '0.0',
            'y_pose': '0.0',
        }.items()
    )

    # 2. SLAM
    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[SLAM_PARAMS],
    )

    # slam_toolbox is a lifecycle node — configure+activate directly.
    # Do NOT use nav2_lifecycle_manager: slam_toolbox inherits plain
    # rclcpp_lifecycle::LifecycleNode (no BondServer), so the manager's bond
    # client can never connect. Wait on EACH transition succeeding (120x1s
    # each) — a single-shot get-then-set races a late-registering node under
    # startup load and wedges the mission forever.
    slam_activate = ExecuteProcess(
        cmd=['bash', '-c',
             'for i in $(seq 1 120); do '
             'ros2 lifecycle set /slam_toolbox configure >/dev/null 2>&1 && break; '
             'sleep 1; done; '
             'for j in $(seq 1 120); do '
             'ros2 lifecycle set /slam_toolbox activate >/dev/null 2>&1 && break; '
             'sleep 1; done'],
        output='screen',
    )

    # 3. Nav2 manual stack
    controller = Node(
        package='nav2_controller', executable='controller_server',
        name='controller_server', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
        remappings=[('/cmd_vel', 'cmd_vel_nav')],
    )
    smoother = Node(
        package='nav2_smoother', executable='smoother_server',
        name='smoother_server', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )
    planner = Node(
        package='nav2_planner', executable='planner_server',
        name='planner_server', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )
    behavior = Node(
        package='nav2_behaviors', executable='behavior_server',
        name='behavior_server', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )
    bt_navigator = Node(
        package='nav2_bt_navigator', executable='bt_navigator',
        name='bt_navigator', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )
    waypoint = Node(
        package='nav2_waypoint_follower', executable='waypoint_follower',
        name='waypoint_follower', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )
    vel_smoother = Node(
        package='nav2_velocity_smoother', executable='velocity_smoother',
        name='velocity_smoother', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
        remappings=[('/cmd_vel', 'cmd_vel_nav')],
    )

    lifecycle_manager = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'autostart_delay': 12.0,
            'node_names': [
                'controller_server', 'smoother_server', 'planner_server',
                'behavior_server', 'bt_navigator', 'waypoint_follower',
                'velocity_smoother',
            ],
        }],
    )

    # 4. House cleaner assistant
    assistant = Node(
        package='house_cleaner_bringup',
        executable='house_cleaner_assistant',
        name='house_cleaner_assistant',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'battery.drain_rate': drain,
            'battery.charge_rate': charge,
            'battery.low_threshold': low,
            'battery.charge_target': target,
            'mission.strip_width': strip,
        }],
    )

    # 5. Foxglove Bridge
    foxglove_bridge = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        output='screen',
        parameters=[{
            'port': 8765,
            'address': '0.0.0.0',
            'num_threads': 2,
            'max_qos_depth': 10,
        }],
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock (must be true with Gazebo)'))
    ld.add_action(DeclareLaunchArgument(
        'battery_drain_rate', default_value='0.20',
        description='Battery drain %/s while driving'))
    ld.add_action(DeclareLaunchArgument(
        'battery_charge_rate', default_value='0.80',
        description='Battery charge %/s while docked'))
    ld.add_action(DeclareLaunchArgument(
        'battery_low_threshold', default_value='35.0',
        description='Battery % at which the robot returns to dock'))
    ld.add_action(DeclareLaunchArgument(
        'battery_charge_target', default_value='95.0',
        description='Battery % at which cleaning resumes'))
    ld.add_action(DeclareLaunchArgument(
        'mission_strip_width', default_value='0.35',
        description='Boustrophedon lane spacing (m)'))

    ld.add_action(gazebo_sim)
    ld.add_action(slam_toolbox)
    ld.add_action(slam_activate)
    ld.add_action(controller)
    ld.add_action(smoother)
    ld.add_action(planner)
    ld.add_action(behavior)
    ld.add_action(bt_navigator)
    ld.add_action(waypoint)
    ld.add_action(vel_smoother)
    ld.add_action(lifecycle_manager)
    ld.add_action(assistant)
    ld.add_action(foxglove_bridge)

    return ld