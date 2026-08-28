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
- X11 server running (for GUI)

**Steps:**

```bash
# Clone the repository
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws

# Set up X11 access (required for GUI)
xhost +local:docker

# Run the simulation (builds automatically on first run)
./run_docker.sh
```

**That's it!** The simulation will start with:
- Gazebo GUI showing the house room
- TurtleBot3 Burger spawning at (0,0)
- SLAM building a map from laser scans
- Nav2 navigating autonomously
- Foxglove Bridge accessible at http://localhost:8765

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

# Headless mode (no GUI, server only)
./run_docker.sh --headless

# Custom launch file
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  house_cleaner:jazzy \
  --launch=house_cleaner_bringup/house_cleaning_auto.launch.py
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
# Terminal 1: Launch the full simulation
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py

# Terminal 2: Battery monitor (optional)
python3 src/house_cleaner_bringup/scripts/battery_monitor.py

# Terminal 3: Teleop control (optional)
ros2 launch house_cleaner_bringup teleop.launch.py
```

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
| `battery.low_threshold` | 35.0 % | Return to dock at this level |
| `battery.charge_target` | 95.0 % | Resume cleaning after charging |

**Customize:**
```bash
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
  battery_drain_rate:=0.3 \
  battery_charge_rate:=1.0 \
  battery_low_threshold:=40.0
```

### Docking Process

1. **Low battery detected** — Current goal cancelled
2. **Return to dock** — Navigate to approach pose (0.0, 1.87)
3. **Laser-guided creep** — Slow forward until front laser reads < 0.13m
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
├── Dockerfile                    # Docker image definition
├── docker-compose.yml           # Docker Compose configuration
├── run_docker.sh                # Docker launcher script
├── entrypoint.sh                # Docker container entrypoint
├── env.sh                       # ROS2 environment setup
├── README.md                    # This file
├── LICENSE                      # MIT License
└── src/
    └── house_cleaner_bringup/
        ├── CMakeLists.txt       # Build configuration
        ├── package.xml          # Package dependencies
        ├── setup.py             # Python package setup
        ├── config/
        │   ├── nav2_params.yaml           # Nav2 parameters
        │   ├── slam_toolbox_gazebo_params.yaml  # SLAM parameters
        │   ├── burger_bridge.yaml         # Gazebo-ROS bridge config
        │   └── foxglove_layout.json       # Foxglove panel layout
        ├── launch/
        │   ├── house_cleaning_auto.launch.py  # Main launch file
        │   ├── gazebo_house_cleaning.launch.py  # Gazebo only
        │   ├── foxglove_bridge.launch.py   # Foxglove bridge
        │   ├── rviz2.launch.py            # RViz2 visualization
        │   └── teleop.launch.py           # Teleop control
        ├── worlds/
        │   └── house_room.world           # Gazebo world
        ├── models/
        │   └── wall/                      # Wall model
        ├── house_cleaner_bringup/
        │   ├── __init__.py
        │   ├── house_cleaner_assistant.py # Cleaning supervisor
        │   └── fake_sim.py               # Lightweight simulator
        └── scripts/
            ├── battery_monitor.py        # Terminal battery display
            └── kill_house_cleaner.sh     # Cleanup script
```

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `qt.qpa.xcb: could not connect to display` | No X11 forwarding | Run `xhost +local:docker` |
| `OpenGL 3.3 is not supported` | GPU driver issues | Use `LIBGL_ALWAYS_SOFTWARE=1` (set in run_docker.sh) |
| `controller_server crashes` | MPPI visualization | Set `visualize: false` in nav2_params.yaml |
| `ros2 command not found` | Environment not sourced | Run `source env.sh` |
| `Assistant times out on /map` | SLAM slow to initialize | Wait up to 120s for first map |
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

> **Note:** Real robot support is planned for a future phase.

The simulation is designed to be directly transferable to a real TurtleBot3 Burger:

1. **Save the SLAM map:**
   ```bash
   ros2 run nav2_map_server map_saver_cli -f /tmp/house_map
   ```

2. **Deploy on real robot:**
   ```bash
   # Copy map to robot
   scp /tmp/house_map.* robot@turtlebot3:/home/robot/maps/

   # Launch navigation on robot
   ros2 launch house_cleaner_bringup bringup_real_robot.launch.py \
     map:=/home/robot/maps/house_map.yaml
   ```

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
