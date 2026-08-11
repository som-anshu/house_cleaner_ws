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
            'config/nav2_params.yaml']),
        ('share/house_cleaner_bringup/launch', [
            'launch/house_cleaning_fake_sim.launch.py',
            'launch/gazebo_house_cleaning.launch.py',
        ]),
        ('share/house_cleaner_bringup/worlds', [
            'worlds/house_cleaner.world',
        ]),
        ('share/house_cleaner_bringup/models/wall', [
            'models/wall/model.config',
            'models/wall/model.sdf',
        ]),
        ('share/house_cleaner_bringup/models/wall/meshes', [
            'models/wall/meshes/wall.dae',
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
)