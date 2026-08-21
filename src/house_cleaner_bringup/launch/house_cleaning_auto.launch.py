#!/usr/bin/env python3
#
# house_cleaning_auto.launch.py
#
# COMPLETE AUTONOMOUS HOUSE-CLEANING DEMO — works in ANY unknown room:
#
#   Gazebo (house_room.world: furniture obstacles + charging dock)
#     + slam_toolbox (live SLAM mapping — no prebuilt map needed)
#     + Nav2 (manual stack, slam-mode: no map_server/amcl; slam_toolbox
#             publishes /map AND map->odom, so Nav2 plans on the live map)
#     + house_cleaner_assistant (boustrophedon coverage, battery sim,
#             low-battery return-to-dock, laser-guided docking, recharge)
#
# Usage:
#   export TURTLEBOT3_MODEL=burger
#   ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py
#
# Tuning (launch args): battery_drain_rate (0.20), battery_charge_rate (0.80),
# battery_low_threshold (35.0), battery_charge_target (95.0), headless (true)
#
# The robot spawns at world (0,0) yaw 0; slam_toolbox anchors the map frame
# there, so map coordinates == world coordinates. Dock is at (0.0, 2.75).

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
    headless = LaunchConfiguration('headless', default='true')
    drain = LaunchConfiguration('battery_drain_rate', default='0.20')
    charge = LaunchConfiguration('battery_charge_rate', default='0.80')
    low = LaunchConfiguration('battery_low_threshold', default='35.0')
    target = LaunchConfiguration('battery_charge_target', default='95.0')
    # Mission parameters for cleaning navigation
    strip = LaunchConfiguration('mission_strip_width', default='0.35')  # Reduced for tighter coverage between obstacles

    # 1. Gazebo: house room with obstacles + charging dock
    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'headless': headless,
            'world': 'house_room.world',
            'x_pose': '0.0',
            'y_pose': '0.0',
        }.items()
    )

    # 2. SLAM: async slam_toolbox builds /map from /scan + odom
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
    # client can never connect and always logs "unable to be reached by bond
    # ... Aborting bringup" no matter the bond_timeout. Wait for the node's
    # lifecycle service, then transition.
    #
    # Robustness: the node can register late under startup load (Gazebo+Nav2
    # starting simultaneously), so wait on EACH transition succeeding rather
    # than a single get-then-set race. 120 x 1s per transition == 2 min cap,
    # comfortably inside the assistant's 120s wait_for_map window.
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

    # 3. Nav2 manual stack (slam mode). cmd_vel chain (verified live):
    #    controller_server -> /cmd_vel_nav -> velocity_smoother
    #    -> /cmd_vel_smoothed -> collision_monitor -> /cmd_vel -> gz bridge
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
    collision_monitor = Node(
        package='nav2_collision_monitor', executable='collision_monitor',
        name='collision_monitor', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
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

    # 4. The cleaning supervisor: coverage + battery + docking
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

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock (must be true with Gazebo)'))
    ld.add_action(DeclareLaunchArgument(
        'headless', default_value='true',
        description='true = no Gazebo GUI'))
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
    # Mission parameters for closer wall/furniture navigation
    ld.add_action(DeclareLaunchArgument(
        'mission_strip_width', default_value='0.35',
        description='Boustrophedon lane spacing (m) — smaller = tighter coverage near obstacles'))

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
    ld.add_action(collision_monitor)
    ld.add_action(lifecycle_manager)
    ld.add_action(assistant)

    return ld
