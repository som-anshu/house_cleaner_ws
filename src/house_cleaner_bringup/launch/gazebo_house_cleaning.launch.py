from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    house_cleaner_pkg = '/home/koko/house_cleaner_ws/src/house_cleaner_bringup'
    fake_sim_launch = os.path.join(house_cleaner_pkg, 'launch', 'house_cleaning_fake_sim.launch.py')
    
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(fake_sim_launch),
        ),
    ])
