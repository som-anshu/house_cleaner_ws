from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    use_sim_time = False

    return LaunchDescription([
        # Run fake_sim as a process with command line args
        ExecuteProcess(
            cmd=['python3',
                 '/home/koko/house_cleaner_ws/src/house_cleaner_bringup/house_cleaner_bringup/fake_sim.py'],
            name='house_cleaning_fake_sim',
            output='screen',
        ),

        # SLAM: async slam_toolbox builds /map from /scan + odom TF
        # (mirrors ROBOTIS tutorial "Run SLAM Node" step, cartographer -> slam_toolbox)
        Node(
            package='slam_toolbox', executable='async_slam_toolbox_node',
            name='slam_toolbox', output='screen',
            parameters=[
                '/home/koko/house_cleaner_ws/src/house_cleaner_bringup/config/slam_toolbox_params.yaml',
            ],
        ),

        # slam_toolbox is a lifecycle node — configure+activate it directly.
        # NOT via nav2_lifecycle_manager: slam_toolbox inherits plain
        # rclcpp_lifecycle::LifecycleNode (no BondServer), so the manager's
        # bond client can never connect and always logs "unable to be reached
        # by bond ... Aborting bringup". Wait for the node, then transition.
        ExecuteProcess(
            cmd=['bash', '-c',
                 'for i in $(seq 1 30); do '
                 'ros2 lifecycle get /slam_toolbox >/dev/null 2>&1 && break; '
                 'sleep 1; done; '
                 'ros2 lifecycle set /slam_toolbox configure; '
                 'sleep 1; '
                 'ros2 lifecycle set /slam_toolbox activate'],
            output='screen',
        ),
    ])
