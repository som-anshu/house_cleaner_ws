# 🤖 House Cleaner Robot

Autonomous room-cleaning robot built on **ROS 2 Jazzy** + **TurtleBot3 Burger**.

The robot maps an unknown room with SLAM, plans a full-coverage cleaning path,
avoids obstacles, tracks its battery, and docks itself to recharge when low.

---

## 🚀 Quick Start

Pick one path:

| Path | Best for | Effort |
|------|----------|--------|
| **[🐳 Docker](#docker-recommended)** | Seeing it run immediately | 1 command |
| **[🛠️ Native install](#native-install)** | Developing the code | ~10 min setup |

---

## 🐳 Docker (Recommended)

Everything (Gazebo + SLAM + Nav2 + assistant) runs in one container.
The Gazebo **GUI** and **battery monitor** launch together automatically.

### 1. First-time setup

```bash
# a) Install Docker (Linux/Ubuntu) — otherwise: https://docs.docker.com/install
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER     # then log out & back in

# b) Clone the repo
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws
```

### 2. How to run (every time)

```bash
./run_docker.sh --build   # first run: builds the image, then launches
./run_docker.sh           # later runs: just launches (reuse cached image)
```

`run_docker.sh` **always kills any previous house-cleaner instance** (host ROS2/Gazebo/RViz processes + the old container) before starting a fresh sim, so you never get a stale robot.

That's it. A Gazebo window opens showing the robot cleaning the room, and the
terminal shows a live battery bar.

### Docker notes

- First run builds the image (installs the whole Nav2/Gazebo stack) → **a few
  minutes**. Later runs start instantly.
- GUI renders in software (no NVIDIA passthrough configured) → fine to view,
  just not buttery-smooth.
- Linux only. On macOS/Windows, run with `DISPLAY`/X11 forwarding configured
  for GUI apps.

### Docker launch parameters (customize at runtime)

Pass launch arguments after `--` to customize the robot's behavior:

```bash
# Default: GUI enabled with tighter obstacle navigation
./run_docker.sh

# Custom parameters: faster battery drain, tighter coverage
./run_docker.sh --battery_drain_rate 0.3 --mission_strip_width 0.4

# Headless mode (no GUI) with default params
./run_docker.sh --headless true

# Full example with all parameters
./run_docker.sh --battery_drain_rate 0.25 --battery_charge_rate 1.0 \
  --battery_low_threshold 40.0 --mission_strip_width 0.35
```

Available Docker launch parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `battery_drain_rate` | `0.20 %/s` | Battery drain while driving |
| `battery_charge_rate` | `0.80 %/s` | Battery charge while docked |
| `battery_low_threshold` | `35.0 %` | Return to dock at this battery % |
| `mission_strip_width` | `0.35 m` | Boustrophedon lane spacing |
| `headless` | `false` | Set `true` to disable Gazebo GUI |

---

## 🛠️ Native Install

### 1. First-time setup

Prerequisites:

```bash
# Ubuntu 24.04 (Noble) with ROS 2 Jazzy already installed
sudo apt install ros-jazzy-desktop
sudo apt install ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-gazebo
sudo apt install ros-jazzy-slam-toolbox ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

Clone + build:

```bash
git clone git@github.com:som-anshu/house_cleaner_ws.git
cd house_cleaner_ws
colcon build --symlink-install \
  --cmake-args "-DPython3_EXECUTABLE=/usr/bin/python3" \
  --packages-select house_cleaner_bringup
source env.sh      # workspace hook (required on this host's old colcon)
```

Environment (every new terminal):

```bash
source /opt/ros/jazzy/setup.bash
source ~/house_cleaner_ws/env.sh
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
```

### 2. How to run (every time)

Kill any previous instance, then launch the full mission:

```bash
# Terminal 1 — kill stale instances, then start the sim (GUI + SLAM + Nav2 + assistant)
bash scripts/kill_house_cleaner.sh
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py headless:=false

# Terminal 2 — battery monitor
cd ~/house_cleaner_ws
python3 src/house_cleaner_bringup/scripts/battery_monitor.py
```

`kill_house_cleaner.sh` always clears leftover ROS2/Gazebo/RViz processes first,
so every run starts from a clean state.

### 3. Alternative launch modes

| Command | What it runs |
|---------|--------------|
| `ros2 launch house_cleaner_bringup house_cleaning_fake_sim.launch.py` | Fake-sim Nav2 only — fast, no Gazebo |
| `ros2 launch house_cleaner_bringup house_cleaning_slam.launch.py` | SLAM-only mapping (save with `map_saver_cli`) |
| `ros2 launch house_cleaner_bringup house_cleaning_gazebo_nav.launch.py headless:=false` | Gazebo + prebuilt map + AMCL |

### 4. Launch parameters (live launch customization)

Modify behavior at launch time with these arguments:

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
| `battery_low_threshold` | `35.0 %` | Return to dock at this battery % |
| `battery_charge_target` | `95.0 %` | Resume cleaning after charging to this % |
| `mission_strip_width` | `0.35 m` | Boustrophedon lane spacing (tighter = more coverage, closer to obstacles) |
| `headless` | `true` | `true` = no Gazebo GUI, `false` = show GUI |

---

## ✨ Features

- **Autonomous coverage cleaning** — boustrophedon (lawnmower) path planned from the live SLAM map
- **Live SLAM mapping** — `slam_toolbox` builds the map on the fly; no prebuilt map needed
- **Battery simulation** — drains while driving, published on `/battery_state`
- **Auto-docking** — returns to dock at low battery, laser-guided final creep, recharges, resumes cleaning
- **Obstacle avoidance** — sofa, table, plant, crates mapped and avoided via Nav2 costmaps
- **Two simulators** — Gazebo Harmonic (physics) or lightweight `fake_sim.py`

---

## 🔋 Battery & Docking

Battery is simulated in `house_cleaner_assistant.py`, tunable via ROS params:

| Parameter | Default | Role |
|-----------|---------|------|
| `battery.drain_rate` | `0.12 %/s` | Drain while driving |
| `battery.charge_rate` | `1.20 %/s` | Charge while docked |
| `battery.low_threshold` | `35.0 %` | Return to dock when below |
| `battery.charge_target` | `95.0 %` | Resume cleaning after charge |
| `mission.strip_width` | `0.60 m` | Boustrophedon lane spacing (coverage density) |
| `inflation_radius` (Nav2) | `0.70 m` | Costmap inflation for obstacle avoidance |

### Cleaning Around Walls & Furniture

For tighter coverage **between** walls and furniture (enabling cleaning closer to obstacles):

- Reduce `mission.strip_width` (default `0.60 m` → try `0.35 m` for denser paths)
- Reduce `inflation_radius` in `nav2_params.yaml` (default `0.70 m` → try `0.35 m`)
- Launch argument: `ros2 launch ... mission_strip_width:=0.35`

This allows the robot to clean closer to walls and furniture while Nav2's obstacle layer still prevents collisions.

---

## 🔁 Cleaning Mission Flow

```
CLEANING → (battery low) → RETURNING → DOCKING → CHARGING → UNDOCKING → RESUME
```

1. **CLEANING** — boustrophedon goals sent one-by-one via `/navigate_to_pose`
2. **Battery drain** — simulated while moving
3. **Low battery** — current goal cancelled, return to dock
4. **RETURNING** — navigate to dock approach `(0.0, 1.87)`
5. **DOCKING** — slow laser-guided creep until front laser < `0.13 m`
6. **CHARGING** — recharge until target
7. **UNDOCKING** — back out `~0.48 m`, resume cleaning
8. **Done** — all goals reached → park at dock

---

## 🗺️ World Geometry

| Item | Value |
|------|-------|
| Room interior | `4.65 m × 5.75 m` |
| Wall bounds | `x ∈ [-2.325, 2.325]`, `y ∈ [-2.875, 2.875]` |
| Map | `100 × 116` px @ `0.05 m/px` |
| Obstacles | sofa, coffee table, plant, crates |
| Dock center | `(0.0, 2.75)` |

---

## 🔍 Verify

```bash
ros2 topic list | grep -E '/(cmd_vel|map|scan|odom|tf|battery_state|dock_pose)'
ros2 lifecycle get /slam_toolbox          # expect "active"
ros2 lifecycle get /controller_server     # expect "active"
```

---

## 📁 Repository Layout

```
src/house_cleaner_bringup/
├── launch/    
│   ├── house_cleaning_auto.launch.py      ← primary (Gazebo + SLAM + Nav2 + assistant)
│   ├── house_cleaning_fake_sim.launch.py
│   ├── house_cleaning_slam.launch.py
│   └── gazebo_house_cleaning.launch.py
├── config/    nav2_params.yaml, slam_toolbox params, prebuilt map
├── house_cleaner_bringup/  
│   └── house_cleaner_assistant.py, fake_sim.py
├── scripts/   battery_monitor.py
└── worlds/    house_room.world
```

---

## ⚠️ Important Notes

- **Always kill stale ROS2 / Gazebo / RViz processes before relaunching** — overlapping instances cause stale TF and port conflicts.
- **Re-source `/opt/ros/jazzy/setup.bash` in every new terminal** — `PYTHONPATH` doesn't survive across sessions.
- **Use `source env.sh`** (not just `install/setup.bash`) — required for package prefix resolution on this host's old colcon.

## 🩹 Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `planner_server` crashes at launch | Costmap width/height must be integer cells | Use `93 × 115` cells, not `4.65 × 5.75` m |
| `ros2` command not found | Env not sourced | `source /opt/ros/jazzy/setup.bash` |
| Assistant times out waiting for `/map` | SLAM slower to start | Timeout is 120 s with progress logging — just wait |
| Mission skips goals | Map still growing | Normal — unreachable goals are skipped, mission continues |
| `/tf` empty or stale | Overlapping node instances | Kill all processes, relaunch one |

---

## 📌 Status

✅ Autonomous coverage from live SLAM · ✅ Battery + auto-docking · ✅ Obstacle avoidance · ✅ Two simulators · ✅ Docker image · ✅ GitHub (SSH)