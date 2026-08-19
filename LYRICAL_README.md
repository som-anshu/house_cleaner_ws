# House Cleaner Robot (ROS2 Lyrical Branch)

Autonomous room-cleaning robot simulation for **ROS 2 Lyrical** (minimal build).

## Branch Info

- **main** - ROS 2 Jazzy with full Nav2 and SLAM stack
- **lyrical** - ROS 2 Lyrical (minimal build without Nav2/SLAM dependencies)

## Current Capabilities (Lyrical)

- ✓ **Synthetic odometry**: `/odom` topic with robot position
- ✓ **360° laser scan**: `/scan` topic for obstacle detection  
- ✓ **Velocity control**: Subscribe to `/cmd_vel` for movement
- ✓ **TF transforms**: odom -> base_footprint -> base_link <-> base_scan

## Missing for Full Jazzy Functionality

The full Jazzy version includes (but Lyrical lacks):

- ✗ Nav2: `nav2_controller`, `nav2_planner`, `nav2_amcl`, `nav2_map_server`, `nav2_bt_navigator`, etc.
- ✗ SLAM: `slam_toolbox` for live mapping
- ✗ Simulation bridge: `ros_gz_bridge` for Gazebo integration
- ✗ Assistant: `house_cleaner_assistant` with autonomous mission planning

## Quick Start (Simulation Only)

```bash
# Run the simulation
source /opt/ros/lyrical/setup.bash
python3 /home/koko/house_cleaner_ws/src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py &

# Verify topics
sleep 1
ros2 topic echo /odom --once
ros2 topic echo /scan --once
```

## For Full Nav2 Functionality

**Option 1: Install Nav2 packages** (if available for Lyrical)
```bash
# Check if available
apt search ros-lyrical-nav2  # or similar

# Install if found
sudo apt install ros-lyrical-nav2 ros-lyrical-slam-toolbox
```

**Option 2: Use Jazzy instead**
```bash
# Full Nav2/SLAM packages available in Jazzy
# Clone the main branch instead
git clone -b main git@github.com:som-anshu/house_cleaner_ws.git
source /opt/ros/jazzy/setup.bash
source env.sh
ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py
```

**Option 3: Manual installation** (advanced)
If you have Jazzy packages compatible with Lyrical's Python 3.14:
```bash
# Copy Jazzy packages to Lyrical location
sudo cp -r /opt/ros/jazzy/lib/python3.14/site-packages/nav2* /opt/ros/lyrical/lib/python3.14/site-packages/
```

## Files in this Branch

- `fake_sim_lyrical.py` - Core simulation node
- `fake_sim_lyrical_standalone.py` - Runs without colcon build
- `house_cleaning_fake_sim_lyrical.launch.py` - ROS2 launch file
- `env.sh` - Environment setup for Lyrical paths
- `run_house_cleaner.sh` - Convenience run script
- `LYRICAL_README.md` - This documentation

## Verification Output

```yaml
Topics:
  /odom     : Odometry (position, orientation, velocity)
  /scan     : LaserScan (360×10m range)
  /tf       : Transform tree
  /cmd_vel  : Velocity subscriber input

QoS:
  odom    : 10Hz publish rate
  scan    : 50Hz (20ms step)
```

## Comparison: Lyrical vs Jazzy

| Feature | Lyrical | Jazzy |
|---------|---------|-------|
| Basic simulation | ✓ | ✓ |
| Nav2 navigation | ✗ | ✓ |
| SLAM mapping | ✗ | ✓ |
| Auto-cleaning mission | ✗ | ✓ |
| Battery simulation | ✗ | ✓ |
| Auto-docking | ✗ | ✓ |
| Gazebo simulation | ✗ | ✓ |

## GitHub Links

- Main repo: https://github.com/som-anshu/house_cleaner_ws
- Lyrical branch: https://github.com/som-anshu/house_cleaner_ws/tree/lyrical  
- PR: https://github.com/som-anshu/house_cleaner_ws/pull/new/lyrical