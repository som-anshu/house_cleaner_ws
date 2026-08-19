# House Cleaner Robot

Autonomous room-cleaning robot simulation for **ROS 2 Lyrical** (minimal build).

## Branch Info

- **main** - ROS 2 Jazzy with full Nav2 and SLAM stack
- **lyrical** - ROS 2 Lyrical (minimal build without Nav2/SLAM dependencies)

## What It Does

- **Autonomous coverage cleaning**: Plans boustrophedon cleanup goals
- **Fake simulation**: Synthetic odom + 360-ray laser for Nav2 testing
- **Battery simulation**: Published on `/battery_state`, triggers return-to-dock
- **Obstacle avoidance**: Costmap-based collision detection

## Lyrical-Specific Features

This branch provides a minimal simulation that works without Nav2:

- `/odom` - Odometry topic
- `/scan` - LaserScan (360 rays, 10m range)
- `/initialpose` - Initial pose publisher
- TF tree: `map` -> `odom` -> `base_footprint` -> `base_link` -> `base_scan`
- Static transforms: base_link -> imu

## Quick Start (Lyrical)

```bash
# Source environment
source /opt/ros/lyrical/setup.bash
source /home/koko/house_cleaner_ws/env.sh

# Launch fake simulation
ros2 launch house_cleaner_bringup house_cleaning_fake_sim_lyrical.launch.py
```

## Verify

```bash
# Topics
ros2 topic list | grep -E '/(cmd_vel|odom|scan|tf)'

# Listen to odom
ros2 topic echo /odom --once

# Listen to scan
ros2 topic echo /scan --once
```

## Files in this Branch

- `fake_sim_lyrical.py` - Minimal simulation (no Nav2 dependencies)
- `house_cleaning_fake_sim_lyrical.launch.py` - Launch file for the minimal sim
- `env.sh` - Updated for Lyrical paths

## TODO

- [ ] Full Nav2 integration (requires nav2 packages)
- [ ] SLAM integration
- [ ] Gazebo simulation
- [ ] Battery management node
- [ ] Auto-docking behavior