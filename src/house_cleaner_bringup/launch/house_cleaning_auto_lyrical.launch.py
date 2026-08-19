"""Launch file for Lyrical: fake_sim + house_cleaner_assistant (no Nav2).

This provides autonomous cleaning behavior without Nav2 dependency:
- fake_sim_lyrical publishes /odom, /scan, TF
- house_cleaner_assistant_lyrical publishes /cmd_vel, /battery_state
- Together they form a complete (simulated) cleaning robot
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """Generate launch description for Lyrical simulation with assistant."""
    
    return LaunchDescription([
        # Fake simulation for odometry + laser
        Node(
            package='house_cleaner_bringup',
            executable='fake_sim_lyrical',
            name='fake_sim_lyrical',
            output='screen',
            parameters=[{'use_sim_time': False}],
        ),
        
        # House cleaner assistant (autonomous cleaning without Nav2)
        Node(
            package='house_cleaner_bringup',
            executable='house_cleaner_assistant_lyrical',
            name='house_cleaner_assistant',
            output='screen',
            parameters=[
                {'battery.drain_rate': 0.12},
                {'battery.charge_rate': 1.20},
                {'battery.low_threshold': 35.0},
                {'battery.charge_target': 95.0},
                {'mission.strip_width': 0.60},
            ],
        ),
    ])