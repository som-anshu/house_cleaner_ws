# House Cleaner Robot (ROS2 Lyrical Branch)

Autonomous room-cleaning robot simulation for **ROS 2 Lyrical** (minimal build).

## Branch Info

- **main** - ROS 2 Jazzy with full Nav2 and SLAM stack
- **lyrical** - ROS 2 Lyrical (minimal build without Nav2/SLAM dependencies)

## What It Does

- **Synthetic odometry**: `/odom` topic with robot position
- **360° laser scan**: `/scan` topic for obstacle detection
- **Velocity control**: Subscribe to `/cmd_vel` for movement
- **TF transforms**: odom -> base_footprint -> base_link <-> base_scan

## Quick Start

```bash
# Run the simulation
source /opt/ros/lyrical/setup.bash
python3 /home/koko/house_cleaner_ws/src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py &

# Verify topics
sleep 1
ros2 topic echo /odom --once
ros2 topic echo /scan --once
```

## Using the Run Script

```bash
bash /home/koko/run_house_cleaner.sh
```

## Files in this Branch

- `fake_sim_lyrical.py` - Core simulation node
- `fake_sim_lyrical_standalone.py` - Standalone version (recommended for Lyrical)
- `house_cleaning_fake_sim_lyrical.launch.py` - ROS2 launch file
- `env.sh` - Environment setup for Lyrical paths
- `LYRICAL_README.md` - This documentation

## Verification Output

When running, the simulation publishes:
- `/odom` - Odometry with position (x, y), orientation, and covariance
- `/scan` - LaserScan with 360 ranges (10m max, 0.1m min)
- TF transforms for robot frame tree

## Next Steps

To use with full Nav2 for autonomous navigation:
1. Install full Nav2 packages compatible with Lyrical
2. Build workspace with colcon
3. Use `ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py`

## GitHub

- Main repo: https://github.com/som-anshu/house_cleaner_ws
- Lyrical branch: https://github.com/som-anshu/house_cleaner_ws/tree/lyrical
- PR: https://github.com/som-anshu/house_cleaner_ws/pull/new/lyrical