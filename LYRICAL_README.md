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

### Prerequisites

ROS2 Lyrical must be installed at `/opt/ros/lyrical/`. The build requires catkin_pkg for Python 3.11.

### Build

```bash
# Install catkin_pkg for the Python version used by ROS2 Lyrical
/usr/bin/python3 -m pip install --user catkin_pkg

# Or use uv
uv pip install catkin_pkg

# Build the workspace
source /opt/ros/lyrical/setup.bash
cd /home/koko/house_cleaner_ws
colcon build --symlink-install --packages-select house_cleaner_bringup
```

### Run

```bash
# Source environment
source /opt/ros/lyrical/setup.bash
source /home/koko/house_cleaner_ws/env.sh

# Launch fake simulation
ros2 launch house_cleaner_bringup house_cleaning_fake_sim_lyrical.launch.py
```

### Alternative: Run Python Module Directly

If colcon build fails, you can run the module directly (requires ROS2 to be sourced):

```bash
source /opt/ros/lyrical/setup.bash
cd /home/koko/house_cleaner_ws
PYTORCH_HOME=/dev/null  # Disable torch if present
python3 src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical.py &
ros2 run tf2_tools view_frames.py &
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
- `LYRICAL_README.md` - This file

## Troubleshooting

### "Package 'house_cleaner_bringup' not found"

Run `source env.sh` after sourcing ROS2:
```bash
source /opt/ros/lyrical/setup.bash
source /home/koko/house_cleaner_ws/env.sh
```

### "ModuleNotFoundError: No module named 'catkin_pkg'"

Install catkin_pkg:
```bash
/usr/bin/python3 -m pip install --user catkin_pkg
```

Or rebuild after installing:
```bash
rm -rf build/house_cleaner_bringup install/house_cleaner_bringup
colcon build --symlink-install --packages-select house_cleaner_bringup
```

### "python3.11 command not found"

The Lyrical ROS2 uses Python 3.11 from uv. If missing:
```bash
uv tool install python3.11 --python-preference=cpython
```

## TODO

- [ ] Full Nav2 integration (requires nav2 packages)
- [ ] SLAM integration
- [ ] Gazebo simulation
- [ ] Battery management node
- [ ] Auto-docking behavior