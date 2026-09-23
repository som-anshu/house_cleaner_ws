#!/usr/bin/env python3
# =============================================================================
# house_cleaning.launch.py - Single entry point for the house cleaner robot
# =============================================================================
# Launches the full autonomous cleaning stack.  The SAME launch file drives
# the Gazebo Harmonic simulation and the real TurtleBot3 Burger:
#
#   mode:=sim      Gazebo Harmonic + slam_toolbox (live map) + Nav2 (SLAM
#                  mode) + battery_sim + docking_controller + supervisor
#   mode:=real     hardware bringup (use_sim_time:=false) + map_server/amcl
#                  + battery_hw + docking_controller + supervisor
#
# GUI: Gazebo / RViz2 windows are X11/Wayland forwarded by the docker
# launcher; ``headless:=true`` runs Gazebo server-only (fully functional,
# Foxglove still available).  ``gui:=false`` skips RViz2 + Foxglove.
#
# Examples:
#   ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim
#   ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim headless:=true
#   ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=real gui:=true
# =============================================================================

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import AndSubstitution
from launch.substitutions import EqualsSubstitution, LaunchConfiguration, NotSubstitution
from launch_ros.actions import Node

BRINGUP = get_package_share_directory('house_cleaner_bringup')
NAV2_PARAMS = os.path.join(BRINGUP, 'config', 'nav2_params.yaml')
SLAM_PARAMS = os.path.join(BRINGUP, 'config', 'slam_toolbox_gazebo_params.yaml')


def _is(mode):
    """IfCondition predicate: 'true' when the launch mode matches, else 'false'."""
    return EqualsSubstitution(LaunchConfiguration('mode'), mode)


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    headless = LaunchConfiguration('headless')
    gui = LaunchConfiguration('gui')

    # These LaunchConfiguration objects are used below inside Node params;
    # ROS resolves them at runtime against declared defaults.
    drain = LaunchConfiguration('battery_drain_rate')
    charge = LaunchConfiguration('battery_charge_rate')
    low = LaunchConfiguration('battery_low_threshold')
    target = LaunchConfiguration('battery_charge_target')
    strip = LaunchConfiguration('mission_strip_width')
    mission_loop = LaunchConfiguration('mission_loop')
    dock_x = LaunchConfiguration('dock_x')
    dock_y = LaunchConfiguration('dock_y')
    dock_yaw = LaunchConfiguration('dock_yaw')

    # --------------------------------------------------------- 1. Simulation
    gazebo_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(BRINGUP, 'launch', 'gazebo_house_cleaning.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'world': 'house_room.world',
            'x_pose': '0.0',
            'y_pose': '0.0',
            'headless': headless,
        }.items(),
        condition=IfCondition(_is('sim')),
    )

    # --------------------------------------------------- 2. SLAM (sim-only)
    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[SLAM_PARAMS],
        condition=IfCondition(_is('sim')),
    )

    # slam_toolbox is a lifecycle node — configure+activate directly.
    # Do NOT use nav2_lifecycle_manager: slam_toolbox inherits plain
    # rclcpp_lifecycle::LifecycleNode (no BondServer), so the manager's bond
    # client can never connect.  Wait on each transition (retry up to 120x1s)
    # to survive late node registration under startup load.
    slam_activate = ExecuteProcess(
        cmd=['bash', '-c',
             'for i in $(seq 1 120); do '
             'ros2 lifecycle set /slam_toolbox configure >/dev/null 2>&1 && break; '
             'sleep 1; done; '
             'for j in $(seq 1 120); do '
             'ros2 lifecycle set /slam_toolbox activate >/dev/null 2>&1 && break; '
             'sleep 1; done'],
        output='screen',
        condition=IfCondition(_is('sim')),
    )

    # --------------------------------------------- 3. Nav2 (mode-independent)
    # cmd_vel chain: controller_server -> /cmd_vel_nav -> velocity_smoother
    #   -> /cmd_vel_smoothed -> collision_monitor -> /cmd_vel -> robot.
    controller = Node(
        package='nav2_controller', executable='controller_server',
        name='controller_server', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
        remappings=[('cmd_vel', 'cmd_vel_nav')],
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
        # Behaviors (spin/backup/drive_on_heading) must go through the same
        # smoother + collision_monitor chain as controller_server — otherwise
        # they publish raw /cmd_vel and bypass the safety gate.
        remappings=[('cmd_vel', 'cmd_vel_nav')],
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
        remappings=[('cmd_vel', 'cmd_vel_nav')],
    )
    # Last node before /cmd_vel — the collision monitor safety gate.
    collision_monitor = Node(
        package='nav2_collision_monitor', executable='collision_monitor',
        name='collision_monitor', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
    )

    # Nav2 lifecycle bringup via bash retry loop (NOT nav2_lifecycle_manager).
    # The manager calls get_state() with a 2s default timeout; under cold-boot
    # load (8 nodes + Gazebo + RViz) the target node's executor can be busy in
    # on_configure, so the call times out and the manager aborts the whole
    # bringup.  Retrying each transition up to 120x1s makes a busy executor
    # only delay, never abort — the same pattern already proven for
    # slam_toolbox above.  Prints a readiness marker for run_docker.sh.
    nav2_nodes = [
        'controller_server', 'smoother_server', 'planner_server',
        'behavior_server', 'bt_navigator', 'waypoint_follower',
        'velocity_smoother', 'collision_monitor',
    ]
    nav2_bringup_cmds = []
    for n in nav2_nodes:
        nav2_bringup_cmds.append(
            f'for i in $(seq 1 120); do '
            f'ros2 lifecycle set /{n} configure >/dev/null 2>&1 && break; '
            f'sleep 1; done; '
            f'for j in $(seq 1 120); do '
            f'ros2 lifecycle set /{n} activate >/dev/null 2>&1 && break; '
            f'sleep 1; done; '
        )
    nav2_bringup_cmds.append('echo "Nav2 lifecycle bringup complete"')
    nav2_activate = ExecuteProcess(
        cmd=['bash', '-c', ' '.join(nav2_bringup_cmds)],
        output='screen',
    )

    # ------------------------------------------------------ 3b. Localization
    # mode:=real uses a prebuilt map + AMCL instead of live SLAM.  Requires
    # the TurtleBot3 bringup driver (OpenCR, LDS) as a separate process.
    map_file = LaunchConfiguration('map')
    map_server = Node(
        package='nav2_map_server', executable='map_server',
        name='map_server', output='screen',
        parameters=[NAV2_PARAMS, {
            'use_sim_time': use_sim_time,
            'yaml_filename': map_file,
        }],
        condition=IfCondition(_is('real')),
    )
    amcl = Node(
        package='nav2_amcl', executable='amcl',
        name='amcl', output='screen',
        parameters=[NAV2_PARAMS, {'use_sim_time': use_sim_time}],
        condition=IfCondition(_is('real')),
    )
    lifecycle_manager_local = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_localization', output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'autostart': True,
            'autostart_delay': 5.0,
            'node_names': ['map_server', 'amcl'],
        }],
        condition=IfCondition(_is('real')),
    )

    # ------------------------------------------ 4. Battery (sim vs real)
    battery_sim = Node(
        package='house_cleaner_battery',
        executable='battery_sim',
        name='battery',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'drain_rate': drain,
            'charge_rate': charge,
            'low_threshold': low,
            'charge_target': target,
        }],
        condition=IfCondition(_is('sim')),
    )
    battery_hw = Node(
        package='house_cleaner_battery',
        executable='battery_hw',
        name='battery',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(_is('real')),
    )

    # -------------------------------------------------- 5. Docking controller
    docking = Node(
        package='house_cleaner_docking',
        executable='docking_controller',
        name='docking_controller',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            # Publish on the Nav2 smoothed chain (/cmd_vel_nav) so the creep
            # passes through velocity_smoother + collision_monitor like every
            # other command.  When the front polygon stop fires at the dock
            # (~0.15 m), the controller's stall/window latches "seated" —
            # collision monitor acts as the last-resort bumper.
            'velocity_topic': '/cmd_vel_nav',
        }],
    )

    # ---------------------------------------------------- 6. Mission supervisor
    supervisor = Node(
        package='house_cleaner_mission',
        executable='mission_supervisor',
        name='mission_supervisor',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'battery.low_threshold': low,
            'battery.charge_target': target,
            'mission.strip_width': strip,
            'mission.loop': mission_loop,
            'mission.return_budget': LaunchConfiguration('mission_return_budget'),
            'dock.x': dock_x,
            'dock.y': dock_y,
            'dock.yaw': dock_yaw,
        }],
    )

    # ---------------------------------------------------------------- 7. GUI
    rviz2 = Node(
        package='rviz2', executable='rviz2', name='rviz2', output='screen',
        arguments=['-d', os.path.join(BRINGUP, 'config', 'house_cleaning.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
        # No X display when headless — rviz2 would SIGABRT.  GUI windows only
        # when gui:=true AND not headless.
        condition=IfCondition(AndSubstitution(
            LaunchConfiguration('gui'), NotSubstitution(headless))),
    )
    foxglove = Node(
        package='foxglove_bridge', executable='foxglove_bridge',
        name='foxglove_bridge', output='screen',
        parameters=[{
            'port': 8765, 'address': '0.0.0.0',
            'num_threads': 2, 'max_qos_depth': 10,
        }],
        condition=IfCondition(gui),
    )

    ld = LaunchDescription()
    for arg in _declare_args():
        ld.add_action(arg)
    ld.add_action(gazebo_include)
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
    ld.add_action(nav2_activate)
    ld.add_action(map_server)
    ld.add_action(amcl)
    ld.add_action(lifecycle_manager_local)
    ld.add_action(battery_sim)
    ld.add_action(battery_hw)
    ld.add_action(docking)
    ld.add_action(supervisor)
    ld.add_action(rviz2)
    ld.add_action(foxglove)
    return ld


def _declare_args():
    return [
        DeclareLaunchArgument('mode', default_value='sim',
                              description='sim (Gazebo) or real (hardware)'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('battery_drain_rate', default_value='0.20'),
        DeclareLaunchArgument('battery_charge_rate', default_value='0.80'),
        DeclareLaunchArgument('battery_low_threshold', default_value='40.0'),
        DeclareLaunchArgument('battery_charge_target', default_value='95.0'),
        DeclareLaunchArgument('mission_strip_width', default_value='0.45'),
        DeclareLaunchArgument(
            'mission_loop', default_value='false',
            description='true: after final dock, undock and run coverage again'),
        DeclareLaunchArgument(
            'mission_return_budget', default_value='180.0',
            description='Wall-clock seconds for the whole RETURNING nav phase'),
        DeclareLaunchArgument('dock_x', default_value='0.0'),
        DeclareLaunchArgument('dock_y', default_value='2.75'),
        DeclareLaunchArgument('dock_yaw', default_value='1.57079632679'),
        DeclareLaunchArgument(
            'map', default_value='',
            description='Map YAML for real mode (mode:=real map:=/path/map.yaml)'),
    ]