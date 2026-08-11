from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
import os

def generate_launch_description():
    autostart_delay = LaunchConfiguration('autostart_delay', default='15.0')
    BRINGUP = get_package_share_directory('house_cleaner_bringup')
    nav_params_file = LaunchConfiguration(
        'nav_params_file',
        default=os.path.join(BRINGUP, 'config', 'nav2_params.yaml'))

    use_sim_time = False

    return LaunchDescription([
        DeclareLaunchArgument('autostart_delay', default_value='15.0'),
        DeclareLaunchArgument(
            'nav_params_file',
            default_value=os.path.join(BRINGUP, 'config', 'nav2_params.yaml')),

        # Run fake_sim as a process with command line args
        Node(
            package='house_cleaner_bringup', executable='fake_sim',
            name='house_cleaning_fake_sim', output='screen',
        ),

        Node(
            package='nav2_map_server', executable='map_server',
            name='map_server', output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                {'yaml_filename': os.path.join(BRINGUP, 'config', 'house_room_map.yaml')},
                {'topic_name': 'map'},
                {'frame_id': 'map'},
            ],
        ),
        
        Node(
            package='nav2_amcl', executable='amcl',
            name='amcl', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
                {'initial_pose.x': 0.0},
                {'initial_pose.y': 0.0},
                {'initial_pose.yaw': 0.0},
                {'base_frame_id': 'base_footprint'},
            ],
        ),
        
        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='lifecycle_manager_localization', output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                {'autostart': True},
                {'autostart_delay': 3.0},
                {'node_names': ['map_server', 'amcl']},
            ],
        ),
        
        Node(
            package='nav2_controller', executable='controller_server',
            name='controller_server', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
                {'controller_frequency': 20.0},
                {'base_frame_id': 'base_footprint'},
            ],
        ),
        
        Node(
            package='nav2_planner', executable='planner_server',
            name='planner_server', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
                {'base_frame_id': 'base_footprint'},
            ],
        ),
        
        Node(
            package='nav2_behaviors', executable='behavior_server',
            name='behavior_server', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),
        
        Node(
            package='nav2_bt_navigator', executable='bt_navigator',
            name='bt_navigator', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
                {'base_frame_id': 'base_footprint'},
            ],
        ),
        
        Node(
            package='nav2_waypoint_follower', executable='waypoint_follower',
            name='waypoint_follower', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),
        
        Node(
            package='nav2_velocity_smoother', executable='velocity_smoother',
            name='velocity_smoother', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),
        
        Node(
            package='nav2_smoother', executable='smoother_server',
            name='smoother_server', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),

        Node(
            package='nav2_collision_monitor', executable='collision_monitor',
            name='collision_monitor', output='screen',
            parameters=[
                nav_params_file,
                {'use_sim_time': use_sim_time},
            ],
        ),

        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='lifecycle_manager_navigation', output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                {'autostart': True},
                {'autostart_delay': autostart_delay},
                {'node_names': [
                    'smoother_server', 'controller_server', 'planner_server',
                    'behavior_server', 'bt_navigator', 'waypoint_follower',
                    'velocity_smoother', 'collision_monitor',
                ]},
            ],
        ),
    ])