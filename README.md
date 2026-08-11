# house_cleaner_ws — Autonomous House-Cleaning Robot (ROS 2 Jazzy + Gazebo Harmonic)

Simulation of a TurtleBot3 Burger that autonomously cleans any unknown room:

- **Live SLAM** (slam_toolbox) — no prebuilt map; the room is mapped as the
  robot drives, so the same stack works in any room.
- **Coverage cleaning** — boustrophedon lanes over the live map, executed as
  Nav2 navigation goals (sofa, coffee table, plant, crates as obstacles).
- **Auto-charging** — at low battery the robot cancels cleaning, navigates to
  its dock, laser-guided docking creep, recharge, and resumes where it left
  off. It also returns to dock and parks after coverage is complete.
- Battery is simulated by the assistant node (no Gazebo plugin needed) and
  published on `/battery_state`.

Verified end to end: 16/16 coverage goals, low-battery return, docking,
recharge, resume, final park.

## Quick start

```bash
export TURTLEBOT3_MODEL=burger
source env.sh
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py
```

Tunable launch args: `battery_drain_rate:=0.2` (%/s while driving),
`battery_charge_rate:=0.8` (%/s while docked), `battery_low_threshold:=35.0`,
`battery_charge_target:=95.0`, `headless:=false` (Gazebo GUI).

Fast demo cycle (drains in a couple of minutes instead of ~15):

```bash
ros2 launch house_cleaner_bringup house_cleaning_auto.launch.py \
  battery_drain_rate:=0.6 battery_charge_rate:=1.5
```

Watch it live: `rviz2` + Map/TF displays on the live `/map`, or launch with
`headless:=false` for the Gazebo GUI. Assistant logs print mission state
(`CLEANING goal n/16`, `LOW BATTERY`, `DOCKED`, `CHARGING`,
`Staying docked (mission done)`).

## Other launch variants

| Launch | What it runs |
|---|---|
| `house_cleaning_auto.launch.py` | **the demo** — Gazebo + SLAM + Nav2 + assistant |
| `house_cleaning_gazebo_nav.launch.py` | Nav2 on the saved map (map_server + AMCL); no SLAM; navigate on a known room |
| `house_cleaning_gazebo_slam.launch.py` | Gazebo + SLAM only — drive around to build/check a map |
| `house_cleaning_fake_sim.launch.py` | no-Gazebo Nav2 sandbox (synthetic odom + scan; same server chain as the auto variant) |
| `house_cleaning_slam.launch.py` | no-Gazebo SLAM sandbox (fake sim + slam_toolbox) |

## Architecture

```
Gazebo (house_room.world, burger, dock, furniture)
  │  /clock /odom /scan /tf  (ros_gz_bridge, plain-Twist /cmd_vel)
  ▼
slam_toolbox ──(async)──► /map + map->odom        Nav2 (planner, controller,
  │                                                   smoother, collision_monitor,
  ▼                                                   bt_navigator, waypoints)
house_cleaner_assistant ──NavigateToPose goals──►
  ├─ wait_for_map (SLAM live) → boustrophedon grid → 16 goals
  ├─ watchdog: battery <= threshold → cancel goal → return to dock
  ├─ creep_to_dock: laser-guided approach + seating verification
  ├─ recharge to target → resume cleaning
  └─ final park when coverage done
```

Key files:

- `house_cleaner_bringup/house_cleaner_assistant.py` — mission logic
- `worlds/house_room.world` — room (4.65×5.75 m interior), obstacles, dock
- `config/nav2_params.yaml` — Nav2 tuning (global costmap has no fixed
  bounds — it must follow the growing SLAM map)
- `config/slam_toolbox_gazebo_params.yaml` — SLAM params
- `config/burger_bridge.yaml` — Gazebo topic bridge (`/cmd_vel` is plain
  `geometry_msgs/Twist`, which Nav2 publishes; the stock TurtleBot bridge
  uses TwistStamped and does not work with Nav2)
- `config/house_room_map.yaml` — saved SLAM map for the localization variant
- `env.sh` — canonical environment (see Troubleshooting)

## Troubleshooting

- **Always `source env.sh`, not `install/setup.bash`.** This host's colcon
  (< 1.5) writes hook-style `package.dsv` files that drop the
  `AMENT_PREFIX_PATH` chain, so `ros2 launch house_cleaner_bringup ...` fails
  with "Package not found" otherwise. `env.sh` prepends the workspace package
  prefixes explicitly.
- **Kill stale instances before relaunching**: `tmux kill-session -t
  house_auto` (if using tmux) and kill leftover `gz sim` / `ros2 launch`
  processes — overlapping sims corrupt TF and costmaps.
- **Rebuild after editing config/launch/worlds**: launch files resolve these
  via the installed share dir, and on this host the install is real files
  (not symlinks), so `colcon build --packages-select house_cleaner_bringup`
  is needed to propagate edits.
- Nav2 goal status (Jazzy): 4 = SUCCEEDED, 5 = CANCELED, 6 = ABORTED.
- LDS scan index 0 is the robot's *forward* (angle 0), index 180 the back.
- The dock sits on the floor (z = 0); a floating dock passes under the robot
  body and the lidar never sees it.