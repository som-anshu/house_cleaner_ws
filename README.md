# House Cleaner Robot

Autonomous room-cleaning robot built on ROS 2 Jazzy and TurtleBot3 Burger.

The robot maps an unknown room with SLAM, plans a full-coverage cleaning path,
avoids obstacles, tracks its battery, and docks itself to recharge when low.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Docker Setup](#docker-setup)
4. [Native Install](#native-install)
5. [Alternative Launch Modes](#alternative-launch-modes)
6. [Features](#features)
7. [Battery and Docking](#battery-and-docking)
8. [Cleaning Mission Flow](#cleaning-mission-flow)
9. [World Geometry](#world-geometry)
10. [Verification](#verification)
11. [Repository Layout](#repository-layout)
12. [Troubleshooting](#troubleshooting)
13. [Automated Testing](#automated-testing)
14. [Status](#status)

---

## System Requirements

- Ubuntu 24.04 LTS (Noble Numbat)
- ROS 2 Jazzy Jalisco
- Docker 24+ (for containerized mode)
- X11 server (for GUI mode)
- GPU with OpenGL 3.3+ support (for GUI rendering; headless mode does not require GPU)

### Prerequisites

```bash
# ROS 2 Jazzy (if not already installed)
sudo apt update && sudo apt install ros-jazzy-desktop

# Additional packages
sudo apt install ros-jazzy-turtlebot3-gazebo \
                 ros-jazzy-turtlebot3-description \
                 ros-jazzy-slam-toolbox \
                 ros-jazzy-nav2 \
                 python3-colcon-common-extensions

# Environment variables
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
```

---

## Quick Start

Choose your preferred path:

| Path | Use Case | Effort |
|------|----------|--------|
| [Docker](#docker-setup) | Run immediately without local ROS2 setup | 1 command |
| [Native Install](#native-install) | Develop or modify the codebase | ~10 min setup |

---

## Docker Setup

The entire stack (Gazebo + SLAM + Nav2 + house cleaner assistant) runs in a single container.

### First-Time Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER     # log out and back in after this

# Clone the repository
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws
```

### Launching the Simulation

```bash
cd house_cleaner_ws

# Headless mode (default): no GUI, runs in container only
./run_docker.sh            # first run: builds the image, then launches
./run_docker.sh --build    # force rebuild the image
./run_docker.sh            # subsequent runs: reuse cached image

# GUI mode: opens Gazebo window on host display
xhost +local:docker
./run_docker_gui.sh
```

Both scripts automatically kill any previous house-cleaner instance (host ROS2/Gazebo/RViz processes plus the old container) before starting a fresh simulation.

### Docker Launch Parameters

Parameters are passed directly to the ROS2 launch system via the entrypoint:

```bash
# Headless mode with default parameters
./run_docker.sh

# Custom parameters
./run_docker.sh --battery_drain_rate 0.3
./run_docker.sh mission_strip_width:=0.4

# GUI mode with custom parameters
./run_docker_gui.sh --battery_drain_rate 0.25 --mission_strip_width 0.35
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `battery_drain_rate` | `0.20 %/s` | Battery drain while driving |
| `battery_charge_rate` | `0.80 %/s` | Battery charge while docked |
| `battery_low_threshold` | `35.0 %` | Return to dock at this battery percent |
| `battery_charge_target` | `95.0 %` | Resume cleaning after charging to this percent |
| `mission_strip_width` | `0.35 m` | Boustrophedon lane spacing |
| `headless` | `true` | Set to `false` to enable Gazebo GUI |

### Docker Configuration Notes

- The `docker-compose.yml` configures the container with X11 and GPU device mappings.
- Headless mode uses `GZ_RENDERING_DISABLED=1` to avoid requiring GPU drivers.
- GUI mode requires X11 access (`xhost +local:docker`) and a valid `DISPLAY` environment variable.

---

## Native Install

### Prerequisites

```bash
# Ubuntu 24.04 with ROS 2 Jazzy already installed
sudo apt install ros-jazzy-turtlebot3-gazebo
sudo apt install ros-jazzy-turtlebot3-description
sudo apt install ros-jazzy-slam-toolbox
sudo apt install ros-jazzy-nav2
sudo apt install python3-colcon-common-extensions
```

### Clone and Build

```bash
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws
colcon build --symlink-install \
  --cmake-args "-DPython3_EXECUTABLE=/usr/bin/python3" \
  --packages-select house_cleaner_bringup
source env.sh    # required for package prefix resolution on older colcon
```

### Environment Setup

Every new terminal:

```bash
source /opt/ros/jazzy/setup.bash
source env.sh                    # use absolute path if running from another directory
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
```

### How to Run

```bash
# Terminal 1: kill stale instances, then start the full simulation
bash src/house_cleaner_bringup/scripts/kill_house_cleaner.sh
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py headless:=false

# Terminal 2: battery monitor
python3 src/house_cleaner_bringup/scripts/battery_monitor.py
```

### Native Launch Parameters

```bash
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
  battery_drain_rate:=0.20 \
  battery_charge_rate:=0.80 \
  battery_low_threshold:=35.0 \
  battery_charge_target:=95.0 \
  mission_strip_width:=0.35 \
  headless:=true
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `battery_drain_rate` | `0.20 %/s` | Battery drain while driving |
| `battery_charge_rate` | `0.80 %/s` | Battery charge while docked |
| `battery_low_threshold` | `35.0 %` | Return to dock at this battery percent |
| `battery_charge_target` | `95.0 %` | Resume cleaning after charging to this percent |
| `mission_strip_width` | `0.35 m` | Boustrophedon lane spacing |
| `headless` | `true` | `true` = no Gazebo GUI, `false` = show GUI |

---

## Alternative Launch Modes

| Command | Description |
|---------|-------------|
| `./run_house_cleaner.sh` | Lyrical/Jazzy direct run: fake_sim + assistant (no Gazebo) |
| `ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py` | Fake-sim Nav2 only (no Gazebo, fast) |
| `ros2 launch house_cleaner_bringup house_cleaning_slam.launch.py` | SLAM-only mapping |
| `ros2 launch house_cleaner_bringup house_cleaning_gazebo_nav_manual.launch.py headless:=false` | Gazebo with prebuilt map and AMCL |

---

## Features

- **Autonomous coverage cleaning** — boustrophedon (lawnmower) path planned from the live SLAM map
- **Live SLAM mapping** — `slam_toolbox` builds the map on the fly; no prebuilt map required
- **Battery simulation** — drains while driving, published on `/battery_state`
- **Auto-docking** — returns to dock at low battery, laser-guided final approach, recharges, resumes cleaning
- **Obstacle avoidance** — sofa, table, plant, and crates mapped and avoided via Nav2 costmaps
- **Dual simulators** — Gazebo Harmonic (physics-based) or lightweight fake simulator

---

## Battery and Docking

Battery simulation runs in `house_cleaner_assistant.py` and is configurable via ROS parameters:

| Parameter | Default | Role |
|-----------|---------|------|
| `battery.drain_rate` | `0.20 %/s` | Drain while driving |
| `battery.charge_rate` | `0.80 %/s` | Charge while docked |
| `battery.low_threshold` | `35.0 %` | Return to dock when below |
| `battery.charge_target` | `95.0 %` | Resume cleaning after charging |
| `mission.strip_width` | `0.35 m` | Boustrophedon lane spacing |

### Cleaning Around Walls and Furniture

For tighter coverage between walls and furniture:

- Reduce `mission.strip_width` (default 0.35 m works for most scenarios)
- Reduce `inflation_radius` in `nav2_params.yaml` (default 0.35 m)
- Launch argument: `mission_strip_width:=0.35`

This allows the robot to clean closer to walls and furniture while Nav2's obstacle layer still prevents collisions.

---

## Cleaning Mission Flow

```
CLEANING -> (battery low) -> RETURNING -> DOCKING -> CHARGING -> UNDOCKING -> RESUME
```

1. **Cleaning** — boustrophedon waypoints sent one-by-one via `/navigate_to_pose`
2. **Battery drain** — simulated while the robot is moving
3. **Low battery** — current goal cancelled, navigation returns to dock
4. **Returning** — navigate to dock approach point at `(0.0, 2.75)`
5. **Docking** — slow laser-guided approach until front laser reads less than 0.13 m
6. **Charging** — recharge until target battery level reached
7. **Undocking** — reverse approximately 0.48 m, resume cleaning
8. **Complete** — all waypoints visited, robot parks at dock

---

## World Geometry

| Item | Value |
|------|-------|
| Room interior | 4.65 m x 5.75 m |
| Wall bounds | x in [-2.325, 2.325], y in [-2.875, 2.875] |
| Map (SLAM) | Approx 94 x 116 cells at 0.05 m/pixel |
| Obstacles | Sofa, coffee table, plant, wooden crates |
| Dock center | (0.0, 2.75) |

---

## Verification

```bash
# List key topics
ros2 topic list | grep -E '/(cmd_vel|map|scan|odom|tf|battery_state|dock_pose)'

# Check lifecycle states
ros2 lifecycle get /slam_toolbox        # expect "active"
ros2 lifecycle get /controller_server   # expect "active"
```

---

## Repository Layout

```
src/house_cleaner_bringup/
    launch/
        house_cleaning_auto.launch.py           # Primary: Gazebo + SLAM + Nav2 + assistant
        house_cleaning_fake_sim.launch.py       # Lightweight fake simulator
        house_cleaning_slam.launch.py           # SLAM-only mapping
        house_cleaning_gazebo_nav_manual.launch.py
        gazebo_house_cleaning.launch.py         # Gazebo + spawn + bridge
    config/
        nav2_params.yaml                        # Full Nav2 parameter set
        slam_toolbox_params.yaml
        burger_bridge.yaml                      # Gazebo-ROS bridge (cmd_vel = Twist)
        house_room_map.yaml                     # Prebuilt map (for AMCL mode)
    house_cleaner_bringup/
        house_cleaner_assistant.py              # Coverage planning + battery + docking
        house_cleaner_assistant_lyrical.py      # Lyrical branch assistant
        fake_sim.py                             # Lightweight simulator (Jazzy)
        fake_sim_lyrical.py                     # Lightweight simulator (Lyrical)
        fake_sim_lyrical_standalone.py          # Standalone fake sim launcher
    scripts/
        battery_monitor.py                      # Terminal battery bar display
        verify_scan_forward_index.py
        kill_house_cleaner.sh                   # Kill all ROS2/Gazebo processes
    worlds/
        house_room.world                        # Gazebo world with obstacles
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `qt.qpa.xcb: could not connect to display` | No X11 forward or DISPLAY not set | Use headless mode (`./run_docker.sh`) or set up X11 access |
| `OpenGL 3.3 is not supported` | No GPU access in container | Set `GZ_RENDERING_DISABLED=1` (default in headless mode) |
| `controller_server` crashes (SIGABRT) | MPPI visualization in headless mode | `visualize: false` in nav2_params.yaml |
| `planner_server` crashes | Costmap dimensions incorrect | Ensure resolution and dimensions produce integer cell counts |
| `ros2` command not found | Environment not sourced | Run `source /opt/ros/jazzy/setup.bash` |
| Assistant times out on `/map` | SLAM slow to initialize | 120s timeout with progress logging; wait for first map |
| Mission skips goals | Map still growing | Normal behavior; unreachable goals are skipped |
| `/tf` empty or stale frames | Overlapping node instances | Kill all processes, relaunch from clean state |

---

## Automated Testing

The repository includes a portability test suite to validate that all hardcoded paths
have been removed and that scripts function correctly regardless of installation location.

### Running Tests

```bash
cd house_cleaner_ws
chmod +x test_portability.sh
./test_portability.sh
```

### Test Coverage

| Test | Validates |
|------|-----------|
| 1 | No hardcoded `/home/koko` paths in tracked files |
| 2 | `env.sh` uses `BASH_SOURCE` for dynamic path detection |
| 3 | `run_house_cleaner.sh` exists, executable, uses dynamic paths |
| 4 | `run_docker_gui.sh` uses `$DIR` for volume mount (not `$HOME`) |
| 5 | Dockerfile includes Mesa/GL libraries for rendering support |
| 6 | All launch files parse as valid Python |
| 7 | No external symlinks in workspace root |
| 8 | README references `env.sh` and `run_docker_gui.sh` |
| 9 | Config files (YAML) are valid |
| 10 | `collision_monitor` parameters present with `observation_sources` |
| 11 | MPPI parameters (`rollout_batch_size`, `collision_checker`) under `FollowPath` |
| 12 | `collision_monitor` excluded from lifecycle manager `node_names` |
| - | Plus 14 additional sub-checks within each test |

### Expected Output

```
=== Portability Test Suite ===

=== Results: 26 passed, 0 failed ===

Exit code: 0
```

---

## Status

- Autonomous coverage from live SLAM mapping
- Battery simulation with low-battery return-to-dock
- Auto-docking and recharging
- Obstacle avoidance
- Dual simulator support (Gazebo and fake sim)
- Docker containerization with headless and GUI modes
- Version-controlled on GitHub via SSH