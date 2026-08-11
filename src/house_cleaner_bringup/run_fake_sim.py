#!/usr/bin/env python3
"""Direct runner for house_cleaning_fake_sim.launch.py that sets up environment correctly."""
import os
import sys
import signal

# Handle termination signals gracefully
def signal_handler(signum, frame):
    print(f"\n[run_fake_sim] Received signal {signum}, shutting down...", file=sys.stderr)
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Set up environment before any ROS 2 imports
os.environ['TURTLEBOT3_MODEL'] = 'burger'
os.environ['AMENT_PREFIX_PATH'] = '/home/koko/house_cleaner_ws/install:' + os.environ.get('AMENT_PREFIX_PATH', '/opt/ros/jazzy')
os.environ['ROS_PACKAGE_PATH'] = '/home/koko/house_cleaner_ws/install/share:' + os.environ.get('ROS_PACKAGE_PATH', '/opt/ros/jazzy/share')

# Add workspace to Python path
sys.path.insert(0, '/home/koko/house_cleaner_ws/install/house_cleaner_bringup/lib/python3.12/site-packages')

# Now import and run the launch file
from launch import LaunchService
exec(compile(open('/home/koko/house_cleaner_ws/src/house_cleaner_bringup/launch/house_cleaning_fake_sim.launch.py').read(), 'launch.py', 'exec'))

if __name__ == '__main__':
    ld = generate_launch_description()
    ls = LaunchService()
    ls.include_launch_description(ld)
    sys.exit(ls.run())