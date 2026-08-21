#!/usr/bin/env python3
#
# house_cleaning_gazebo_nav_manual.launch.py
#
# Full Nav2 stack on Gazebo with a PREBUILT map — no nav2_bringup needed.
# Mirrors what nav2_bringup's bringup_launch.py does, but with the manual
# node pattern proven in this repo (house_cleaning_auto.launch.py /
# house_cleaning_fake_sim.launch.py): map_server + amcl + Nav2 nodes,
# managed by two lifecycle managers.
#
#   export TURTLEBOT3_MODEL=burger
#   ros2 launch house_cleaner_bringup house_cleaning_gazebo_nav_manual.launch.py
#
# The map ships with the package at config/house_room_map.yaml. The robot
# spawns at world (0,0) yaw 0, which is also amcl's initial_pose, so
# localization converges instantly. Override with map:=/path/to/other_map.yaml.
#
# cmd_vel chain (verified): controller_server -> cmd_vel_nav ->
# velocity_smoother -> cmd_vel_smoothed -> collision_monitor -> cmd_vel
# -> gz bridge (plain geometry_msgs/Twist).

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

BRINGUP = get_package_share_directory('house_cleaner_bringup')
NAV2_PARAMS = os.path.join(BRINGUP, 'config', 'nav2_params.yaml')


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    map_yaml = LaunchConfiguration(
        'map',
        default=os.path.join(BRINGUP, 'config', 'house_room_map.yaml'),
    )
    drain = LaunchConfiguration('battery_drain_rate', default='0.20')
    charge = LaunchConfiguration('battery_charge_rate', default='0.80')
    low = LaunchConfiguration('battery_low_threshold', default='35.0')
    target = LaunchConfiguration('battery_charge_target', default='95.0')

    # 1. Gazebo: house room with obstacles + charging dock
    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'world': 'house_room.world',
            'x_pose': '0.0',
            'y_pose': '0.0',
        }.items()
    )

    # 2. Localization: static map + amcl (instant, no SLAM wait)
    map_server = Node(
        package='nav2_map_server', executable='map_server',
        name='map_server', output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'yaml_filename': map_yaml},
            {'topic_name': 'map'},
            {'frame_id': 'map'},
        ],
    )

    amcl = Node(
        package='nav2_amcl', executable='amcl',
        name='amcl', output='screen',
        parameters=[
            NAV2_PARAMS,
            {'use_sim_time': use_sim_time},
            {'initial_pose.x': 0.0},
            {'initial_pose.y': 0.0},
            {'initial_pose.yaw': 0.0},
            {'base_frame_id': 'base_footprint'},
        ],
    )

    # 3. Nav2 manual stack. cmd_vel chain:
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

    lifecycle_manager_localization = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_localization', output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'autostart_delay': 5.0,
            'node_names': ['map_server', 'amcl'],
        }],
    )

    lifecycle_manager_navigation = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'autostart_delay': 12.0,
            'node_names': [
                'controller_server', 'smoother_server', 'planner_server',
                'behavior_server', 'bt_navigator', 'waypoint_follower',
                'velocity_smoother', 'collision_monitor',
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
        }],
    )

    ld = LaunchDescription()
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo /clock (must be true with Gazebo)'))
    ld.add_action(DeclareLaunchArgument(
        'map', default_value=os.path.join(BRINGUP, 'config', 'house_room_map.yaml'),
        description='Prebuilt map yaml for localization'))
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

    ld.add_action(gazebo_sim)
    ld.add_action(map_server)
    ld.add_action(amcl)
    ld.add_action(controller)
    ld.add_action(smoother)
    ld.add_action(planner)
    ld.add_action(behavior)
    ld.add_action(bt_navigator)
    ld.add_action(waypoint)
    ld.add_action(vel_smoother)
    ld.add_action(collision_monitor)
    ld.add_action(lifecycle_manager_localization)
    ld.add_action(lifecycle_manager_navigation)
    ld.add_action(assistant)

    return ld