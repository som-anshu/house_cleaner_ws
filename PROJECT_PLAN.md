# House Cleaner Robot — Project Plan & Progress

## Objective

Transform `house_cleaner_ws` into a clean, modular, Docker-based ROS2 Jazzy
package set for the TurtleBot3 Burger, running Gazebo Harmonic in Docker on
Linux X11/Wayland (no VNC), and structured so the same code runs on real
hardware.  The single `house_cleaning.launch.py` drives both
`mode:=sim` (SLAM + Gazebo) and `mode:=real` (map_server + AMCL + hardware).

## Decisions (locked)

- Linux X11 + Wayland only (Docker GUI), no VNC.
- Stay on ROS2 Jazzy + Gazebo Harmonic (upgrade only if blocked).
- Target: TurtleBot3 Burger + custom dock/charger.
- Architecture: **split packages** (msgs / core / battery / docking /
  mission / description / bringup), not a monolith.
- All folder permissions verified (koko owns every workspace dir).

---

## Package layout (implemented)

```
src/
├── house_cleaner_msgs        # interfaces: DockCommand, DockState, CreepToDock
├── house_cleaner_core        # pure-Python coverage/geometry (no ROS dep)
├── house_cleaner_battery     # battery_sim + battery_hw, same contract
├── house_cleaner_docking     # laser-guided docking_controller + /undock
├── house_cleaner_mission     # mission_supervisor (coverage/battery/dock)
├── house_cleaner_description # (reserved) custom burger/dock URDF
└── house_cleaner_bringup     # launch + config + worlds + models + scripts
```

`house_cleaner_bringup` is a pure `ament_cmake` package (launch/config/
worlds/models/scripts only — no runtime Python nodes).

### Shared contract (sim == real)

| Topic / Service                 | Type                                   | Producer              |
|---------------------------------|----------------------------------------|-----------------------|
| `/battery_state` (pub)          | sensor_msgs/BatteryState               | battery_sim / hw      |
| `/dock/state` (pub)             | house_cleaner_msgs/DockState           | battery_sim / hw      |
| `/dock/command` (sub)           | house_cleaner_msgs/DockCommand         | mission_supervisor    |
| `/dock/seated` (sub/pub)        | std_msgs/Bool                          | docking_controller    |
| `/creep_to_dock` (srv)          | house_cleaner_msgs/CreepToDock         | docking_controller    |
| `/undock` (srv)                 | std_srvs/Trigger                       | docking_controller    |
| `/navigate_to_pose` (action)    | nav2_msgs/NavigateToPose               | Nav2 bt_navigator     |

Real-hardware inputs (wired via the dock): `/dock/current` (Float64),
`/dock/fault` (Bool), `/battery_state_opencr` (raw BMS, must differ from the
node's own `/battery_state` output to avoid a feedback loop).

### Velocity chain (Nav2, critical fix)

```
controller_server --/cmd_vel_nav--> velocity_smoother --/cmd_vel_smoothed-->
   collision_monitor --/cmd_vel--> gz bridge (or robot driver)
```

- `collision_monitor` is the **last** node before `/cmd_vel` (per Nav2 docs).
- Docking creep publishes on `/cmd_vel_nav` so it flows through the same
  smoother + collision_monitor; the front polygon (`PolygonStop`, 0.03–0.15 m)
  is the last-resort bumper — the docking controller's stall / flat-window
  latch seats the robot when the monitor presses it in.
- `velocity_smoother` first. `controller_server` remaps out to `/cmd_vel_nav`.

---

## Implementation status

### Completed

- **P0 fix — launch NameError / headless inversion**
  - Old `house_cleaning_auto.launch.py` referenced undefined
    `gazebo_sim_gui` (NameError); removed.
  - `gazebo_house_cleaning.launch.py` used `IfCondition(headless)` (inverted);
    rewritten with `UnlessCondition(headless)` + GPU/software env options.
  - Redundant `house_cleaning_headless.launch.py` and
    `gazebo_house_cleaning_headless.launch.py` removed — headless is now a
    launch arg (`headless:=true`).
- **P0 fix — Nav2 params**
  - `nav2_params.yaml` rewritten for Jazzy: MPPI controller (robot_radius
    0.105), Navfn planner, full bt_navigator plugin list, behavior_server
    plugins (spin/back_up/drive_on_heading/wait), velocity_smoother limits,
    waypoint_follower, collision_monitor (scan source, PolygonStop,
    `enable_stamped_cmd_vel: false`), lifecycle_manager with all 8 nodes.
  - slam_toolbox stays a lifecycle node (plain LifecycleNode, no bond) —
    activated directly via `slam_activate` ExecuteProcess, not the manager.
- **P0 fix — run_docker.sh X11**
  - Auto-detects X11 vs Wayland; mounts `/tmp/.X11-unix` + xauth cookie (no
    bare `xhost +`), `/dev/dri` when present, `--shm-size`, `-p 8765:8765`;
    `LIBGL_ALWAYS_SOFTWARE` fallback; mounts `./src` (rw) over the image's
    built tree (no `:/workspace:ro` clobber).
- **P1 — modularization** (all new packages build skeleton + logic written):
  - `house_cleaner_msgs` (ament_cmake + rosidl) — msg/srv interfaces.
  - `house_cleaner_core` — geometry.py: yaw/quat, cell_value,
    snap_to_free_row, revalidate_goal, build_boustrophedon, coverage_bounds.
  - `house_cleaner_battery` — battery_sim.py (drain on `/cmd_vel_smoothed`
    + `/cmd_vel`, charge when seated+CMD_START, publishes `/battery_state` +
    `/dock/state`), battery_hw.py (BMS + dock GPIO/current inputs).
  - `house_cleaner_docking` — docking_controller.py: azimuth-aware front
    sector, creep with seat/stall/flat-window, timeouts, retries, services
    `/creep_to_dock` + `/undock`, publishes `/dock/seated`.
  - `house_cleaner_mission` — mission_supervisor.py: INIT→CLEANING→
    RETURNING→DOCKING→CHARGING→UNDOCKING→DONE state machine, NavigateToPose
    async client, coverage from house_cleaner_core, 0.5s low-battery watchdog,
    manual-spin executor pattern.
- **P1 — bringup cleanup**: removed fake_sim.py (moved to
  `house_cleaner_mission/test/fake_sim.py`), removed old assistant + setup.py;
  package.xml dropped to ament_cmake deps; CMakeLists installs launch/config/
  worlds/models + scripts to `lib/${PROJECT_NAME}`.
- **Unified launch**: `house_cleaning.launch.py` — `mode:=sim|real`,
  `gui:=true|false`, `headless:=true|false`; wires Gazebo/SLAM/Nav2
  (slam_activate), battery_sim|battery_hw, docking_controller
  (`velocity_topic:=/cmd_vel_nav`), mission_supervisor, rviz2, foxglove;
  real mode adds map_server + amcl + lifecycle_manager_localization.
- **Docker infra**: Dockerfile (added qtwayland, xauth, libxkbcommon,
  nav2-bringup; correct `.bashrc` source order), docker-compose.yml, and
  entrypoint rewritten for the new launch file / X11+Wayland.
- **RViz config** `config/house_cleaning.rviz` — proper .rviz display config
  (was wrongly pointing rviz2 `-d` at a YAML).
- All Python packages pass `py_compile`; YAML configs parse; bash scripts
  pass `bash -n`.

### Pending

- **Build + smoke test**: no colcon/ROS2 in the host environment (the stack
  builds inside Docker).  Run `./run_docker.sh --build` then the GUI launch,
  verify the checklist below.  Fix any build/launch-time issues surfaced.
- **`house_cleaner_description`**: directory reserved but empty — decide
  whether to vendor burger/dock URDF or keep using turtlebot3_description.
- **Real-hardware bringup**: `mode:=real` expects the TurtleBot3 driver
  (OpenCR, LDS) publishing /odom, /scan, /joint_states as a separate process;
  add `turtlebot3_bringup` to the Dockerfile / a bringup script when going
  physical.  Map file required via `map:=`.

---

## Docker usage

```bash
./run_docker.sh                 # GUI (auto X11/Wayland)
./run_docker.sh --build         # force rebuild
./run_docker.sh --headless      # server-only, Foxglove still on :8765
./run_docker.sh --shell         # interactive bash
```

Native (with colcon + ros-jazzy deps installed):
```bash
source env.sh
ros2 launch house_cleaner_bringup house_cleaning.launch.py mode:=sim
```

---

## Validation checklist

- [ ] `docker build -t house_cleaner:jazzy .` succeeds
- [ ] Gazebo GUI launches and shows `house_room.world` (X11 and Wayland)
- [ ] TurtleBot3 Burger spawns at (0,0); TF tree complete
- [ ] `ros2 lifecycle get /slam_toolbox` == active; `/map` publishes
- [ ] Nav2 lifecycle nodes active (all 8 via manager)
- [ ] `<cmd_vel` only from collision_monitor; teleop reaches the robot
- [ ] Battery drains while driving, charges seated, low-battery return works
- [ ] Auto-dock: approach → creep → seated → charge → undock → resume
- [ ] Full boustrophedon coverage completes then parks at dock
- [ ] Foxglove connects at http://localhost:8765
- [ ] RViz2 (`-d house_cleaning.rviz`) shows map, scan, robot model
- [ ] `mode:=real` structure launches (map_server/amcl) with a saved map