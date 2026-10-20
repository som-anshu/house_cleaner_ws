# AGENTS.md — how to work in this repo

READ CONTEXT.md first. It holds environment facts, root causes and the session
ledger. Keep it updated as you work.

## Portable by design

Nothing in this repo hardcodes a ROS distro, a username or an absolute path.
Source `ros-distro.sh` (or just `env.sh`) and everything else follows:

| Variable | Set by | Example |
| --- | --- | --- |
| `ROS_DISTRO` | `ros-distro.sh` | `lyrical` |
| `CONTAINER_NAME` | `ros-distro.sh` | `house_cleaner_lyrical` |
| `IMAGE_NAME` | `ros-distro.sh` | `house_cleaner:lyrical` |
| `WS_DIR` | `ros-distro.sh` | repo root |

Override the distro by exporting `ROS_DISTRO` before running anything. Never
edit a script to change the distro.

`env.sh` is the single command for a working ROS shell on the host:

```sh
source env.sh
```

## Commands

Run everything from the repo root.

- **One command for the whole GUI setup: `./run_all.sh`** — kills stale
  instances (watchdog, battery monitor, old container), launches Gazebo GUI +
  RViz + Foxglove bridge + mission loop + watchdog + looping battery monitor,
  then health-checks every piece. Flags: `--stop` (kill stale only),
  `--verify` (checks only). Re-execs through `sg docker` automatically when
  the session lacks the docker group. `make launch` / `make stop` /
  `make verify` wrap the same script.
- Launch stack headless (CI-like default): `./run_docker.sh --headless`
  Prints READY when Nav2 lives.
- GUI **mission loop** (Gazebo GUI + RViz + restart coverage after dock):
  `./run_gui_loop.sh` — relaunches with `mission_loop:=true`, copies helpers,
  starts the stall watchdog (`/tmp/opencode/watchdog.sh`, log
  `/tmp/opencode/watchdog.log`).
- Full GUI when a display is present: `./run_docker.sh` —
  it auto-detects Wayland or X11, and native Docker vs Docker Desktop.
- Stop: `docker stop "$CONTAINER_NAME"`. Relaunch creates a fresh container.
- Logs: `docker logs -f "$CONTAINER_NAME"`
- ROS commands inside the container MUST go through the helper:
  `docker cp /tmp/opencode/ros_exec.sh "$CONTAINER_NAME:/tmp/ros_exec.sh"`
  then `docker exec "$CONTAINER_NAME" bash /tmp/ros_exec.sh <cmd...>`
- Do NOT try docker-exec one-liners with quotes or `%` — they break; use
  script files.
- Live battery acceleration: `ros2 param set /battery drain_rate 4.0`
  (restore `0.20` later). Re-read every 0.2 s tick.
- Stall recovery: `watchdog.sh` (repo root) — on log-silence, repeated
  RETURNING TIMEOUT / BATTERY EMPTY / VEL_CHAIN_STALL, or `/cmd_vel` dead
  while `/cmd_vel_nav` live: `scripts/cancel_nav.py` + a lifecycle bounce of
  `velocity_smoother`/`collision_monitor`, then a full `run_gui_loop.sh` after
  2 soft failures. Helpers are copied into the container by `run_gui_loop.sh`.
- Mission knobs: `battery.low_threshold` default **40%**, `battery.critical`
  **1%** (hard abort), `mission.return_budget` **180 s** (RETURNING nav wall
  budget), `mission.stall_hold` **8.0 s**. Launch: `battery_low_threshold`,
  `mission_return_budget`, `mission_loop`.
- Config and `src/` edits are bind-mounted → NO rebuild, just relaunch.
- Validate Python edits: `python3 -m py_compile <file>`, and relink if needed.
  Code is symlinked via `--symlink-install`, so no colcon rebuild for
  `.py`/`.yaml` edits.

### Environment variables that matter

| Variable | Default | Why |
| --- | --- | --- |
| `ROS_DOMAIN_ID` | `30` | Isolates this robot from others on the network. Must match between host and container. |
| `TURTLEBOT3_MODEL` | `burger` | The target robot. |
| `LIBGL_ALWAYS_SOFTWARE` | unset → auto | `1` forces llvmpipe. Only set it when there is genuinely no GPU; auto-detection handles the rest. |

## Conventions

- Fake sim stand-alone: `python3 src/house_cleaner_mission/test/fake_sim.py`
- Keep the ledger (`CONTEXT.md` §5) append-only; don't drop history.
- Prefer headless boots for CI-like validation; GUI only if a display exists.
- After any relaunch, helpers must be re-`docker cp`'d into the new container.
  `run_gui_loop.sh` does this for you.
- Prefer host networking in Docker. DDS discovery is multicast and Docker's
  bridge network drops it, so a container without `--network host` silently
  cannot see the host.
- Never bake `LIBGL_ALWAYS_SOFTWARE=1` into the image or scripts.

## Changing the entrypoint, Dockerfile or run scripts

`entrypoint.sh` is **baked into the image**. Editing the host file has no
effect until you rebuild, and `apt-get update` in the build invalidates the
layer cache, so a rebuild re-downloads everything. Use `./run_docker.sh
--build` and expect it to take a while. `run_docker.sh` itself is host-side and
takes effect immediately.
