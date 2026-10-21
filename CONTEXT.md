# CONTEXT.md — durable project ledger (read this first)

Read AGENTS.md for commands/conventions. This file is the long-lived record of
environment facts, architecture, root causes and session state. It survives model
context loss — treat it as the source of truth for "where are we".

## 1. Environment facts (do not re-derive)

- Workspace: this git repo. **No path is hardcoded anywhere** — every script
  resolves its own root via `ros-distro.sh`, which also sets `ROS_DISTRO`,
  `CONTAINER_NAME` (`house_cleaner_<distro>`) and `IMAGE_NAME`.
- ROS distro is **detected**, not assumed: lyrical on Ubuntu 26.04, jazzy on
  24.04, humble on 22.04. `source env.sh` gives you a working shell.
  Override with `export ROS_DISTRO=<name>` before running anything.
- Docker flavour is detected too: **native Linux engine vs Docker Desktop**.
  They need completely different display forwarding (see §6). The socat+xauth
  dance below only applies to Docker Desktop.
- Daemon recovery on a native engine: `sudo systemctl start docker`.
  On Docker Desktop: `systemctl --user start docker-desktop`.
- Image: `house_cleaner:<distro>`, built with
  `docker build --build-arg ROS_DISTRO=<distro>`. Container:
  `house_cleaner_<distro>`.
- `entrypoint.sh` is **baked into the image** — editing the host file needs
  `./run_docker.sh --build`.
- **X display: Xwayland `:0` may be present**, with a Wayland `wayland-0`
  socket alongside it. Prefer Wayland when the socket exists — it needs no
  authentication setup at all.
- Bind-mounted config means source/config edits need NO rebuild: the
  Dockerfile uses `colcon build --symlink-install` and `run_docker.sh` maps
  `src → /workspace/src:rw`.
- Readiness marker printed by the bash Nav2 bringup:
  `Nav2 lifecycle bringup complete`. `run_docker.sh` polls for it
  (90×2 s), and dumps `docker logs` on early exit.
- Live accelerate battery drain (params re-read every 0.2 s tick):
  `ros2 param set /battery drain_rate 4.0` → restore `0.20` when done.
  Battery model drains only when `not docked and speed > 0.03` (from /odom +
  /cmd_vel_smoothed + /cmd_vel).
- **docker exec gotcha**: quoting/`%` breaks one-liners. Write a script to the
  host, `docker cp` it, run it. Re-sync helpers into a NEW container each boot:
  `docker cp /tmp/opencode/ros_exec.sh "$CONTAINER_NAME:/tmp/ros_exec.sh"`.


## 2. Files (inventory)

- `CONTEXT.md` (this), `AGENTS.md`, `PROJECT_PLAN.md`, `README.md` — repo root docs.
- `src/house_cleaner_bringup/launch/house_cleaning.launch.py` — single entry point
  (mode:=sim/real, headless, gui, battery args). Contains:
  - bash Nav2 retry bringup (`nav2_activate`, 8 nodes × configure/activate ×120×1 s)
    printing the readiness marker. NOT nav2_lifecycle_manager (its `get_state()`
    default timeout is 2 s → aborts cold boots).
  - slam_toolbox bash activate (same pattern; manager can't bond to it).
  - rviz2 gated on `gui AND not headless`; foxglove gated on `gui` only.
  - `lifecycle_manager_local` for mode:=real (map_server/amcl).
- `src/house_cleaner_bringup/config/nav2_params.yaml` — all Nav2 params.
  **Contains `local_costmap`/`global_costmap` sections now** (they were missing — see §3).
- `src/house_cleaner_bringup/config/foxglove_layout.json`, `house_cleaning.rviz`, `slam_toolbox_gazebo_params.yaml`.
- `src/house_cleaner_battery/house_cleaner_battery/battery_sim.py` (+ `battery_hw.py`).
- `src/house_cleaner_docking/house_cleaner_docking/docking_controller.py` (+ `creep_to_dock` srv).
- `src/house_cleaner_mission/house_cleaner_mission/mission_supervisor.py` (+ `test/fake_sim.py`).
- Deleted: `house_cleaner_description` package (cleaned up earlier).

## 3. Root causes found & fixed (lifecycle/readiness, this effort)

1. `server_timeout: 90.0` under `lifecycle_manager_navigation` was a **no-op** —
   Jazzy `nav2_lifecycle_manager` does not declare it. Removed from nav2_params.yaml.
2. Real timeout: `nav2_util::LifecycleServiceClient::get_state()` default = **2 s**.
   Under cold-boot load the target node's executor is busy → call times out →
   manager aborts the whole bringup. Fix: bash retry loop (120×1 s per node),
   pattern proven from slam_toolbox.
3. `battery_sim` crashed at start: `AttributeError: 'BatterySim' object has no
   attribute '_odom_cb'` — subscription existed, method was missing. Added `_odom_cb`.
4. Goals REJECTED with "Action server is inactive" because `bt_navigator` advertised
   before going lifecycle-ACTIVE. Fix: `mission_supervisor._wait_nav2_active()` polls
   `/bt_navigator/get_state` until id==3 (ACTIVE), 120 s; Nav2 wait 60→180 s.
5. rviz2 gated behind `gui AND not headless` (no X display → SIGABRT).
6. **MPPI "Optimizer fail to compute path" + behavior_server "Current footprint not
   available" (the big one, fixed this session)**: `nav2_params.yaml` had **NO
   `local_costmap`/`global_costmap` sections**, so `/local_costmap/local_costmap`
   ran on **defaults**: `global_frame=map`, non-rolling 2.5 m window anchored at map
   origin, and **empty `observation_sources`** → costmap saw no scan → no obstacles,
   no footprint published → MPPI couldn't build any valid trajectory and every goal
   aborted `err=104`. Fix: added both sections — local = rolling 3×3 m, `global_frame=odom`,
   `robot_base_frame=base_footprint`, `obstacle_layer` subscribing to `/scan` (frame
   `base_scan`), `inflation_layer` radius 0.55; global = `static_layer` (from SLAM /map)
   + obstacle + inflation, `global_frame=map`. NOTE: `width`/`height` must be **int**
   in Jazzy (double → `InvalidParameterTypeException` → controller_server SIGABRT).

## 4. Stack architecture / data flow

- Gazebo Harmonic (headless OK) → /clock, /odom (50 Hz), /scan (50 Hz), TF.
- slam_toolbox → /map (94×116 live), map→odom.
- Nav2: controller_server (MPPI `nav2_mppi_controller::MPPIController`), planner_server
  (NavFn), smoother_server, behavior_server, bt_navigator, waypoint_follower,
  velocity_smoother, collision_monitor, + local/global costmap nodes (inside
  controller/planner server processes, namespaced `/local_costmap`, `/global_costmap`).
- cmd_vel chain: controller_server → /cmd_vel_nav → velocity_smoother →
  /cmd_vel_smoothed → collision_monitor → /cmd_vel (robot).
- battery_sim → /battery_state (drain on motion, charge when docked);
  docking_controller → dock pose, creep_to_dock, seated latch;
  mission_supervisor → 26-goal SLAM coverage, low-battery return-to-dock loop
  (`_watchdog_cb` cancels goal ≤35%, `_recharge_cycle` charges ≥95%, resumes mission).
- foxglove_bridge on 8765 (host may show `curl http://localhost:8765` → 000; verify
  inside container — not blocking).

## 5. Session ledger (append after each step)

- [DONE] CONTEXT.md + AGENTS.md written (then zeroed by corruption — rewritten).
- [DONE] fake_sim.py docstring fixed (`python3 test/fake_sim.py`).
- [DONE] server_timeout removed; lifecycle_manager → bash retry bringup; rviz2 headless gate.
- [DONE] battery_sim `_odom_cb`; supervisor `_wait_nav2_active` + 180 s Nav2 wait.
- [DONE] run_docker.sh: no `--rm`, readiness probe, log dump on early exit.
- [DONE] **Costmap config added** (`local_costmap`+`global_costmap`) → MPPI root cause.
  Verified after relaunch: costmap `global_frame=odom`, `rolling_window=true`,
  `observation_sources=scan`, obstacle_layer_raw ~1.4 Hz.
- [DONE] Navigation validation: goals 1→2→3→4/26 progressed (~50–180 s each,
  occasional `Failed to make progress` retries), odom moved across the room,
  battery drained 100→78.7%. Costmap fix resolved the standing MPPI deadlock.
- [DONE] **Accelerated battery-loop test (drain_rate=4.0)**: low-battery watchdog
  FIRED correctly — at 34.3% it cancelled the in-flight goal, logged
  `LOW BATTERY (34.3%)` and issued `[RETURNING] goal (0.00,1.87)` then
  `(0.00,2.75)` after the approach timed out. **BUT the robot could not reach the
  dock**: it was wedged against the SE wall/furniture (map (1.69,-2.09), scan
  ~0.18 m in all directions) — the SLAM coverage goal (-1.80,-1.84) sits inside
  the 0.55 m inflation band (coverage margin 0.37 + inflate 0.55), so MPPI saw
  "Collision Ahead" and both spin+follow_path failed. Supervisor correctly
  fallbacked: `Cannot reach dock (TIMEOUT) — skipping dock this cycle`,
  resumed cleaning, re-triggered at 0%. **Decision logic 100% validated;
  physical docking blocked by goal-in-inflation navigation geometry.**
- [KNOWN] With drain_rate 4.0 and a stuck robot, battery hits 0% quickly; drain
  model is motion-gated so this is expected, not a bug.
- [PENDING] Next: (a) inset coverage goals further from walls/purge the inflation
  band (e.g. bump coverge margin ≥ inflation_radius, or snap goals away from high
  inflated cost), and/or widen `movement_time_allowance`; then re-run the
  accelerated battery loop to see return→seat→charge→resume complete. (b) update
  ledger + consider git commit.
- [DONE] Container stopped after the test (stack is clean; next boot is fresh).
- [KNOWN] Docker daemon stops mid-session (socket gone). Debugged 2026-09-23:
  NOT a crash/OOM/disk-full — journal shows external stops only (`qemu
  terminating on signal 15 from pid 2788 (systemd)`, `explicit cancel`), 16 VM
  starts/3 d incl. a 12-restart storm on Sep 22. No ENOSPC/OOM/panic in 3 d of
  logs; host mem OK (8.1 G avail); VM disk only 3% used. Each stop kills the
  container (exit 255) — that code means daemon/VM died, not an app crash.
  FRAGILITY (unfixed, needs user): host disk 98% full (11 G free) and
  `Docker.raw` holds ~279 G of dead space (288 G actual vs 8.9 G live in VM;
  raw never shrinks without discard) — any burst write (e.g. image rebuild)
  risks real ENOSPC. Do NOT `builder prune` (frees nothing on host) and do NOT
  compact/delete Docker.raw without user approval.
- [DONE] run_docker.sh hardened for the above: daemon preflight (fail fast with
  `systemctl --user start docker-desktop` hint) + `--log-opt max-size=50m
  --log-opt max-file=5` on the detached run (verified via inspect; clean READY
  reboot after edit, battery 98.6% publishing, all Nav2 nodes present).
- [DONE] Geometry fixes for goal-in-inflation wedge: inflation_radius 0.55→0.35
  (both costmaps), coverage_bounds margin 0.37→0.55, behavior_server footprint
  topics → `*/published_footprint` (fixes "Current footprint not available" so
  spin/backup recovery can run), progress_checker movement_time_allowance
  30→60 s.
- [DONE] **Full GUI sim run (Sep 23)**: Xwayland `:0` present, so `./run_docker.sh`
  (no `--headless`) works after fixing X auth — live cookie is unix-family only,
  container connects over socat TCP → "Authorization required". Wildcard cookie
  recipe (see §1) fixed it: rviz2 on OpenGL 4.5, gazebo up, no display errors,
  container stays Up, mission started (24 goals, goal 1/24), 0 MPPI optimizer
  fails. GUI launch recipe now in AGENTS.md.
- [DONE] **Slowness debug (Sep 23, multi-factor, all evidenced)**:
  (a) MPPI output only ~0.10–0.14 m/s sim vs 0.5 cap (was 0.016 → 8x gain from
  inflation 0.35→0.25 + scaling 3→2 + vx_std 0.2→0.3), heavy yaw churn, 180 s
  goal timeouts with skips.
  (b) RTF only ~0.47–0.61: guest CPU 808% (rviz2 116% + gazebo ~200% llvmpipe +
  our python nodes ~150%) on host load 16→21/12 and rising.
  (c) velocity_smoother emits NOTHING for 20 s+ stretches (0 msgs vs 19 Hz Twist
  input; node ACTIVE, wiring correct) — starvation episodes fully stop robot;
  only BT spin bursts (direct /cmd_vel) get through. Odometry frozen while MPPI
  commands constant yaw.
  (d) "Passing new path" @1 Hz sim is BY DESIGN (BT =
  navigate_to_pose_w_replanning_and_recovery.xml), not a bug.
  (e) Reverted: CostCritic 0.5 experiment (confounded by monitor-stop wedge) and
  controller 10 Hz (MPPI requires period<=model_dt). Kept: inflation 0.25,
  scaling 2.0, vx_std 0.3, wz_std 0.6, batch 600, movement_time_allowance 60 s,
  coverage margin 0.55, footprint fix.
  Bigger levers left (not taken): headless-physics+GUI-viz split, async
  supervisor rewrite (blocking spins burn 65%), host load reduction.
- [DONE] **Disk emergency (Sep 23)**: host hit 100% (0 avail, was 11 G) mid-debug
  — Docker.raw stable at 288 G (not the grower). Freed 2.9 G via `pip cache
  purge` (428 files, safe/regenerable). Remaining growth (~7 G) is user data;
  do NOT touch. Lesson: keep 2 G+ headroom; never `--build` when tight.
- [DONE] **Docking crash fixed + full dock/charge mechanics validated (Sep 23)**:
  ROOT CAUSE of every "Docking controller (creep) unavailable": creep/undock
  service handlers called rclpy.spin_once INSIDE the executor (SingleThreaded)
  → deterministic "Executor is already spinning" RuntimeError → node died on
  EVERY creep attempt (pids 42, 43). Docking NEVER worked. Fix: MultiThreaded-
  Executor (3 threads) + threading.Lock around scan/odom state + time.sleep
  pacing instead of nested spins (bind-mounted src, egg-link live, no rebuild).
  VALIDATED end-to-end on furniture-dock (mechanics, not true dock):
  creep→seated=True (front 0.35, stall latch, NO crash) → CMD_START (missing
  piece: battery needs seated AND charging cmd; supervisor sends it) →
  battery 52→89% and climbing at charge_rate → undock success (no crash) →
  drain restored 0.20. Remaining unproven: TRUE dock approach (needs
  contact-free autonomous nav, still the blocker) + seated=False re-check.
- [DONE] **Slowness debug (Sep 23, multi-factor, all evidenced)**:
  (a) MPPI translational output only ~0.10–0.14 m/s sim vs 0.5 cap (was 0.016 at
  start → 8x gain from inflation 0.35→0.25 + scaling 3→2 + vx_std 0.2→0.3), with
  heavy yaw churn (cmd w med ~0.17, p90 ~1.0) and 180 s goal timeouts.
  (b) RTF only ~0.47–0.61: guest CPU 808% (rviz2 116% + gazebo ~200% llvmpipe +
  our python nodes ~150%) on host load 16→21/12 CPUs and rising.
  (c) velocity_smoother emits NOTHING for 20 s+ stretches (0 msgs vs 19 Hz input;
  node ACTIVE, wiring correct) — starvation episodes under peak load fully stop
  the robot; only BT spin bursts (direct /cmd_vel) get through.
  (d) "Passing new path" @1 Hz sim is BY DESIGN (BT =
  navigate_to_pose_w_replanning_and_recovery.xml), not a bug.
  (e) Dead ends ruled out: CostCritic 0.5 experiment reverted (confounded by
  monitor-stop wedge); controller 10 Hz attempt reverted (MPPI requires
  period<=model_dt: "Controller period more then model dt" kills configure).
   Net: no single bug — crawl (costs) × RTF 0.5 (CPU) × stalls (starvation) ×
   recovery churn. Bigger levers left (not taken): headless-physics+GUI-viz
   split, async supervisor rewrite (blocking spin_until_future_complete burns
   ~65% of one core), host load reduction.
- [DONE] **Permanent speed increases + stuck root-cause fix + full mission
  validation (Sep 23, post-reboot)**:
  Speed (all permanent in bind-mounted config, verified live):
  MPPI vx_max 0.5→0.65 / wz_max 1.9→2.5 / temperature 0.5 / CostCritic
  3.81→2.5 / PathAlign occupancy 0.05→0.25 / PreferForward 5→2;
  amcl robot_max_vel_trans 0.3→0.65, robot_max_vel_theta 1.0→2.5;
  velocity_smoother max_vel [0.65,0,2.5] accel [1.5,0,3.0] decel [-2,0,-3.5];
  goal xy/yaw 0.18/0.20; progress 45s→55s / radius 0.08; inflation 0.25→0.30
  scaling 2.0→2.5 both costmaps; local costmap 3×3→4×4; collision_monitor
  PolygonSlow (limit 45%, 0.12–0.35 m) ahead of PolygonStop; mission
  strip_width 0.45 (18→~7–15 goals); send_goal default 90 s, first CLEANING
  goal 120 s cold-start; teleop scale 0.65/2.0.
  Stuck ROOT CAUSE: coverage goals landed on furniture because SLAM leaves
  interiors unknown (-1) and (a) snap_to_free_row treated `c < 50` as free
  (unknown passed) (b) _goal_blocked used `c >= 100` on OccupancyGrid 0–100
  (entire inflation band 1–99 + unknown passed). Robot then MPPI-crawled →
  Failed to make progress / 100 s TIMEOUT. Fix: geometry.is_known_free
  (0≤occ<50 only), snap/revalidate block unknown; mission FURNITURE_KEEPOUT
  AABBs (+0.55, dock body only, approach free) + in_furniture_keepout filter
  at plan time + _goal_blocked keepout/unknown/c>=50; TIMEOUT now retries
  once (was skip-immediately).
  VALIDATED live (GUI, post-PC-reboot): `Filtered 8 goal(s) in furniture
  keep-out` → 7 goals over x∈[-1.79,1.81] y∈[-2.35,2.35]; 5/7 reached
  (g1 cold-start TIMEOUT, g6 progress-collapsed control loop 8 Hz under load
  18 — both transient, not keepout); COVERAGE COMPLETE → RETURNING →
  DOCKING → **DOCKED seated** → CHARGING 84.5→95.1% → `Staying docked
  (mission done)`. First TRUE dock approach via autonomous nav worked.
  Helpers recreated this boot: /tmp/opencode/{ros_exec,cancel_nav,diag_stuck,
  probe_costmap}. NOTE: ros_exec.sh must NOT use `set -u` (AMENT_TRACE_
  SETUP_FILES unbound in setup.bash). XAUTH cookie regenerated
  (94 bytes). Sudo: passwordless ALL for koko. Disk 95% (23 G free) — still
  no --build.
- [DONE] **Second stuck root cause — local costmap track_unknown_space (Sep 23)**:
  After relaunch, goal 1 (0.53,-1.45) still TIMEOUTd at 120 s + retry, robot
  wedged at (0.41,-1.09) with front scan clear 0.86 m, cmd≈0, spin recovery
  `Collision Ahead`. Probe: **local costmap 97% unknown (-1)** (free only
  32→155 cells over minutes; global free at same pose). Cause: local_costmap
  had `track_unknown_space: true` with ONLY obstacle_layer (no static) —
  rolling window starts -1, raytrace never fills fast enough, MPPI CostCritic
  treats unknown as blocked → zero cmd → free space never grows (death
  spiral). behavior_server also aborts spin when footprint sits on unknown.
   Fix: local_costmap `track_unknown_space: false` (unknown→FREE, only laser
   marks are obstacles); global stays true. yaml asserted local=False global=True.
   TIMEOUT now retries once; progress_checker movement_time_allowance 55 s;
   first CLEANING goal gets 120 s cold-start timeout (default 90 s).
- [DONE] **Stuck root cause #3 — coffee-table wedge + reverse blocked
  (Sep 23)**: After keepout=0.32 + local costmap fix: g1–g3 fast (~27 s);
  robot later wedged at (−0.213,−0.220) yaw 27° — coffee-table NE corner,
  front scan 0.16 m (PolygonStop edge), cmd≈0; PreferForwardCritic 2.0
  discouraged reverse escape; CostCritic under-clear. Fixes that STUCK (all
  live-verified after relaunch): PreferForward `cost_weight: 0.0` (free
  reverse), CostCritic `cost_weight: 3.5`. REVERTED/FORBIDDEN:
  `GridBased.allow_unknown: false` — Navfn failed "Failed to create plan
  with tolerance of: 0.250000" on valid early-SLAM free space → value is
  **true** with comment (mitigation = PreferForward 0 + CostCritic 3.5 +
  laser costmap + keepout); `CostCritic.consider_footprint: true` — MPPI
  configure dies "Considering footprint… no robot footprint provided" while
  costmaps only set `robot_radius` (no polygon) → value is **false** with
  comment. Local costmap `track_unknown_space: false` (global true) verified.
- [DONE] **Battery percentage scale bug — infinite dock loop (Sep 23)**:
  ROOT CAUSE of CHARGED→UNDOCK→immediate-LOW-BATTERY loop: battery_sim/hw
  published `percentage` 0–100 while `mission_supervisor._battery_cb` does
  `pct * 100 if 0<=pct<=1 else pct` → real 0.96% read as 96% → "CHARGED to
  96.0%" after ~1 s → undock → real 0.96% ≤ 35 → immediate re-return.
  Fix: both publishers emit `battery_pct / 100.0` (ROS standard 0..1);
  supervisor conversion left unchanged (0.0→0, 0.35→35, 0.96→96, 1.0→100).
  py_compile OK; after relaunch `/battery_state percentage` ≈ 0.90 (fraction).
  battery_monitor.py uses the same `<=1.0` heuristic — now consistent.
- [DONE] **Post-fix relaunch + accelerated charge-loop re-validation (Sep 23, headless)**:
  `./run_docker.sh --headless` → READY. Helpers re-copied to
  `/tmp/{ros_exec,cancel_nav,diag_stuck,probe_costmap,set_drain}`.
  Build hardlinks to bind-mounted src (same inode; realpath →
  `/workspace/src/...`) — no rebuild for `.py`. Processes pid 42/43/44
  started 13:37:31 UTC **after** source mtimes 13:32–13:33; imported
  modules contain all fix markers (`charge_timeout`/livelock/plant 0.50,
  no-blind-creep/stall 0.22, `/100`, TRANSIENT_LOCAL, CMD_START).
  Live at boot: `/battery_state percentage=0.977` (fraction),
  `drain_rate=0.2`, `/dock/seated` RELIABLE+TRANSIENT_LOCAL pub=
  `/docking_controller` subs=`/battery`+`/mission_supervisor`. No
  Tracebacks / "Executor is already spinning".
  Accelerated re-validation (`set_drain.sh 4.0`): Filtered 5 → 10 goals;
  g1 done ~22 s (chronic early TIMEOUT cleared); g2 TIMEOUT×2 → skip
  (retry path works); g3 done; **LOW BATTERY 34.6% → RETURNING →
  DOCKING → DOCKED seated → charging enabled → CHARGING 0→95% →
  CHARGED to 95.0% → UNDOCKING** (full cycle under fixed mission+docking
  logic). drain_rate restored to **0.20**. Host load 10–15 (was 18).
  Disk 95% / 23 G free. entrypoint.sh `--launch` fix still needs image
  rebuild (baked); default launch path does not use `--launch`, so this
  boot is unaffected.
- [DONE] **Whole-code logical-error audit + fixes (Sep 23)**:
  Critical: (1) `fake_sim.py` had truncated `rclpy.spin` → bare `r`
  (NameError; fixed). (2) `run_docker.sh --build` leaked `--build` into
  container argv → entrypoint `exec --build` (strips host-only flags
  `--build/--headless/--shell` before `docker run`). (3) `entrypoint.sh
  --launch` double-shifted and duplicated the package name
  (`ros2 launch pkg pkg file`) — rewritten as a single index walk over
  ARGS (NOTE: entrypoint is **baked** — needs image rebuild to take
  effect; run_docker.sh is host-side, immediate).
  High mission: charge wait now has 300 s deadline + abort if seat lost;
  low-battery cancel during ABORTED/TIMEOUT **retry** no longer permanently
  skips the goal; final_park only logs "Staying docked" when `dock_ok`
  (returns False otherwise); livelock guard — if still ≤low% and not
  seated after recharge, break remaining goals; undock failure is logged.
  High docking: creep **stops** when laser is None (no blind drive);
  stall/flat seated latch only inside `stop_range+0.22` (was 0.40 —
  false-seat on furniture); `/dock/seated` is TRANSIENT_LOCAL (pub+subs
  in battery_sim + supervisor); undock returns success only if integrated
  reverse progress ≥ ½ commanded distance; blocked undock does not force
  seated=False.
  Medium: plant keepout clearance 0.32→0.50 (point AABB); battery
  percentage -1/NaN ignored (supervisor + monitor); battery_hw CMD_START
  arms `charging=True`, CMD_STOP clears; power_supply_status only
  CHARGING when actually charging (sim+hw). All py_compile + bash -n +
  entrypoint/run_docker parse smoke tests pass. Helpers/X11+Wayland
  unchanged. Disk 95% / 23 G free — no --build unless user approves
  (needed for entrypoint.sh fix).
  GUI stack READY; helpers re-copied. Run: Filtered 5 goals → 10 planned;
  g1–3 done fast; g4 TIMEOUT×2 (last=CANCELED by low-battery race) — only
  miss; **LOW BATTERY 35.0% → RETURNING → DOCKING → DOCKED seated →
  CHARGING 0%→95% → UNDOCK → Resuming (1st true cycle, no loop)**; g5–7
  done (coffee-table region free after critic fixes); **LOW BATTERY 33.4%
  → second full dock/charge/resume**; g8–10 done; **COVERAGE COMPLETE
  (9/10 reached)** → final RETURNING → DOCKED → CHARGED 95.0% →
  **`Staying docked (mission done)`**. Final `/battery_state percentage`
  0.9504 (fraction). **Stuck #3 cleared + low-battery loop validated
  end-to-end.** drain_rate restored to 0.20 (`bash /tmp/set_drain.sh 0.20`,
  node name is `/battery`). Container still Up; helpers in /tmp.
  [KNOWN] g4 still the only recurring miss (row-blocked / low-battery cancel
  race) — not a wedge; goal-skip path works. Host load ~16–17, RTF ~0.5 —
   performance levers still open. X11+Wayland both kept in
   Dockerfile (qtwayland5, libwayland*, libx11*, x11-xserver-utils) and
   run_docker.sh auto-detects session type.
- [DONE] **Docker.raw compaction + image rebuild bake entrypoint (Sep 23, user-approved sudo)**:
  Host was 95% / 23 G free; Docker.raw allocated 287 G (virtual 409 G).
  Path: (1) `fallocate -d` dig-holes → 260 G; (2) virt-sparsify blocked
  (supermin can't read root-only `/boot/vmlinuz-*`, `--no-check-super` not
  in 1.54.0); (3) **loop-mount partition at offset 1 MiB + `e2fsck -fy` +
  `fstrim` → allocated 260 → 13.2 G** (trimmed 395.3 GiB free blocks).
  Host **95%→23% / 52→299 G free** at that point.
  Rebuild `./run_docker.sh --build` (first attempt tool-timeout canceled
  mid-apt; apt-get update busts layer cache so full reinstall re-ran ~19 min
  + colcon 13 s + export 105 s) → image **2d67bf012da9**, entrypoint
  `diff` **matches host source**. Baked `--launch` smoke: prints
  `Launching custom: demo_nodes_cpp talker` (single pkg — double-shift fix
  live). X11+Wayland packages still in Dockerfile (grep 3).
  Post-rebuild relaunch READY; helpers re-copied; `/battery drain_rate=0.2`;
  `/battery_state percentage≈0.990` (fraction); `/dock/seated` RELIABLE +
  TRANSIENT_LOCAL pub=docking_controller subs=battery(+mission_supervisor).
  Host **97 G used / 292 G free (25%)**; Docker.raw allocated **20.3 G**
  (grew ~7 G for new layers — still ~240 G below pre-compaction).
  `docker system df`: 1 image 5.26 GB, build cache 4.27 G (0 reclaimable).
  [NOTE] leftover `/opt/docker-desktop/bin/com.docker.build` helper may
  linger after canceled builds — safe to kill when no `docker build -t`.
  [KNOWN] rclpy double-`shutdown` on SIGINT for docking/battery/mission
  during container stop (exit code 1 on teardown only — runtime OK).
- [DONE] **GUI + mission_loop demo (Sep 23)**: `mission.loop` param +
  launch `mission_loop` (default false). When true, final dock parks then
  undocks and restarts coverage forever. Launcher:
  `./run_gui_loop.sh` → wildcard xauth `/tmp/xauth_docker`, socat TCP:6000,
  `XAUTHORITY=... ./run_docker.sh --launch house_cleaner_bringup
  house_cleaning.launch.py mode:=sim headless:=false use_sim_time:=true
  gui:=true mission_loop:=true`, re-copies helpers, starts
  `/tmp/opencode/watchdog.sh` (pid log `/tmp/opencode/watchdog.log`;
  no new mission line 180s → `diag_stuck.py` dump; container down →
  auto-relaunch via run_gui_loop). Live: **loop=True**, windows
  `Gazebo Sim (on <id>)` + `RViz`, gz server+gui, mission advancing
  (g1 retry, **g4 TIMEOUT×2 skip — known miss**, g5–8 done under host
  load ~16). Helpers present. Parallel run_gui_loop races on container
  name — run one at a time; only one watchdog.sh after settle.
  **First full loop observed live (ROS2 tools):** coverage 7/9 → RETURNING →
  DOCKED seated → CHARGING 85.3→95% → `Parked at dock (mission loop)` →
  `MISSION LOOP — undocking` → `/dock/seated false` → **CLEANING goal 1/9
  next pass**. `ros2 doctor`: all 5 checks passed. Lifecycle
  bt_navigator/controller/planner/slam `active [3]`. Actions: 12 listed;
  `/navigate_to_pose` clients×3 (bt_navigator, waypoint_follower,
  mission_supervisor) + server×1. `/clock` ~390–600 Hz, `/cmd_vel` ~19–21 Hz,
   `/battery_state` ~3.2 Hz. TF map→base_footprint live. Watchdog
   `/tmp/opencode/watchdog.sh` PID 67837 logging progress lines.
- [DONE] **Fix TF/BT/dock-cascade freezes (Sep 23 evening)**: user saw robot
  appear still + dock skip. Root causes (ROS2 tools): goals stamped `now()`
  raced lagging `map→odom` → controller `extrapolation into the future` /
  `Unable to transform goal pose` → **FollowPath TF_ERROR (err=102)**;
  `bt_navigator default_server_timeout` default **20 ms** too tight under
  host load → BT `Timed out while waiting for action server to acknowledge`
  → instant ABORTED (dock pose died in ~65 ms after approach abort);
  progress_checker 8 cm/55 s false-stalled near-dock cells (g8).
  Fixes: `_pose_msg` stamp=0 (latest TF) + `_settle_nav` after non-success
  goals; cleaning `err==102` settle+one retry; `_recharge_cycle` settle
  before dock + 2× approach retries + 2× dock-pose retries;
  `default_server_timeout: 5000`, MPPI `transform_tolerance: 0.5`,
  `failure_tolerance: 2.0`, progress_checker 90 s / 0.05 m.
  Relaunched `./run_gui_loop.sh` (id 61cfdcb18f22). **Validated live:**
  TF extrapolate 0, BT ack timeout 0, Failed-to-make-progress 0, err=102 0,
  `Cannot reach dock` 0. Coverage 6/8 → RETURNING → CHARGING 84.7→95.1% →
  `Parked at dock` → `MISSION LOOP` undock → pass 2 goal 1/8. Live params:
  `default_server_timeout=5000`, `failure_tolerance=2.0`,
  `movement_time_allowance=90.0`. Gazebo+RViz windows up.
  [KNOWN] occasional pure TIMEOUT skips remain (host load / path), not TF.
- [DONE] **Stuck-case prevention: budget / empty / vel-chain / recover (Sep 24)**:
  Sep 23 night robot sat still while mission kept logging RETURNING goals —
  battery hit 0 %, `/cmd_vel_nav` ~18 Hz but `/cmd_vel` silent, host load ~16,
  watchdog never fired (fresh goal line every 30–90 s).
  Fixes: `mission.return_budget` (180 s wall) bounds whole RETURNING nav;
  `battery.critical` (1%) hard-aborts nav/mission when empty (no ~460 s retry
  chains); velocity-chain liveness (`/cmd_vel_nav` live + `/cmd_vel` stale +
  speed≈0 → `VEL_CHAIN_STALL` cancel); async `send_goal` spin_once loop checks
  abort reasons every 100 ms; `battery_sim` empty latch + UNKNOWN status at 0%;
  `behavior_server` remapped to `cmd_vel_nav` (no safety bypass); low_threshold
  default 35→40; `watchdog.sh` recover mode (stuck-pattern / empty / vel-chain
  → cancel_nav + bounce smoother+collision_monitor, then full restart);
   `scripts/{cancel_nav,diag_stuck}.py` sample full cmd chain. Relaunch
   `./run_gui_loop.sh` to pick up bind-mounted code.
- [DONE] **Validate prevention stack + fix VEL_STALL false positives (Sep 24)**:
  Relaunched with fixes live: ready line `low=40% critical=1.0% return_budget=180s`;
  `behavior_server` pubs only `/cmd_vel_nav`; coverage → RETURNING (budget 180s)
  → docked → charged 82→95% → loop undock. First post-fix pass then hit a
  **VEL_STALL storm** (2 s `/cmd_vel` threshold too tight under host load ~16;
  probe showed multi-second out gaps + sparse nav → 0/10 reached, return loop
  of VEL_STALL cancels). Fix: `mission.stall_hold` **8.0 s** gates out_age
  (param on mission_supervisor); watchdog always runs `probe_reason` (was
  skipped when every log line differed) and counts plain `VEL_STALL` in
  STUCK_PATTERN. Relaunch validated: `stall_hold=8.0` live, **0 VEL_STALL in
  90 s**, goals 1–8/9 completing, single recover-mode watchdog PID.
  [KNOWN] host load ~16 / RTF ~0.5 still causes occasional TIMEOUT skips.

## 6. Portability model (added 2026-10-09)

The project was originally developed on a machine with Docker Desktop, ROS 2
Jazzy and hardcoded `/home/koko/...` paths. Every one of those assumptions has
been removed.

`ros-distro.sh` is the single source of truth. It is sourced by `env.sh`,
`run_docker.sh`, `run_gui_loop.sh`, `watchdog.sh`, `monitor_loop.sh`,
`batt_probe2.sh` and `docker-compose.yml`, and by the Dockerfile via
`--build-arg`. It sets:

| Var | Meaning |
| --- | --- |
| `ROS_DISTRO` | Respects an explicit value; otherwise picks the newest installed LTS; otherwise guesses from the Ubuntu codename |
| `ROS_ROOT`, `ROS_SETUP` | `/opt/ros/<distro>` and its `setup.bash` |
| `WS_DIR` | Repo root, resolved from the script's own location |
| `CONTAINER_NAME` | `house_cleaner_<distro>` |
| `IMAGE_NAME` | `house_cleaner:<distro>` |
| `TURTLEBOT3_MODEL`, `ROS_DOMAIN_ID` | `burger`, `30` unless already set |

Choosing new distros requires editing only the `_rd_candidates` line and the
codename case block in `ros-distro.sh`.

### Docker flavour detection

`run_docker.sh` distinguishes a **native Linux engine** from **Docker
Desktop**, because they need entirely different display forwarding:

- **Native** — the container shares the host's filesystem, so mounting
  `/tmp/.X11-unix` and `$XDG_RUNTIME_DIR` just works. This is the fast, simple
  path: no `socat`, no wildcard xauth cookie, no `host.docker.internal`.
- **Docker Desktop** — containers run in a VM that cannot see the host's unix
  sockets, so X must be tunneled over TCP and a wildcard cookie built. The old
  code only ever did this, which is why it failed on a native engine.

Flavour is decided from `DOCKER_HOST`, falling back to `docker context show`.

### GPU

The old script always mounted `/dev/dri` and baked
`LIBGL_ALWAYS_SOFTWARE=1`, so a host GPU was never used and the simulator
crawled. Now:

1. NVIDIA runtime present (`nvidia-smi` works and `docker info` lists `nvidia`)
   → `--gpus all` + `NVIDIA_DRIVER_CAPABILITIES=all`
2. else `/dev/dri` present → mount it
3. else → software rendering

`LIBGL_ALWAYS_SOFTWARE` is auto-set from the result and is no longer baked
into the image; an explicit value in the environment always wins.

### GUI

Wayland is preferred when `$XDG_RUNTIME_DIR/wayland-0` exists — no
authentication to get wrong. X11 is the fallback.

### Known porting risks (verify after a rebuild)

- **Gazebo version changes with the distro**: lyrical → Jetty (gz-sim 10),
  jazzy → Harmonic (gz-sim 8), humble → Fortress (gz-sim 6). `worlds/` and
  `models/` SDF may need version-specific adjustments; the wall model is
  deliberately simple to minimise this.
- **Community packages**: `turtlebot3-gazebo` and `turtlebot3-description`
  must have binaries for the target distro on packages.ros.org.
- **Python version**: lyrical uses Python 3.14, where a `ament_python` entry
  point generation bug has been reported (`ros2 run` failing with
  `ModuleNotFoundError` even after a clean `colcon build`). If a console
  script is missing from `/workspace/install/lib/<pkg>/`, this is the cause —
  fix by ensuring the system `python3-setuptools` and `python3-wheel` are
  installed, not by installing anything with pip.

### Ledger

- [DONE] **Portability overhaul (2026-10-09)**: `ros-distro.sh` added as the
  single source of truth; `Dockerfile` takes `ROS_DISTRO` as a build arg;
  `run_docker.sh` rewritten with Docker-flavour detection, Wayland support,
  GPU auto-detection and an `LIBGL_ALWAYS_SOFTWARE` auto-default;
  `entrypoint.sh`, `watchdog.sh`, `monitor_loop.sh`, `batt_probe2.sh`,
  `run_gui_loop.sh` and `docker-compose.yml` all made distro- and path-
  independent; every `/home/koko/...` absolute path removed. All scripts pass
  `bash -n` and the compose file passes a YAML parse. Verified: distro
  detection picks an installed distro over the preference list, honours an
  explicit `ROS_DISTRO`, and falls back to the right distro per Ubuntu
  codename; `run_docker.sh` builds correct argument sets for
  Wayland+NVIDIA, X11+Docker-Desktop, and headless.
  Not yet verified: a real image build, because ROS 2 and Docker were not
  installed on the target machine at the time of the change.

- [DONE] **GUI mission-loop stability pass (2026-10-20)**: five root causes
  found and fixed; two full cleaning → return → dock → charge → undock →
  resume cycles then ran with **zero watchdog restarts**.
  1. **`TwistStamped` vs `Twist`** — `enable_stamped_cmd_vel: false` on
     `controller_server` + `behavior_server` (already in place before this
     pass); without it Nav2 published nothing the bridge understood.
  2. **Docking crash** — `self.get_logger().warn(...)` in
     `docking_controller.py` (lines 243/304). `warn()` was removed from
     Lyrical's rclpy, so the node died the moment a creep attempt failed
     (which is why clean first-try docks worked and failed ones lost the
     node). Changed to `warning()` and rebuilt `house_cleaner_docking`.
  3. **Collision-monitor deadlock** — `PolygonStop` (`action_type: stop`)
     forced `req_vel` to zero every cycle; after `stop_pub_timeout` Nav2's
     collision monitor *ceases publishing `/cmd_vel` entirely*
     (`publishVelocity()` in `nav2_collision_monitor_node.cpp`). Because the
     robot was stopped, the obstacle never left the 3–15 cm front polygon,
     so the chain stayed silent forever and every later goal looked like a
     dead velocity chain (VEL_STALL storms → watchdog full restarts). The
     stop polygon is removed; `PolygonSlow` (45 %) and MPPI avoidance remain.
     `source_timeout` raised 1.0 → 3.0 s so a slow scan under host load does
     not trip the fail-safe.
  4. **Stale `map→odom` after undock** — `minimum_travel_distance: 0.5` while
     the undock backs out exactly 0.48 m, so slam_toolbox never re-matched
     the final move. The robot's map pose stayed inside the dock and the
     planner aborted every goal with "Failed to create plan with tolerance
     of: 0.300000" (goal unreachable from an enclosed start). Lowered to
     `minimum_travel_distance: 0.15` / `minimum_travel_heading: 0.20`.
  5. **Mission fail-fast** — cleaning goal timeout 90 → 45 s (first goal and
     RETURNING stay at 90 s); `xy_goal_tolerance` / `yaw_goal_tolerance`
     0.20/0.22 → 0.30/0.30 (MPPI settles ~0.28 m short and never satisfied
     the old checker); new `NAV_SILENT` detector (MPPI alive but commanding
     zero for 15 s) skips a frozen point in ~20 s instead of the full
     timeout; `ABORTED` planner failures are skipped without the wasted
     retry; return-to-dock walks five nearby approach candidates instead of
     the unplannable dock pose (creep is laser-guided, so any pose roughly in
     front works). Planner `tolerance` 0.25 → 0.30 (must stay ≤ the goal
     checker's xy tolerance).
  Validation: boot gate sends goal 1 within ms of collision_monitor ACTIVE;
  pass 1 8/10, pass 2 9/10 reached; return in ~2 s; dock seated (creep
  retries once after a failed attempt), charge to 95 %, undock, resume;
  watchdog log shows only `progress:` lines (0 RECOVER / 0 FULL_RESTART);
  freeze dumps show the remaining skips are near-goal cells with an obstacle
  within ~0.13 m, handled in ~20 s.

### 2026-10-21 — one-command launcher (`run_all.sh`) + Foxglove protocol note
- New `run_all.sh`: kill stale instances (watchdog + battery monitor first —
  the watchdog would relaunch a container we are removing — then `docker rm -f`
  the container, then sweep host strays from native runs) → `run_gui_loop.sh`
  (launch + helper copy + watchdog) → looping battery monitor (`APPEND=1
  monitor_loop.sh`, history kept in `/tmp/opencode/dockloop.txt`) → built-in
  health check: container, gz-sim-main, rviz2, Nav2 READY marker, Foxglove
  WebSocket 101 handshake, `/battery_state`, watchdog, monitor.
  Flags: `--stop` (kill only), `--verify` (checks only). Re-execs itself via
  `sg docker -c` when the session lacks the docker group (group membership
  applied at login; `docker info` → "permission denied" otherwise).
  `Makefile` launch/stop/verify now wrap it; dropped the stale
  `../launch_gui.py` reference and the hardcoded `lyrical` in `setup` /
  check targets (uses `ros-distro.sh` detection like everything else).
- Verification bugs found and fixed while testing the verifier itself:
  1. RViz spawns a few seconds *after* the Nav2 READY marker, so a single
     instantaneous probe reported a false FAIL right after launch — checks now
     retry for ~60 s (`retry` helper, 12 × 5 s).
  2. `docker logs | grep -q PATTERN` under `set -o pipefail` returns 141
     (SIGPIPE: `grep -q` exits on first match, closing the log stream) once
     the log is large — it only appeared to work while the log was tiny
     right after boot. `clog_has`/`ctop_has` disable pipefail locally.
- Foxglove: the bridge (3.6.0) is WebSocket-only and requires the
  `foxglove.sdk.v1` subprotocol; a plain GET to :8765 returns 400 "Missing
  expected sec-websocket-protocol header". Open https://app.foxglove.dev and
  connect to `ws://localhost:8765` — it is not a web page. The verifier
  probes with a real upgrade request expecting HTTP 101.
- Full `./run_all.sh` run validated end-to-end: killed 3 accumulated stale
  watchdogs from previous boots, removed the old container, READY in ~90 s,
  all 8 checks [OK]; `--stop` and `--verify` also exercised.

### 2026-10-21 — research-level project documentation (`DOCUMENTATION.md`)
- New single-file reference manual (1304 lines / ~9.4k words, A4-friendly:
  no table wider than 5 columns). Sections: aim & objectives, tech stack,
  features, file/package structure, node graph + interface contracts (topic /
  action / service / TF tables), launch system, mission state machine,
  algorithms, non-coder pseudocode, configuration reference, deployment &
  fault recovery, launch instructions, testing, future work, glossary,
  references.
- Diagrams are Mermaid (renders on GitHub): 2 × `flowchart TB`, 1 ×
  `flowchart LR` node graph, 1 × `sequenceDiagram` boot order, 1 ×
  `stateDiagram-v2` mission states; ASCII pseudocode blocks elsewhere.
- Tabular purpose/input/output tables for every root script, source file and
  launch/config file — the request was explicit about per-file I/O tables.
- Algorithms documented with their real tuned numbers and the *reason* each
  value was chosen: boustrophedon coverage, goal revalidation + keep-out,
  NavFn Dijkstra, MPPI (critics table), goal/progress checkers, slam_toolbox
  travel gating, laser creep (stall + flat-clearance latches), undock
  verification, the three fault-detection layers (VEL_STALL / NAV_SILENT /
  RETURN_BUDGET, host watchdog probes), and the safety chain.
- Verification of the doc itself: balanced code fences (48), consistent pipe
  counts in every Markdown table, valid Mermaid headers. One table row was
  fixed after lint (a literal `|` inside an inline code span split the row).

### 2026-10-21 — presentation deck (`docs/House_Cleaner_Robot.pptx`)
- 16-slide, deliberately non-technical deck explaining the project to a
  general audience: what it is, the 5-step mission loop, mapping, lawnmower
  planning, navigator vs driver, battery thresholds, docking, the three
  babysitter layers, the four program groups, memorable numbers, the
  one-command launch, what you see on screen, real problems-and-fixes, and
  the roadmap. Every slide carries speaker notes.
- Generated by `tools/make_ppt.py` (python-pptx), so the deck is
  reproducible and diffable in review rather than being a binary artefact
  nobody can regenerate. Installed `python-pptx` into **conda base** — the
  system ROS interpreter is left untouched per the machine rules.
- Two self-checks ship with it because the layout was verified rather than
  eyeballed (this model cannot view images):
  * `tools/check_ppt.py` — geometry from the .pptx (shapes on-slide,
    non-nested text-box overlaps, estimated text overflow).
  * `tools/check_rendered.py` — parses `pdftotext -bbox-layout` output, i.e.
    what LibreOffice *actually drew*: text past the page edge, cross-box
    text clashes, slides with suspiciously little content.
- Real defects this caught and fixed: slide 1's five-step strip ran 0.22 in
  off the right edge; the footer strip on eight slides collided with the
  page-number box (footer narrowed to 11.48 in); slide 14's column labels
  sat on top of the kicker; slide 15's cards were ~0.9 in too short for
  their body text. Final render: 16 pages, widest content 943.2 pt against a
  959.98 pt page, 0 collisions.
- `libreoffice-impress` installed on the host (headless PDF conversion) and
  `docs/` added; README gained a "Presentations & Documentation" section.

### 2026-10-21 — technical deck (`docs/House_Cleaner_Robot_Technical.pptx`)
- A second 16-slide deck telling the same story in real ROS 2 / Nav2
  vocabulary, for a technical audience: the four interface contracts
  (action/service/topics + QoS), the node graph and topic direction, the
  velocity chain and the TwistStamped/Twist mismatch, the lifecycle ACTIVE
  gate, boustrophedon coverage with the real `geometry.py` API names,
  NavFn + MPPI (critic weights as configured), SLAM travel gates and costmap
  layers, the mission FSM transitions, every `send_goal()` status and its
  handler, the three watchdog tiers, laser-guided creep with the actual
  `CreepToDock` .srv content, the `PolygonSlow`-vs-`PolygonStop` deadlock,
  the battery model, and `run_all.sh` plus its eight checks. Speaker notes on
  every slide.
- Facts were verified against source before writing: interface names, QoS
  durability (the latched `/dock/seated` TRANSIENT_LOCAL pair), MPPI
  parameters, tolerances, the .srv body and the battery threshold values.
- Generated by `tools/make_ppt_technical.py` (same helpers/style as
  `make_ppt.py`), verified with the same two checkers. One real defect
  caught: slide 16's footer was a single three-run line whose wrapped text
  (three lines) overlapped the italic closing line beneath it — split into
  three one-line footers at 6.06/6.50/6.94 in. Final render: 16 pages, no
  text past the page edge, 0 cross-box clashes, 0 estimator overlaps.

### 2026-10-21 — post-reboot GUI failure: X cookie + Foxglove probe
- Symptom after a reboot: `./run_all.sh` came up but the verifier reported
  `[FAIL] RViz not running` and `[FAIL] Foxglove handshake returned HTTP 000`.
- Root cause 1 (RViz): the desktop is GNOME/Mutter with XWayland, so the X
  cookie now lives in `$XDG_RUNTIME_DIR/.mutter-Xwaylandauth.<random>` and is
  recreated on every login — `~/.Xauthority` **does not exist**. The native
  X11 path in `run_docker.sh` passed no cookie and relied on `xhost +local:`
  only, which is insufficient because a container process is not "local" to
  the X server. rviz2 died with:
  `Authorization required, but no authorization protocol specified` /
  `qt.qpa.xcb: could not connect to display :0`.
  Fix: `run_docker.sh` now builds the cookie ONCE (searching `$XAUTHORITY`,
  then the newest `$XDG_RUNTIME_DIR/.mutter-Xwaylandauth.*`, then
  `~/.Xauthority`) and mounts it read-only as `/tmp/xauth_cookie` with
  `XAUTHORITY` set, on BOTH the native and Docker-Desktop paths. The
  Docker-Desktop branch no longer duplicates the logic; `xhost` stays as a
  best-effort extra, and a missing cookie now prints an actionable warning
  (`xhost +local:root`) instead of failing silently.
- Root cause 2 (Foxglove): the bridge was healthy — `ss` shows `0.0.0.0:8765`
  listening and the upgrade returns 101. The probe was a bare single-shot,
  so it caught the window right after a watchdog relaunch when the listener
  had not re-bound yet, and reported HTTP 000. `curl` also exits 28 on a
  SUCCESSFUL upgrade (the socket is held open), so only the status code is
  meaningful. Fix: the check is now a `foxglove_up()` predicate wrapped in
  the existing `retry` helper (~60 s), matching the RViz/Nav2 checks.
- Verified: relaunch reports `X cookie: /run/user/1000/.mutter-Xwaylandauth.*
  (mounted read-only)`, all 8 checks `[OK]`, rviz2 alive with no Qt/auth
  errors, and the mission cleaning (goal 3/9 done, ~7 s per goal).


