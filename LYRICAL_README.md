# House Cleaner Robot (ROS2 Lyrical Branch)

Autonomous room-cleaning robot simulation for **ROS 2 Lyrical**.

## Branch Info

- **main** - ROS 2 Jazzy with Nav2 (requires Nav2 packages)
- **lyrical** - ROS 2 Lyrical (self-contained implementation, no Nav2 dependency)

## Full Functionality NOW AVAILABLE in Lyrical

| Feature | Lyrical Status | Jazzy Status |
|---------|----------------|--------------|
| Odomety simulation | ✅ `/odom` | ✅ |
| 360° laser scan | ✅ `/scan` | ✅ |
| Velocity control | ✅ `/cmd_vel` | ✅ |
| TF transforms | ✅ Full chain | ✅ |
| Boustrophedon coverage | ✅ | ✅ |
| Battery simulation | ✅ `/battery_state` | ✅ |
| Auto-return to dock | ✅ | ✅ |
| Collision avoidance | ✅ Laser-based | ✅ Nav2 costmap |

## Key Difference: Architecture

**Lyrical**: Self-contained implementation
- No external Nav2/SLAM dependencies
- Direct `/cmd_vel` publishing for navigation
- Built-in battery management and charging logic

**Jazzy**: Nav2-integrated
- Requires `nav2_controller`, `nav2_planner`, `slam_toolbox`
- Action-based navigation (`/navigate_to_pose`)
- Lifecycle-managed nodes

## Quick Start (Full Functionality)

```bash
# Run complete cleaning simulation
source /opt/ros/lyrical/setup.bash
source /home/koko/house_cleaner_ws/env.sh

# Launch both simulation + assistant
ros2 launch house_cleaner_bringup house_cleaning_auto_lyrical.launch.py
```

## Components

1. **fake_sim_lyrical** (`fake_sim_lyrical.py`)
   - Publishes `/odom`, `/scan`
   - Simulates wall collisions
   - Provides TF: odom → base_footprint → base_link

2. **house_cleaner_assistant_lyrical** (`house_cleaner_assistant_lyrical.py`)
   - Generates boustrophedon coverage goals
   - Simple proportional navigation
   - Battery management with auto-docking
   - Publishes `/cmd_vel`, `/battery_state`

## Verification

```bash
# Check health
ros2 topic echo /odom --once
ros2 topic echo /scan --once
ros2 topic echo /battery_state --once

# Monitor cleaning progress
ros2 topic echo /current_goal --once

# Check robot pose
ros2 topic echo /odom -n 3
```

## Run Script

```bash
bash /home/koko/run_house_cleaner.sh
```

## GitHub Links

- Main repo: https://github.com/som-anshu/house_cleaner_ws
- Lyrical branch: https://github.com/som-anshu/house_cleaner_ws/tree/lyrical
- PR: https://github.com/som-anshu/house_cleaner_ws/pull/new/lyrical