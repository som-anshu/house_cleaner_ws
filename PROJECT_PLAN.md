# House Cleaner Robot - Complete Overhaul Plan

## Executive Summary

This plan transforms the `house_cleaner_ws` project from a mixed ROS2 Lyrical/Jazzy codebase into a clean, Docker-based ROS2 Jazzy project with full GUI simulation (Gazebo Harmonic + Nav2 + RViz2 + Foxglove). The target is a TurtleBot3 Burger simulation ready for real robot deployment.

---

## Current State Analysis

### Issues Identified

1. **Lyrical Code Contamination**: 6+ files with "lyrical" references targeting an older ROS2 version
2. **Mixed Docker/Native Paths**: Conflicting setup approaches
3. **Redundant Launch Files**: 8+ launch files, many overlapping
4. **Missing Foxglove Integration**: No foxglove_bridge setup
5. **Incomplete Dockerfile**: Minimal, missing GUI dependencies
6. **GUI Not Functional**: Docker setup lacks proper X11/OpenGL support
7. **Missing Dependencies**: package.xml incomplete for Jazzy
8. **No RViz2 Config**: Custom lyrical.rviz, no proper Jazzy RViz config

### Files to Remove (Lyrical/Legacy)

```
LYRICAL_JAZZY_PLAN.md
lyrical.rviz
run_house_cleaner.sh
src/house_cleaner_bringup/house_cleaner_bringup/house_cleaner_assistant_lyrical.py
src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical.py
src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py
src/house_cleaner_bringup/launch/house_cleaning_auto_lyrical.launch.py
src/house_cleaner_bringup/launch/house_cleaning_fake_sim_lyrical.launch.py
src/house_cleaner_bringup/launch/house_cleaning_fake_sim.launch.py  (redundant)
src/house_cleaner_bringup/launch/house_cleaning_slam.launch.py  (redundant)
src/house_cleaner_bringup/launch/house_cleaning_gazebo_slam.launch.py  (redundant)
src/house_cleaner_bringup/launch/house_cleaning_gazebo_nav.launch.py  (use nav2_bringup)
src/house_cleaner_bringup/launch/house_cleaning_gazebo_nav_manual.launch.py  (redundant)
src/house_cleaner_bringup/config/slam_toolbox_params.yaml  (use gazebo version)
src/house_cleaner_bringup/config/house_room_map.yaml  (use SLAM instead)
src/house_cleaner_bringup/config/house_room_map.pgm  (use SLAM instead)
src/house_cleaner_bringup/scripts/verify_scan_forward_index.py  (debug tool)
scripts/kill_house_cleaner.sh  (move to src/scripts/)
test_portability.sh  (remove, no longer needed)
```

### Files to Keep/Improve

```
Dockerfile  → Major rewrite for GUI support
docker-compose.yml  → Rewrite with X11 forwarding
run_docker.sh  → Update for GUI and Foxglove
entrypoint.sh  → Update for full stack launch
env.sh  → Simplify (remove lyrical fallback)
src/house_cleaner_bringup/house_cleaner_bringup/house_cleaner_assistant.py  → Keep as-is (solid code)
src/house_cleaner_bringup/house_cleaner_bringup/fake_sim.py  → Keep as-is
src/house_cleaner_bringup/launch/house_cleaning_auto.launch.py  → Keep (main launch)
src/house_cleaner_bringup/launch/gazebo_house_cleaning.launch.py  → Keep
src/house_cleaner_bringup/config/nav2_params.yaml  → Keep (well-tuned)
src/house_cleaner_bringup/config/slam_toolbox_gazebo_params.yaml  → Keep
src/house_cleaner_bringup/config/burger_bridge.yaml  → Keep (correct cmd_vel bridge)
src/house_cleaner_bringup/worlds/house_room.world  → Keep
src/house_cleaner_bringup/scripts/battery_monitor.py  → Keep
src/house_cleaner_bringup/models/  → Keep
```

---

## Implementation Plan

### Phase 1: Clean Lyrical Code (Remove Legacy)

**Step 1.1: Delete Lyrical Files**
- Remove all files listed in "Files to Remove" section
- Remove lyrical references from `setup.py` and `CMakeLists.txt`
- Update `setup.py` data_files to remove deleted launch files
- Update `setup.py` entry_points to remove lyrical executables

**Step 1.2: Clean env.sh**
- Remove Lyrical fallback logic
- Keep only Jazzy path
- Simplify to:
```bash
#!/usr/bin/env bash
_WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
if [ -d "${_WS_DIR}/install" ]; then
    source "${_WS_DIR}/install/setup.bash"
fi
```

### Phase 2: Docker Infrastructure (GUI-Ready)

**Step 2.1: Rewrite Dockerfile**
- Base: `ros:jazzy-ros-base`
- Install: All Nav2 packages, Gazebo Harmonic, slam_toolbox, turtlebot3_gazebo
- Install: X11 utils, Mesa OpenGL, foxglove_bridge
- Build workspace with colcon
- Set proper environment variables
- Entry point for full GUI stack

**Step 2.2: Rewrite docker-compose.yml**
- X11 socket mounting (`/tmp/.X11-unix`)
- DISPLAY environment variable
- Software rendering (LIBGL_ALWAYS_SOFTWARE=1)
- Shared memory for Gazebo (`/dev/shm`)
- Volume mounts for workspace

**Step 2.3: Update run_docker.sh**
- Auto-detect display
- Set X11 permissions (`xhost +local:docker`)
- Launch with GUI support
- Add `--build` flag for rebuilds
- Add Foxglove port mapping (8765)

**Step 2.4: Update entrypoint.sh**
- Launch full Gazebo + SLAM + Nav2 + Assistant stack
- Include Foxglove bridge node
- Include RViz2 launch option

### Phase 3: Launch Files (Simplified)

**Step 3.1: Main Launch File (house_cleaning_auto.launch.py)**
- Keep existing (works well)
- Add RViz2 node option
- Add Foxglove bridge node

**Step 3.2: Create foxglove_bridge.launch.py**
```python
# Foxglove bridge for web-based visualization
foxglove_node = Node(
    package='foxglove_bridge',
    executable='foxglove_bridge',
    name='foxglove_bridge',
    parameters=[{
        'port': 8765,
        'address': '0.0.0.0',
        'num_threads': 2,
        'max_qos_depth': 10,
    }],
)
```

**Step 3.3: Create rviz2.launch.py**
- Launch RViz2 with Nav2 config
- Subscribe to /map, /scan, /tf, /costmap
- Display robot model

### Phase 4: Foxglove Integration

**Step 4.1: Install foxglove_bridge in Dockerfile**
```dockerfile
RUN apt-get update && apt-get install -y \
    ros-jazzy-foxglove-bridge \
    && rm -rf /var/lib/apt/lists/*
```

**Step 4.2: Create Foxglove Config Panel**
- Create `config/foxglove_layout.json` for default panels
- Include: Map view, 3D view, laser scan, battery gauge

**Step 4.3: Document Foxglove Access**
- Connect via: `ws://localhost:8765`
- Or use Foxglove web app: https://app.foxglove.dev
- Import layout from `config/foxglove_layout.json`

### Phase 5: TurtleBot3 Burger Compatibility

**Step 5.1: Verify URDF**
- Ensure turtlebot3_description URDF is used
- Check TF tree: map → odom → base_footprint → base_link → laser_link

**Step 5.2: Verify Sensor Config**
- Laser: 360 rays, 0.12-3.5m range (Burger LDS)
- Odometry: DiffDrive from Gazebo plugin
- IMU: Published via bridge

**Step 5.3: Create Real Robot Launch**
- `bringup_real_robot.launch.py` for TurtleBot3 Burger
- Disable Gazebo, use real hardware interfaces
- Load Nav2 with saved map

### Phase 6: Documentation

**Step 6.1: Rewrite README.md**
- Quick Start (Docker)
- GUI Setup Instructions
- Foxglove Connection Guide
- Real Robot Deployment
- Troubleshooting

**Step 6.2: Create docs/ directory**
- `setup.md` - Environment setup
- `simulation.md` - Gazebo simulation guide
- `real_robot.md` - TurtleBot3 deployment
- `foxglove.md` - Visualization guide

---

## Final Directory Structure

```
house_cleaner_ws/
├── Dockerfile
├── docker-compose.yml
├── run_docker.sh
├── entrypoint.sh
├── env.sh
├── README.md
├── PROJECT_PLAN.md
├── src/
│   └── house_cleaner_bringup/
│       ├── CMakeLists.txt
│       ├── package.xml
│       ├── setup.py
│       ├── config/
│       │   ├── nav2_params.yaml
│       │   ├── slam_toolbox_gazebo_params.yaml
│       │   ├── burger_bridge.yaml
│       │   └── foxglove_layout.json
│       ├── launch/
│       │   ├── house_cleaning_auto.launch.py  (main)
│       │   ├── gazebo_house_cleaning.launch.py
│       │   ├── foxglove_bridge.launch.py
│       │   └── rviz2.launch.py
│       ├── worlds/
│       │   └── house_room.world
│       ├── models/
│       │   └── wall/
│       ├── house_cleaner_bringup/
│       │   ├── __init__.py
│       │   ├── house_cleaner_assistant.py
│       │   └── fake_sim.py
│       └── scripts/
│           ├── battery_monitor.py
│           └── kill_house_cleaner.sh
├── docs/
│   ├── setup.md
│   ├── simulation.md
│   ├── real_robot.md
│   └── foxglove.md
└── scripts/
    └── kill_house_cleaner.sh
```

---

## Implementation Order

1. **Phase 1** (30 min): Remove all lyrical code and clean references
2. **Phase 2** (1 hour): Rewrite Docker infrastructure for GUI
3. **Phase 3** (30 min): Simplify and update launch files
4. **Phase 4** (30 min): Integrate Foxglove bridge
5. **Phase 5** (30 min): Verify TurtleBot3 Burger compatibility
6. **Phase 6** (30 min): Write documentation

**Total Estimated Time: 3-4 hours**

---

## Validation Checklist

- [ ] Docker builds successfully
- [ ] Gazebo GUI launches and shows house_room.world
- [ ] TurtleBot3 Burger spawns at (0,0)
- [ ] SLAM builds map from /scan
- [ ] Nav2 navigates to goals
- [ ] Battery simulation works
- [ ] Auto-docking works
- [ ] RViz2 shows all topics
- [ ] Foxglove connects via web browser
- [ ] All topics publish correctly
- [ ] TF tree is complete
- [ ] Ready for real TurtleBot3 deployment

---

## Notes

- The existing `house_cleaner_assistant.py` is well-written and functional
- The `nav2_params.yaml` is well-tuned for MPPI controller
- The `burger_bridge.yaml` correctly bridges cmd_vel as Twist (not TwistStamped)
- The `house_room.world` has proper furniture layout and charging dock
- SLAM-based approach (no prebuilt map) is the right choice for unknown rooms
