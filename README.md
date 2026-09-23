# House Cleaner Robot

[![ROS2 Jazzy](https://img.shields.io/badge/ROS2-Jazzy-blue.svg)](https://docs.ros.org/en/jazzy/)
[![Gazebo Harmonic](https://img.shields.io/badge/Gazebo-Harmonic-green.svg)](https://gazebosim.org/docs/harmonic/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Autonomous room-cleaning robot built on ROS 2 Jazzy and TurtleBot3 Burger.

The robot maps an unknown room with SLAM, plans a full-coverage cleaning path, avoids obstacles, tracks its battery, and docks itself to recharge when low.

![House Cleaner Simulation](docs/images/simulation.png)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Docker Setup](#docker-setup)
- [Native Install](#native-install)
- [GUI Visualization](#gui-visualization)
- [Teleop Control](#teleop-control)
- [Battery and Docking](#battery-and-docking)
- [Cleaning Mission Flow](#cleaning-mission-flow)
- [World Geometry](#world-geometry)
- [Repository Layout](#repository-layout)
- [Troubleshooting](#troubleshooting)
- [Real Robot Deployment](#real-robot-deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Autonomous coverage cleaning** — Boustrophedon (lawnmower) path planned from the live SLAM map
- **Live SLAM mapping** — `slam_toolbox` builds the map on the fly; no prebuilt map required
- **Battery simulation** — Drains while driving, published on `/battery_state`
- **Auto-docking** — Returns to dock at low battery, laser-guided final approach, recharges, resumes cleaning
- **Obstacle avoidance** — Sofa, table, plant, and crates mapped and avoided via Nav2 costmaps
- **Foxglove visualization** — Web-based real-time visualization on port 8765
- **Docker containerized** — One-command setup, works on any device with Docker
- **TurtleBot3 Burger ready** — Designed for real TurtleBot3 Burger deployment

---

## Quick Start

### Option 1: Docker (Recommended)

**Prerequisites:**
- Docker installed ([Install Docker](https://docs.docker.com/get-docker/))
- A Linux desktop session (X11 or Wayland) for the GUI — auto-detected

**Steps:**

```bash
# Clone the repository
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws

# Run the simulation (builds automatically on first run)
./run_docker.sh
```

**That's it!** The simulation will start with:
- Gazebo GUI showing the house room
- TurtleBot3 Burger spawning at (0,0)
- SLAM building a map from laser scans
- Nav2 navigating autonomously
- Foxglove Bridge accessible at http://localhost:8765

`run_docker.sh` auto-detects your GUI backend (X11 or Wayland), forwards the
display socket + xauth cookie (no `xhost +` needed), passes through `/dev/dri`
when present for GPU rendering, and falls back to software rendering
(llvmpipe) otherwise.  No VNC is required.

### Option 2: Native Install

See [Native Install](#native-install) section below.

---

## Docker Setup

### Building the Image

```bash
# Build the Docker image
docker build -t house_cleaner:jazzy .

# Or force rebuild
./run_docker.sh --build
```

### Running the Simulation

```bash
# GUI mode (default)
./run_docker.sh

# Headless mode (no GUI, server only — Foxglove still available)
./run_docker.sh --headless

# Interactive shell inside the container
./run_docker.sh --shell

# Custom launch file
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  house_cleaner:jazzy \
  --launch house_cleaner_bringup gazebo_house_cleaning.launch.py
```

### Docker Commands

```bash
# View logs
docker logs -f house_cleaner_jazzy

# Enter container shell
docker exec -it house_cleaner_jazzy bash

# Stop the simulation
docker stop house_cleaner_jazzy

# Remove the container
docker rm house_cleaner_jazzy
```

### Docker Configuration

The Docker container includes:
- ROS2 Jazzy
- Gazebo Harmonic
- Nav2 Navigation Stack
- SLAM Toolbox
- TurtleBot3 Burger
- Foxglove Bridge
- RViz2
- Teleop Twist Keyboard

---

## Native Install

### Prerequisites

```bash
# Ubuntu 24.04 with ROS2 Jazzy
sudo apt update && sudo apt install ros-jazzy-desktop

# Additional packages
sudo apt install \
  ros-jazzy-turtlebot3-gazebo \
  ros-jazzy-turtlebot3-description \
  ros-jazzy-slam-toolbox \
  ros-jazzy-nav2 \
  ros-jazzy-foxglove-bridge \
  ros-jazzy-teleop-twist-keyboard \
  python3-colcon-common-extensions
```

### Clone and Build

```bash
# Clone the repository
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws

# Build the workspace
colcon build --symlink-install

# Source the workspace
source env.sh
```

### Run the Simulation

```bash
# Terminal 1: Launch the full simulation (GUI)
ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim

# Server-only Gazebo (no GUI)
ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim headless:=true

# Terminal 2: Battery monitor (optional)
python3 src/house_cleaner_bringup/scripts/battery_monitor.py

# Terminal 3: Teleop control (optional)
ros2 launch house_cleaner_bringup teleop.launch.py
```

The single `house_cleaning.launch.py` drives both sim and real hardware
(`mode:=sim|real`); see [Real Robot Deployment](#real-robot-deployment).

---

## GUI Visualization

### Foxglove (Web-Based)

Foxglove provides web-based visualization accessible from any device on your network.

**Access:**
1. Open browser to: http://localhost:8765
2. Or use Foxglove app: ws://localhost:8765
3. Select "Foxglove WebSocket" connection type

**Features:**
- 3D robot model view
- Map and costmap visualization
- Laser scan display
- Battery state monitoring
- Real-time topic plotting

### RViz2 (Local)

RViz2 provides local 3D visualization.

**Launch:**
```bash
# In Docker
docker exec -it house_cleaner_jazzy ros2 launch house_cleaner_bringup rviz2.launch.py

# Native
ros2 launch house_cleaner_bringup rviz2.launch.py
```

**Displays:**
- Robot model (TF frames)
- Laser scan
- Map and costmap
- Navigation goals and paths
- Battery state

---

## Teleop Control

Manually control the robot in Gazebo for testing.

**Launch:**
```bash
# In Docker
docker exec -it house_cleaner_jazzy ros2 launch house_cleaner_bringup teleop.launch.py

# Native
ros2 launch house_cleaner_bringup teleop.launch.py
```

**Controls:**
| Key | Action |
|-----|--------|
| `i` | Move forward |
| `k` | Stop |
| `j` | Turn left |
| `l` | Turn right |
| `u` | Forward + turn left |
| `o` | Forward + turn right |
| `,` | Move backward |
| `.` | Increase speed |
| `-` | Decrease speed |
| `q` | Quit |

---

## Battery and Docking

### Battery Simulation

The battery drains while driving and charges while docked.

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `battery.drain_rate` | 0.20 %/s | Drain while driving |
| `battery.charge_rate` | 0.80 %/s | Charge while docked |
| `battery.low_threshold` | 40.0 % | Return to dock at this level |
| `battery.charge_target` | 95.0 % | Resume cleaning after charging |

**Customize:**
```bash
ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim \
  battery_drain_rate:=0.3 \
  battery_charge_rate:=1.0 \
  battery_low_threshold:=45.0 \
  mission_return_budget:=180.0
```

### Docking Process

1. **Low battery detected** — Current goal cancelled (watchdog timer)
2. **Return to dock** — Navigate to approach pose (0.0, 1.87)
3. **Laser-guided creep** — `docking_controller` creeps via the Nav2 velocity
   chain (`/cmd_vel_nav` -> velocity_smoother -> collision_monitor);
   the front polygon stop or stall/flat-window latch seats the robot
4. **Charging** — Battery recharges to target level
5. **Undocking** — Back out 0.48m, resume cleaning

---

## Cleaning Mission Flow

```
CLEANING -> (battery low) -> RETURNING -> DOCKING -> CHARGING -> UNDOCKING -> RESUME
```

1. **Cleaning** — Boustrophedon waypoints sent one-by-one via `/navigate_to_pose`
2. **Battery drain** — Simulated while the robot is moving
3. **Low battery** — Current goal cancelled, navigation returns to dock
4. **Returning** — Navigate to dock approach point at (0.0, 2.75)
5. **Docking** — Slow laser-guided approach until front laser reads < 0.13m
6. **Charging** — Recharge until target battery level reached
7. **Undocking** — Reverse 0.48m, resume cleaning
8. **Complete** — All waypoints visited, robot parks at dock

---

## World Geometry

| Item | Value |
|------|-------|
| Room interior | 4.65m x 5.75m |
| Wall bounds | x ∈ [-2.325, 2.325], y ∈ [-2.875, 2.875] |
| Map (SLAM) | ~94 x 116 cells at 0.05m/pixel |
| Obstacles | Sofa, coffee table, plant, wooden crates |
| Dock center | (0.0, 2.75) |

---

## Repository Layout

```
house_cleaner_ws/
├── Dockerfile                    # Docker image definition (ROS2 Jazzy + Gazebo Harmonic)
├── docker-compose.yml            # Docker Compose configuration (X11/Wayland GUI)
├── run_docker.sh                 # Docker launcher (auto X11/Wayland detection)
├── entrypoint.sh                 # Docker container entrypoint
├── env.sh                        # ROS2 environment setup (native)
├── README.md                     # This file
├── LICENSE                       # MIT License
└── src/
    ├── house_cleaner_msgs/       # Shared interfaces (DockCommand, DockState, CreepToDock)
    ├── house_cleaner_core/       # Pure-Python coverage/geometry helpers (no ROS)
    ├── house_cleaner_battery/    # battery_sim + battery_hw backends (same contract)
    ├── house_cleaner_docking/    # Laser-guided docking controller + /undock
    ├── house_cleaner_mission/    # Mission supervisor (coverage + battery + dock orchestration)
    ├── house_cleaner_description/# (reserved) custom burger/dock URDF
    └── house_cleaner_bringup/    # Launch files + config + worlds + models + scripts
        ├── CMakeLists.txt        # Install launch/config/worlds/models/scripts
        ├── package.xml           # Package dependencies
        ├── config/
        │   ├── nav2_params.yaml           # Nav2 + collision_monitor params
        │   ├── slam_toolbox_gazebo_params.yaml  # SLAM parameters
        │   ├── burger_bridge.yaml         # Gazebo-ROS bridge config
        │   └── house_cleaning.rviz       # RViz2 display config
        ├── launch/
        │   ├── house_cleaning.launch.py  # UNIFIED entry point (mode:=sim|real)
        │   ├── gazebo_house_cleaning.launch.py  # Gazebo world + burger + bridge
        │   ├── foxglove_bridge.launch.py   # Foxglove bridge
        │   ├── rviz2.launch.py            # RViz2 visualization
        │   └── teleop.launch.py           # Teleop control
        ├── worlds/
        │   └── house_room.world           # Gazebo world
        ├── models/
        │   └── wall/                      # Wall model
        └── scripts/
            ├── battery_monitor.py        # Terminal battery display
            └── kill_house_cleaner.sh     # Cleanup script
```

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `qt.qpa.xcb: could not connect to display` | Display socket/xauth not forwarded | Use `./run_docker.sh` (auto X11/Wayland forwarding, no `xhost +`) |
| `OpenGL 3.3 is not supported` | GPU driver issue in container | `LIBGL_ALWAYS_SOFTWARE=1` is set by default in run_docker.sh |
| `controller_server crashes` | MPPI visualization | Set `visualize: false` in nav2_params.yaml (already default) |
| `ros2 command not found` | Environment not sourced | Run `source env.sh` |
| `Supervisor times out on /map` | SLAM slow to initialize | Wait up to 120s for first map |
| Foxglove won't connect | Port 8765 blocked | Check `docker ps` for port mapping |

### Debug Commands

```bash
# Check topic list
ros2 topic list | grep -E '/(cmd_vel|map|scan|odom|tf|battery_state)'

# Check lifecycle states
ros2 lifecycle get /slam_toolbox        # expect "active"
ros2 lifecycle get /controller_server   # expect "active"

# View node graph
ros2 node list

# Check TF tree
ros2 run tf2_tools view_frames
```

### Logs

```bash
# Docker logs
docker logs -f house_cleaner_jazzy

# Enter container for debugging
docker exec -it house_cleaner_jazzy bash
```

---

## Real Robot Deployment

The stack is structured for a real TurtleBot3 Burger out of the box.  The
same `house_cleaning.launch.py` drives it with `mode:=real` — SLAM / Nav2
are replaced by map_server + AMCL localization, and the battery backend swaps
from `battery_sim` to `battery_hw`.

> **Note:** `mode:=real` expects the TurtleBot3 bringup driver (OpenCR, LDS)
> to publish `/odom`, `/scan`, `/joint_states`, etc. on the robot, or via the
> host `turtlebot3_bringup` package (add it to the Dockerfile when you go
> physical).  Custom dock wiring: see below.

1. **Save the SLAM map from the sim:**
   ```bash
   ros2 run nav2_map_server map_saver_cli -f /tmp/house_map
   ```

2. **Run on hardware (localize on the saved map):**
   ```bash
   # Not yet implemented: real-mode substitution of map_server/AMCL and the
   # TurtleBot3 driver nodes is stubbed in house_cleaning.launch.py (mode:=real).
   ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=real
   ```

**Custom dock (hardware) contract** used by `battery_hw` and the mission
supervisor:

| Topic | Type | Description |
|-------|------|-------------|
| `/dock/seated` (in) | std_msgs/Bool | Robot physically seated (also published by docking_controller) |
| `/dock/current` (in) | std_msgs/Float64 | Analog charge-current input (A) |
| `/dock/fault` (in) | std_msgs/Bool | Dock fault detection |
| `/battery_state_opencr` (in) | sensor_msgs/BatteryState | Raw OpenCR/BMS battery stream |
| `/battery_state` (out) | sensor_msgs/BatteryState | Supervisor-facing battery telemetry |
| `/dock/state` (out) | house_cleaner_msgs/DockState | seat + charge + fault state machine |
| `/dock/command` (in) | house_cleaner_msgs/DockCommand | `CMD_START/STOP/FAULT` from supervisor |

Wire these into whatever dock hardware you use (GPIO expander, I2C bridge,
or the OpenCR); the supervisor only ever reads `/battery_state`, sends
`/dock/command`, and waits on `/creep_to_dock` + `/undock`.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow ROS2 coding standards
- Add comments to all code
- Test in Docker before pushing
- Update documentation for new features

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [ROS2](https://docs.ros.org/) - Robot Operating System
- [Nav2](https://docs.nav2.org/) - Navigation2 Stack
- [Gazebo](https://gazebosim.org/) - Robotics Simulator
- [Foxglove](https://foxglove.dev/) - Robotics Visualization
- [TurtleBot3](https://www.robotis.us/turtlebot-3/) - Robot Platform
