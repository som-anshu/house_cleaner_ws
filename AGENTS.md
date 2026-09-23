# AGENTS.md — how to work in this repo

READ /home/koko/house_cleaner_ws/CONTEXT.md first. It holds environment facts,
root causes and the session ledger. Keep it updated as you work.

## Commands

- Launch stack headless (CI-like default): `./run_docker.sh --headless`
-   (from `/home/koko/house_cleaner_ws`). Prints READY when Nav2 lives.
- GUI **mission loop** (Gazebo GUI + RViz + restart coverage after dock):
  `./run_gui_loop.sh` — builds wildcard xauth, relaunches with
  `mission_loop:=true`, re-copies helpers, starts stall watchdog
  (`/tmp/opencode/watchdog.sh`, log `/tmp/opencode/watchdog.log`).
- Full GUI when X is up (`:0` present): first build a wildcard xauth cookie —
-   `xauth -f "$XAUTHORITY" nlist :0 | sed -e 's/^..../ffff/' | xauth -f /tmp/xauth_docker nmerge -`
-   then `XAUTHORITY=/tmp/xauth_docker ./run_docker.sh` (live cookie is unix-family
-   only, so TCP-forwarded clients fail auth without this).
  (from `/home/koko/house_cleaner_ws`). Prints READY when Nav2 lives.
- Stop: `docker stop house_cleaner_jazzy`. Relaunch creates a fresh container.
- Logs: `docker logs -f house_cleaner_jazzy`
- ROS commands inside container MUST go through the helper:
  `docker cp /tmp/opencode/ros_exec.sh house_cleaner_jazzy:/tmp/ros_exec.sh`
  then `docker exec house_cleaner_jazzy bash /tmp/ros_exec.sh <cmd...>`
  (`ros_exec.sh` sources /opt/ros/jazzy/setup.bash + /workspace/install/setup.bash).
- Do NOT try docker-exec one-liners with quotes/% — they break; use script files.
- Live battery acceleration: `ros2 param set /battery drain_rate 4.0`
  (restore `0.20` later). Re-read every 0.2 s tick.
- Config + src edits are bind-mounted → NO rebuild, just relaunch.
- Validate Python edits: `python3 -m py_compile <file>`, and relink if needed
  (`ls -la /workspace/install/.../lib/...`). Code is symlinked via
  `--symlink-install`, so no colcon rebuild required for `.py`/`.yaml` edits.

## Conventions

- Fake sim stand-alone: `python3 src/house_cleaner_mission/test/fake_sim.py`
- Keep the ledger (`CONTEXT.md` §5) append-only; don't drop history.
- Never change `entrypoint.sh`/Dockerfile/run_docker.sh without a rebuild in mind.
- Prefer headless boots for CI-like validation; GUI only if X is available.
- After any relaunch, re-`docker cp` the helper script into the new container.