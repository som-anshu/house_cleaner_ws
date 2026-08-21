# ROS2 Lyrical → Jazzy Compatibility Plan

## Environment Comparison

| Aspect | Lyrical | Jazzy |
|--------|---------|-------|
| Python | 3.14 | 3.12 |
| rmw | ? | cyclonedds |
| Nav2 | ❌ Not available | ✅ Full stack |
| SLAM | ❌ Not available | ✅ slam_toolbox |

## Package Availability

### Lyrical Packages (from /opt/ros/lyrical/lib/python3.14/site-packages):
- rclpy
- geometry_msgs
- sensor_msgs
- nav_msgs
- std_msgs
- tf2_ros
- action_tutorials_cpp
- action_tutorials_py
- demo_nodes_py

### Needed for Full Jazzy Functionality (NOT in Lyrical):
- nav2_msgs.action (NavigateToPose)
- nav2_controller
- nav2_planner  
- nav2_amcl
- nav2_map_server
- nav2_bt_navigator
- nav2_lifecycle_manager
- nav2_collision_monitor
- nav2_smoother
- nav2_velocity_smoother
- slam_toolbox

## Implementation Strategy

### Phase 1: Lyrical (COMPLETE)
**Approach**: Self-contained implementation without Nav2

1. fake_sim_lyrical_standalone.py
   - Publishes /odom, /scan
   - No external dependencies
   - Works immediately

2. house_cleaner_assistant_lyrical.py
   - Direct /cmd_vel publishing
   - Built-in navigation logic
   - Battery simulation

### Phase 2: Jazzy Integration (READY)
**Approach**: Nav2 action-based navigation

1. house_cleaner_assistant.py (already exists, Jazzy-compatible)
   - Uses nav2_msgs.action.NavigateToPose
   - ActionClient for goal submission
   - Lifecycle node management

2. house_cleaning_auto.launch.py
   - Launches all Nav2 nodes
   - Requires nav2_params.yaml
   - Requires prebuilt map

## Key Code Locations

- Lyrical implementation: house_cleaner_assistant_lyrical.py
- Jazzy implementation: house_cleaner_assistant.py (main)
- Fake simulation: fake_sim_lyrical_standalone.py
- Launch files: house_cleaning_auto_lyrical.launch.py

## Testing Verification

```bash
# Lyrical test
source /opt/ros/lyrical/setup.bash
python3 fake_sim_lyrical_standalone.py &
sleep 2
ros2 topic echo /odom --once
ros2 topic echo /scan --once

# Jazzy test requires building:
# source /opt/ros/jazzy/setup.bash  
# source env.sh
# ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py
```

## Limitations

Lyrical cannot run full Jazzy Nav2 without:
1. Installing Nav2 packages (not available in apt)
2. Manually copying Jazzy packages (Python 3.14 vs 3.12 compatibility issues)
3. Building from source (requires colcon + catkin_pkg)