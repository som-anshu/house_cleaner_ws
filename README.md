# House Cleaner Robot

Autonomous room-cleaning robot built on **ROS 2 Jazzy** with a **TurtleBot3 Burger** model. It cleans rooms autonomously using boustrophedon coverage, manages battery life, and returns to a charging dock when needed.

## What It Does

- **Autonomous coverage cleaning**: Plans a boustrophedon mission from the live SLAM map and executes it goal-by-goal through Nav2.
- **Live SLAM mapping**: Uses `slam_toolbox` in `mapping` mode to build an occupancy map in an unknown room — no prebuilt map required for the cleaning run.
- **Battery simulation**: Battery drains while driving, is published on `/battery_state`, and triggers an automatic return-to-dock when it drops below a threshold.
- **Auto-docking**: Navigates to a dock approach pose, then performs a laser-guided final creep into the dock. While docked, the battery recharges. After reaching the charge target, the robot undocks and resumes cleaning.
- **Obstacle avoidance**: Sofa, coffee table, plant, and crates are mapped during SLAM and avoided by Nav2 costmaps.
- **Two simulation paths**:
  - `fake_sim.py` — lightweight synthetic odom + 360-ray laser for fast Nav2 iteration.
  - Gazebo Harmonic — physics-accurate single-room world with TurtleBot3 Burger URDF and LDS sensor.

## Repository Layout

```
src/house_cleaner_bringup/
├── launch/
│   ├── house_cleaning_auto.launch.py          ← primary launcher (Gazebo + SLAM + Nav2 + assistant)
│   ├── house_cleaning_fake_sim.launch.py      ← fake_sim + AMCL + Nav2 (no Gazebo)
│   ├── house_cleaning_slam.launch.py          ← SLAM-only mapping launch
│   ├── house_cleaning_gazebo_nav.launch.py    ← Gazebo + prebuilt map + AMCL + Nav2
│   └── gazebo_house_cleaning.launch.py        ← Gazebo world + burger spawn + bridge
├── config/
│   ├── nav2_params.yaml                       ← Nav2 costmaps, planners, controllers, collision monitor
│   ├── house_room_map.yaml / house_room_map.pgm ← prebuilt 100x116 map (origin -2.325, -2.875)
│   ├── slam_toolbox_params.yaml               ← SLAM params for fake_sim
│   └── slam_toolbox_gazebo_params.yaml        ← SLAM params for Gazebo
├── house_cleaner_bringup/
│   ├── house_cleaner_assistant.py             ← mission supervisor, battery, docking
│   └── fake_sim.py                            ← synthetic odom + 360-ray LaserScan publisher
├── scripts/
│   └── battery_monitor.py                     ← live battery level visualizer
└── worlds/
    └── house_room.world                       ← 4.65 x 5.75 m room, obstacles, charging dock
```

## Key Concepts

### Coverage Bounds

The cleaning area is derived from the live SLAM map window at runtime. `_coverage_bounds(grid)` reads the map metadata and computes a rectangle with a safety margin. No room dimensions are hardcoded in the assistant.

Goals are generated as a boustrophedon strip pattern and clamped inward by `strip_width/2` so they stay inside the SLAM costmap even while the map is still resizing.

### Battery & Docking

Battery is simulated entirely in `house_cleaner_assistant.py`. Parameters are exposed as ROS parameters so they can be tuned at launch:

| Parameter | Default | Role |
|-----------|---------|------|
| `battery.drain_rate` | `0.12 %/s` | Drain while driving |
| `battery.charge_rate` | `1.20 %/s` | Charge while docked |
| `battery.low_threshold` | `35.0 %` | Trigger return to dock |
| `battery.charge_target` | `95.0 %` | Resume cleaning after charge |
| `mission.strip_width` | `0.60 m` | Boustrophedon lane spacing |

Dock geometry (map frame):
- Dock body center: `(0.0, 2.75)`, south face at `y = 2.625`
- Approach pose: `(0.0, 1.87)` yaw `+pi/2`
- `creep_to_dock` stops when front laser reads `< 0.13 m` (seated)
- `undock` backs out `~0.48 m` to clear dock inflation

### Nav2 Stack

The auto launch wires Nav2 manually (no `nav2_bringup`):

- `map_server` (prebuilt map)
- `amcl` (localization on the saved map)
- `planner_server` — `NavfnPlanner`
- `controller_server` — `FollowPath` (MPPI), `controller_frequency: 20.0`
- `behavior_server` — backup, spin, wait
- `bt_navigator` — BT-based `NavigateToPose` / `NavigateThroughPoses`
- `waypoint_follower` — `FollowWaypoints`
- `velocity_smoother` — `/cmd_vel_nav` → `/cmd_vel_smoothed`
- `collision_monitor` — reads costmap, outputs `/cmd_vel`
- `lifecycle_manager_navigation` — manage all Nav2 nodes

cmd_vel chain (verified live):
```
controller_server -> /cmd_vel_nav -> velocity_smoother -> /cmd_vel_smoothed
  -> collision_monitor -> /cmd_vel -> gz bridge -> robot
```

### SLAM

Two SLAM parameter files exist because `use_sim_time` and sensor range differ:

| Variant | File | `use_sim_time` | `max_laser_range` |
|---------|------|----------------|-------------------|
| fake_sim | `slam_toolbox_params.yaml` | `false` | `10.0` |
| Gazebo | `slam_toolbox_gazebo_params.yaml` | `true` | `4.0` |

Frames used everywhere: `map`, `odom`, `base_footprint`, `base_scan`.

## Hardware / Simulation Targets

- ROS distro: **Jazzy**
- Robot model: **TurtleBot3 Burger**
- Simulators: **Gazebo Harmonic** + custom `fake_sim.py`
- SLAM: **slam_toolbox** (async)
- Navigation: **Nav2**

## Prerequisites

```bash
# ROS 2 Jazzy
sudo apt install ros-jazzy-desktop
sudo apt install ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-gazebo
sudo apt install ros-jazzy-slam-toolbox ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

Environment variables:

```bash
source /opt/ros/jazzy/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
```

## Build

```bash
cd /home/koko/house_cleaner_ws
colcon build --symlink-install --cmake-args "-DPython3_EXECUTABLE=/usr/bin/python3" --packages-select house_cleaner_bringup
source env.sh   # workspace hook — required for this old colcon
```

## Launch

### 1) Auto-cleaning mission (Gazebo GUI + SLAM + Nav2 + assistant)

**Terminal 1 — simulation:**
```bash
tmux kill-session -t house_auto 2>/dev/null
tmux new-session -d -s house_auto \
  "source /opt/ros/jazzy/setup.bash && \
   source /home/koko/house_cleaner_ws/env.sh && \
   ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
     headless:=false \
     battery_drain_rate:=0.6 \
     battery_charge_rate:=1.5"
tmux attach -t house_auto
# detach without killing: Ctrl+b then d
```

**Terminal 2 — battery monitor:**
```bash
cd /home/koko/house_cleaner_ws
python3 src/house_cleaner_bringup/scripts/battery_monitor.py
# stop: Ctrl+c
```

- `headless:=true` (default) runs Gazebo headless.
- Battery drain/charge rates override the defaults for faster demo cycles.
- Logs: `/tmp/house_auto.log` and `~/.ros/log/...`

### 2) Fake-sim Nav2 only (fast, no Gazebo)

```bash
source /opt/ros/jazzy/setup.bash
source /home/koko/house_cleaner_ws/env.sh
ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py
```

### 3) SLAM-only mapping

```bash
ros2 launch house_cleaner_bringup house_cleaning_slam.launch.py
```

Drive the robot with `/cmd_vel` in a boustrophedon sweep, then save the map:

```bash
ros2 run nav2_map_server map_saver_cli -f ~/slam_map
```

### 4) Gazebo + prebuilt map + AMCL

```bash
ros2 launch house_cleaner_bringup house_cleaning_gazebo_nav.launch.py \
  headless:=false map:=/path/to/slam_map.yaml
```

## Verify

```bash
# Topics
ros2 topic list | grep -E '/(cmd_vel|map|scan|odom|tf|battery_state|dock_pose)'

# Lifecycle nodes
ros2 lifecycle get /slam_toolbox
ros2 lifecycle get /map_server
ros2 lifecycle get /controller_server

# Send a test goal
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 0.0, y: 1.0, z: 0.0}, orientation: {x: 0, y: 0, z: 0, w: 1}}}}"
```

## Cleaning Mission Flow

1. **CLEANING** — assistant generates a boustrophedon mission from the live SLAM map bounds and sends each goal sequentially via `/navigate_to_pose`.
2. **Battery drain** — simulated at `battery.drain_rate` while the robot is moving; `/battery_state` publishes current percentage.
3. **Low battery** — when battery drops below `battery.low_threshold`, the current goal is canceled and the state switches to **RETURNING**.
4. **RETURNING** — assistant navigates to the dock approach pose `(0.0, 1.87)`.
5. **DOCKING** — robot performs a slow laser-guided forward creep (`creep_to_dock`) until the front laser reads `< 0.13 m` (seated against dock).
6. **CHARGING** — battery recharges at `battery.charge_rate` until it reaches `battery.charge_target`.
7. **UNDOCKING** — robot backs out `~0.48 m` to clear the dock inflation zone.
8. **RESUME** — mission continues from the next uncovered goal.
9. **Mission complete** — when all goals are reached, the robot returns to dock and stays.

If a cleaning goal or dock approach cannot be planned, the assistant retries once, then skips that goal rather than aborting the whole mission.

## World Geometry

- Room interior: `4.65 m x 5.75 m`
- Wall interior: `x ∈ [-2.325, 2.325]`, `y ∈ [-2.875, 2.875]`
- Map: `100 x 116` px @ `0.05 m/px`, origin `[-2.325, -2.875, 0]`
- Coverage margin: `0.37 m` from walls
- Obstacles: sofa, coffee table, plant, crate A, crate B — all static, mapped by SLAM
- Dock: centered at `(0.0, 2.75)`, south face at `y = 2.625`

## Important Notes

- **Always kill stale ROS2 / Gazebo / RViz processes before relaunching.** Overlapping instances cause stale TF caches and port conflicts.
- **Re-source `/opt/ros/jazzy/setup.bash` in every new terminal.** `PYTHONPATH` does not survive across sessions.
- **Use `source env.sh`**, not just `install/setup.bash`. The workspace colcon hook is required for package prefix resolution.
- **`fake_sim.py` has no `ros2 run` entry point.** It is launched via the launch file or run directly as a Python script.
- **GitHub HTTPS API is proxy-blocked from this machine.** All git operations use SSH (`git@github.com:som-anshu/house_cleaner_ws.git`).

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `planner_server` crashes at launch | Costmap `width`/`height` must be integer cells | Use `93 x 115` (cells), not `4.65 x 5.75` (meters) |
| Gazebo launch exits -9 | controller_server crash, missing `/world/.../create` service | Use fake-sim launch instead |
| AMCL warns "Failed to transform initial pose in time" | Cosmetic — fake_sim `/initialpose` timestamp slightly off | Safe to ignore; `transform_tolerance: 1.0` absorbs it |
| Action clients fail with "context is invalid" | Stale ROS nodes after long run or overlapping instances | Kill all processes and relaunch fresh |
| `/tf` empty or stale | Multiple overlapping node instances | Kill all, relaunch one |
| `ros2` command not found | Env not sourced in new terminal | `source /opt/ros/jazzy/setup.bash` |
| Assistant exits with `Timed out waiting for /map` | SLAM startup is slower than old timeout | Fixed in latest code: timeout raised to 120s with progress logging |
| Mission skips goals instead of finishing | Map still growing; goals clamped away from bounds | Normal — assistant skips unreachable goals and continues |

## Status

- ✅ Autonomous boustrophedon coverage from live SLAM map
- ✅ Battery simulation with `/battery_state`
- ✅ Auto-return, laser-guided dock, charge, undock, resume
- ✅ Obstacle mapping and avoidance
- ✅ Two simulation paths (fake_sim + Gazebo Harmonic)
- ✅ SLAM mapping with map save/load
- ✅ All 9 Nav2 nodes + lifecycle manager verified
- ✅ Live battery monitor script
- ✅ Skip-unreachable-goal recovery instead of mission abort
- ✅ Git repo on GitHub (SSH)
