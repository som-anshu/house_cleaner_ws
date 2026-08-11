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

        # slam_toolbox is a lifecycle node - auto configure+activate it
        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='lifecycle_manager_slam', output='screen',
            parameters=[
                {'use_sim_time': use_sim_time},
                {'autostart': True},
                {'autostart_delay': 3.0},
                {'node_names': ['slam_toolbox']},
            ],
        ),
    ])
