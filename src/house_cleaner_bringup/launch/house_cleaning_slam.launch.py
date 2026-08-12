from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from launch.substitutions import LaunchConfiguration
import os

def generate_launch_description():
    BRINGUP = get_package_share_directory('house_cleaner_bringup')

    return LaunchDescription([
        # Run fake_sim (no Gazebo smoke test: odom + scan from the fake sim)
        Node(
            package='house_cleaner_bringup', executable='fake_sim',
            name='house_cleaning_fake_sim', output='screen',
        ),

        # SLAM: async slam_toolbox builds /map from /scan + odom TF
        Node(
            package='slam_toolbox', executable='async_slam_toolbox_node',
            name='slam_toolbox', output='screen',
            parameters=[
                os.path.join(BRINGUP, 'config', 'slam_toolbox_params.yaml'),
            ],
        ),

        # slam_toolbox is a lifecycle node — configure+activate it directly.
        # NOT via nav2_lifecycle_manager: slam_toolbox inherits plain
        # rclcpp_lifecycle::LifecycleNode (no BondServer), so the manager's
        # bond client can never connect and always logs "unable to be reached
        # by bond ... Aborting bringup". Wait on EACH transition succeeding
        # (120x1s each) — a single-shot get-then-set races a late-registering
        # node under startup load and wedges the mission forever (mod-16).
        ExecuteProcess(
            cmd=['bash', '-c',
                 'for i in $(seq 1 120); do '
                 'ros2 lifecycle set /slam_toolbox configure >/dev/null 2>&1 && break; '
                 'sleep 1; done; '
                 'for j in $(seq 1 120); do '
                 'ros2 lifecycle set /slam_toolbox activate >/dev/null 2>&1 && break; '
                 'sleep 1; done'],
            output='screen',
        ),
    ])