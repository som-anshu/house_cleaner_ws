from setuptools import setup, find_packages
import os

setup(
    name='house_cleaner_bringup',
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/house_cleaner_bringup']),
        ('share/house_cleaner_bringup', ['package.xml']),
        ('share/house_cleaner_bringup/config', [
            'config/burger_bridge.yaml',
            'config/nav2_params.yaml',
            'config/slam_toolbox_params.yaml',
            'config/slam_toolbox_gazebo_params.yaml',
            'config/house_room_map.yaml',
            'config/house_room_map.pgm']),
        ('share/house_cleaner_bringup/launch', [
            'launch/house_cleaning_fake_sim.launch.py',
            'launch/gazebo_house_cleaning.launch.py',
            'launch/house_cleaning_slam.launch.py',
            'launch/house_cleaning_gazebo_slam.launch.py',
            'launch/house_cleaning_gazebo_nav.launch.py',
            'launch/house_cleaning_auto.launch.py',
        ]),
        ('share/house_cleaner_bringup/worlds', [
            'worlds/house_room.world',
        ]),
        ('share/house_cleaner_bringup/models/wall', [
            'models/wall/model.config',
            'models/wall/model.sdf',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='koko',
    maintainer_email='koko@example.com',
    description='House cleaner bringup',
    license='MIT',
    tests_require=['pytest'],
    test_suite='test',
    entry_points={
        'console_scripts': [
            'house_cleaner_assistant = house_cleaner_bringup.house_cleaner_assistant:main',
        ],
    },
)
