#!/usr/bin/env python3
"""
house_cleaner_assistant.py

Autonomous cleaning + auto-charging supervisor for the house_cleaner robot.

Runs a complete cleaning mission in an UNKNOWN room (works with any room the
robot can map — slam_toolbox builds the map live, no prebuilt map needed):

  CLEANING   -> boustrophedon coverage via Nav2 /navigate_to_pose
  battery    -> drains while driving, simulated /battery_state
  low bat    -> RETURNING: navigate to dock approach pose
             -> DOCKING: laser-guided final creep into the dock
             -> CHARGING: battery recharges
             -> UNDOCKING: back out, resume coverage
  coverage   -> complete: return to dock and stay (mission done)

Everything is driven from ROS params so demo timing can be tuned:

  battery.drain_rate     %/s while driving          (default 0.12)
  battery.charge_rate    %/s while docked           (default 1.20)
  battery.low_threshold  %  -> return to dock       (default 35.0)
  battery.charge_target  %  -> resume cleaning      (default 95.0)
  mission.strip_width    m  boustrophedon spacing   (default 0.60)

Room geometry (house_room.world interior):
  x in [-2.325, 2.325], y in [-2.875, 2.875]
Dock (world == map frame at start):
  dock body center (0.0, 2.75), south face y = 2.625
  approach pose (0.0, 1.87) yaw +pi/2, docked pose (0.0, ~2.50) yaw +pi/2
"""

import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, ReliabilityPolicy

from geometry_msgs.msg import Pose, PoseStamped, Point, Quaternion, Twist
from std_msgs.msg import Header
from sensor_msgs.msg import BatteryState, LaserScan
from nav_msgs.msg import Odometry, OccupancyGrid
from nav2_msgs.action import NavigateToPose
from tf2_ros import TransformListener, Buffer

# Room interior (world == initial map frame; matches house_room.world walls)
X_MIN, X_MAX = -2.325, 2.325
Y_MIN, Y_MAX = -2.875, 2.875

# Dock geometry (map frame; override with params dock.x / dock.y / dock.yaw)
DOCK_CENTER = (0.0, 2.75)
DOCK_YAW = math.pi / 2.0      # robot faces +y (north) into the dock
DOCK_APPROACH_BACK = 0.88     # approach pose is this far south of dock.y
CREEP_STOP_RANGE = 0.13       # laser front range at which we are seated
CREEP_SPEED = 0.04
CREEP_TIMEOUT = 30.0
UNDOCK_SPEED = -0.06
UNDOCK_TIME = 8.0  # back out ~0.5 m: clear of the dock's costmap inflation

# battery constants
VOLTAGE_FULL = 12.6
VOLTAGE_EMPTY = 10.0


def yaw_from_quat(q):
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


class HouseCleanerAssistant(Node):
    def __init__(self):
        super().__init__("house_cleaner_assistant")

        self.declare_parameter("battery.drain_rate", 0.12)
        self.declare_parameter("battery.charge_rate", 1.20)
        self.declare_parameter("battery.low_threshold", 35.0)
        self.declare_parameter("battery.charge_target", 95.0)
        self.declare_parameter("mission.strip_width", 0.60)
        self.declare_parameter("dock.x", DOCK_CENTER[0])
        self.declare_parameter("dock.y", DOCK_CENTER[1])
        self.declare_parameter("dock.yaw", DOCK_YAW)

        self.drain_rate = self.get_parameter("battery.drain_rate").value
        self.charge_rate = self.get_parameter("battery.charge_rate").value
        self.low_threshold = self.get_parameter("battery.low_threshold").value
        self.charge_target = self.get_parameter("battery.charge_target").value
        strip = self.get_parameter("mission.strip_width").value
        self.dock = (
            self.get_parameter("dock.x").value,
            self.get_parameter("dock.y").value,
            self.get_parameter("dock.yaw").value,
        )

        # battery state
        self.battery_pct = 100.0
        self.docked = False
        self.speed = 0.0

        # publishers / subscribers
        self.battery_pub = self.create_publisher(BatteryState, "/battery_state", 10)
        self.dock_pose_pub = self.create_publisher(PoseStamped, "/dock_pose", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Odometry, "/odom", self.odom_cb, 10)
        self.create_subscription(LaserScan, "/scan", self.scan_cb, 10)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # action client
        self.nav = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self.goal_handle = None

        # mission state (goals are planned from the live SLAM map in
        # run_mission, once the map is known — see _coverage_bounds)
        self.strip = strip
        self.goals = None
        self.goal_idx = 0
        self.state = "INIT"
        self.low_battery_fired = False
        self.last_scan = None
        self._creep_win = []

        # live /map + global costmap for execution-time goal revalidation:
        # plan-time snapping can't see furniture that reads unknown (-1)
        # while the map is still sparse, so each goal is re-checked against
        # the matured map/costmap right before it is sent (see _revalidate_goal)
        self.last_grid = None
        self.last_costmap = None
        self.create_subscription(OccupancyGrid, "/map", self._map_cb, 10)
        self.create_subscription(OccupancyGrid, "/global_costmap/costmap", self._costmap_cb,
                                 QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))

        # timers
        self.create_timer(0.2, self.battery_timer_cb)
        self.create_timer(0.5, self.watchdog_cb)

        self.get_logger().info(
            f"Assistant ready: strip={strip:.2f} m, "
            f"drain={self.drain_rate:.2f}%/s charge={self.charge_rate:.2f}%/s, "
            f"low={self.low_threshold:.0f}% target={self.charge_target:.0f}%, "
            f"dock=({self.dock[0]:.2f}, {self.dock[1]:.2f}, "
            f"yaw={math.degrees(self.dock[2]):.0f}deg)"
        )

    # ------------------------------------------------------------- helpers
    def _coverage_bounds(self, grid):
        """Derive the cleaning rectangle from the live SLAM map.

        Bounds come from the map window (origin + size), inset by the robot
        half-width + margin, clamped to stay clear of the dock's apron, with
        a sane minimum so a barely-started map still yields usable goals.
        This is what makes the mission work in ANY mapped room instead of
        this room's hardcoded constants.
        """
        info = grid.info
        margin = 0.37  # robot_radius 0.22 + wall margin
        x_min = info.origin.position.x + margin
        y_min = info.origin.position.y + margin
        x_max = info.origin.position.x + info.width * info.resolution - margin
        y_max = info.origin.position.y + info.height * info.resolution - margin

        if x_max - x_min < 2.0 or y_max - y_min < 1.0:
            # degenerate window — fall back to this room's proven geometry
            self.get_logger().warn(
                f"Map window too small ({x_max - x_min:.1f}x{y_max - y_min:.1f} m) "
                "— using fallback bounds"
            )
            return (X_MIN, X_MAX, Y_MIN, Y_MAX)
        return (x_min, x_max, y_min, y_max)

    def _build_goals(self, strip, bounds, grid=None):
        """Boustrophedon coverage grid over the given rectangle.

        Goals are clamped away from the exact bounds by ``strip/2`` so they
        stay inside the SLAM costmap even while the map is still resizing.

        If an occupancy grid is passed, every goal is validated against it:
        a goal whose cell is occupied is snapped to the nearest free cell in
        the same row (boustrophedon pattern preserved), or dropped when no
        free cell exists nearby.  Without this, a goal landing inside an
        obstacle (e.g. the sofa when the map window shifts by one cell)
        makes Nav2 replan forever, drain the battery, and loop in
        recharge cycles — the module-16 live failure.
        """
        x_min, x_max, y_min, y_max = bounds
        margin = strip / 2.0
        x_min = x_min + margin
        x_max = x_max - margin
        y_min = y_min + margin
        y_max = y_max - margin

        if x_max <= x_min or y_max <= y_min:
            self.get_logger().warn(
                f"Coverage rectangle too small after clamping "
                f"({x_max - x_min:.2f}x{y_max - y_min:.2f} m) — skipping mission"
            )
            return []

        goals = []
        y = y_min + strip / 2.0
        row = 0
        while y <= y_max - strip / 2.0:
            if row % 2 == 0:
                x0, x1, yaw0, yaw1 = x_min, x_max, 0.0, math.pi
            else:
                x0, x1, yaw0, yaw1 = x_max, x_min, math.pi, 0.0
            for x, yaw in ((x0, yaw0), (x1, yaw1)):
                if grid is not None:
                    snapped = self._snap_to_free(grid, x, y)
                    if snapped is None:
                        continue  # no free cell on this row — skip goal
                    x, y = snapped
                goals.append((x, y, yaw))
            y += strip
            row += 1
        return goals

    def _cell(self, grid, x, y):
        """Occupancy [0-100] at world (x, y), or None when out of window."""
        info = grid.info
        col = int((x - info.origin.position.x) / info.resolution)
        row = int((y - info.origin.position.y) / info.resolution)
        if col < 0 or row < 0 or col >= info.width or row >= info.height:
            return None
        return grid.data[row * info.width + col]

    def _map_cb(self, msg):
        self.last_grid = msg

    def _costmap_cb(self, msg):
        self.last_costmap = msg

    def _goal_blocked(self, cm, x, y):
        """True when the robot center cannot occupy world (x, y) at execution time.

        Only Nav2's inscribed-inflation semantics block: cost 253 (inscribed)
        / 254 (lethal) means the robot's footprint cannot be centered there.
        Unknown (255) and out-of-window (None) are NOT treated as blocked —
        the global costmap lags the SLAM map at mission start and goals near
        walls would otherwise be yanked; the sweep in _revalidate_goal only
        needs to escape confirmed-lethal cells.
        """
        c = self._cell(cm, x, y)
        return c is not None and c >= 253 and c != 255

    def _occupancy_blocked(self, grid, x, y):
        """Occupancy fallback: only confirmed-occupied cells block (>= 50).

        Unknown (-1) stays cleanable — the costmap (with live obstacle layer)
        is the authoritative check; this is just a pre-costmap fallback.
        """
        occ = self._cell(grid, x, y)
        return occ is not None and occ >= 50

    def _revalidate_goal(self, x, y):
        """Re-check a plan-time goal against the matured map/costmap.

        Returns (x, y, drop) — drop is a reason string when the whole row
        within the 2 m sweep is blocked (caller skips the goal), else None.
        Plan-time snapping can't see furniture that still reads unknown at
        t~5s, so every goal is re-snapped here right before it is sent.
        """
        cm = self.last_costmap
        if cm is not None:
            blocked = self._goal_blocked
            src = cm
        elif self.last_grid is not None:
            blocked = self._occupancy_blocked
            src = self.last_grid
        else:
            return (x, y, None)  # no data yet — send as planned

        if not blocked(src, x, y):
            return (x, y, None)

        info = src.info
        max_cells = int(2.0 / info.resolution)  # 2 m sweep each way
        for step in range(1, max_cells + 1):
            for cx in (x + step * info.resolution, x - step * info.resolution):
                if cx == x:
                    continue
                c = self._cell(src, cx, y)
                if c is None:
                    continue  # off-window snap target — not a valid escape
                if not blocked(src, cx, y):
                    return (cx, y, None)
        return (x, y, "row blocked within 2 m sweep")

    def _snap_to_free(self, grid, x, y):
        """Nearest free cell on row y to (x, y); occupied -> nudge, else None.

        Returns the adjusted (x, y) or None when the whole row near the goal
        is blocked/unknown.  Row-scan keeps the boustrophedon pattern intact
        instead of creating diagonal detours.
        """
        info = grid.info
        occ = self._cell(grid, x, y)
        if occ is not None and occ < 50:  # free
            return (x, y)
        # scan outward from the goal cell along x, both directions
        max_cells = int(2.0 / info.resolution)  # 2 m sweep each way
        for step in range(1, max_cells + 1):
            for cx in (x + step * info.resolution, x - step * info.resolution):
                c = self._cell(grid, cx, y)
                if c is None:
                    continue  # outside window — treat as blocked
                if c < 50:
                    return (cx, y)
        return None

    def _pose_msg(self, x, y, yaw):
        return PoseStamped(
            header=Header(frame_id="map", stamp=self.get_clock().now().to_msg()),
            pose=Pose(
                position=Point(x=x, y=y, z=0.0),
                orientation=Quaternion(
                    x=0.0, y=0.0,
                    z=math.sin(yaw / 2.0), w=math.cos(yaw / 2.0),
                ),
            ),
        )

    def odom_cb(self, msg):
        v = msg.twist.twist.linear
        self.speed = math.hypot(v.x, v.y)

    def scan_cb(self, msg):
        self.last_scan = msg

    def battery_timer_cb(self):
        dt = 0.2
        if self.docked and self.battery_pct < 100.0:
            self.battery_pct = min(100.0, self.battery_pct + self.charge_rate * dt)
        elif not self.docked and self.speed > 0.03:
            self.battery_pct = max(0.0, self.battery_pct - self.drain_rate * dt)

        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = VOLTAGE_EMPTY + (VOLTAGE_FULL - VOLTAGE_EMPTY) * (self.battery_pct / 100.0)
        msg.percentage = self.battery_pct
        msg.present = True
        if self.docked:
            msg.power_supply_status = (
                BatteryState.POWER_SUPPLY_STATUS_FULL
                if self.battery_pct >= 99.9
                else BatteryState.POWER_SUPPLY_STATUS_CHARGING
            )
        else:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        self.battery_pub.publish(msg)

    def watchdog_cb(self):
        # while cleaning, if battery drops below threshold: cancel current goal
        if (
            self.state == "CLEANING"
            and not self.docked
            and self.battery_pct <= self.low_threshold
            and not self.low_battery_fired
            and self.goal_handle is not None
        ):
            self.low_battery_fired = True
            self.get_logger().warn(
                f"LOW BATTERY ({self.battery_pct:.1f}%) — cancelling goal, returning to dock"
            )
            self.goal_handle.cancel_goal_async()

    def publish_dock_pose(self):
        msg = self._pose_msg(self.dock[0], self.dock[1], self.dock[2])
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        self.dock_pose_pub.publish(msg)

    def stop(self):
        self.cmd_vel_pub.publish(Twist())

    def robot_pose_map(self):
        """Current robot pose in map frame (None until TF available)."""
        try:
            t = self.tf_buffer.lookup_transform(
                "map", "base_footprint", rclpy.time.Time(), timeout=Duration(seconds=0.2)
            )
            return (t.transform.translation.x, t.transform.translation.y,
                    yaw_from_quat(t.transform.rotation))
        except Exception:
            return None

    def wait_for_map(self, timeout=120.0):
        """Wait until slam_toolbox publishes a non-empty occupancy grid.

        Returns the grid (used to plan the coverage rectangle) or None.
        """
        got = {"grid": None}
        deadline = self.get_clock().now() + Duration(seconds=timeout)
        self._map_wait_start = self.get_clock().now()
        self._map_wait_timeout = timeout

        def cb(grid):
            if grid is not None and got["grid"] is None:
                got["grid"] = grid

        sub = self.create_subscription(OccupancyGrid, "/map", cb, 10)
        last_log = -1
        while got["grid"] is None and self.get_clock().now() < deadline:
            rclpy.spin_once(self, timeout_sec=0.5)
            # Log progress once per 5 s bucket so the user knows we're alive
            # (naive `int(elapsed) % 5 == 0` re-fires every spin within the
            # same second and floods the log with duplicates).
            elapsed = int((self.get_clock().now() - self._map_wait_start).nanoseconds / 1e9)
            bucket = elapsed // 5
            if bucket > last_log:
                last_log = bucket
                self.get_logger().info(f"Waiting for /map... {elapsed}s / {timeout:.0f}s")
        self.destroy_subscription(sub)
        if got["grid"] is None:
            self.get_logger().error("Timed out waiting for /map from slam_toolbox")
            return None
        grid = got["grid"]
        occ = sum(1 for v in grid.data if v > 50)
        free = sum(1 for v in grid.data if 0 <= v <= 50)
        self.get_logger().info(
            f"Map live: {grid.info.width}x{grid.info.height} "
            f"({occ} occupied / {free} free cells)"
        )
        return grid

    # --------------------------------------------------------- nav actions
    def send_goal(self, x, y, yaw, timeout=180.0):
        """Blocking NavigateToPose; returns (status_str, error_code)."""
        goal = NavigateToPose.Goal()
        goal.pose = self._pose_msg(x, y, yaw)
        self.get_logger().info(
            f"[{self.state}] goal ({x:.2f}, {y:.2f}, yaw={math.degrees(yaw):.0f}deg)"
        )
        future = self.nav.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        if not future.done() or future.result() is None:
            return ("NO_SERVER", -1)
        self.goal_handle = future.result()
        if not self.goal_handle.accepted:
            return ("REJECTED", -1)
        result_future = self.goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout)
        if not result_future.done():
            # hard timeout — cancel and report
            self.goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, result_future, timeout_sec=5.0)
            self.goal_handle = None
            return ("TIMEOUT", -1)
        status = result_future.result().status
        err = result_future.result().result.error_code
        # action_msgs/GoalStatus (Jazzy): 4=SUCCEEDED 5=CANCELED 6=ABORTED
        status_str = {
            4: "SUCCEEDED", 5: "CANCELED", 6: "ABORTED",
        }.get(status, f"STATUS_{status}")
        self.goal_handle = None
        return (status_str, err)

    def front_clearance(self):
        """Min laser range in the forward +-12 deg sector (None if no scan)."""
        if self.last_scan is None:
            return None
        s = self.last_scan
        n = len(s.ranges)
        mid = 0  # angle 0 == robot forward (verified: LDS index 0 = +x)
        sector = max(1, int(n * (12.0 / 360.0)))
        vals = [s.ranges[i % n] for i in range(mid - sector, mid + sector + 1)]
        vals = [v for v in vals if math.isfinite(v) and v > s.range_min]
        return min(vals) if vals else None

    def creep_to_dock(self):
        """Slow forward creep until seated.

        Stops when the front laser reads < CREEP_STOP_RANGE, or when the robot
        is commanded to move but stalls (pressed against the dock face) while
        a surface is closer than 0.40 m. Returns True only if the robot ends
        pressed against the dock (front clearance < 0.35 m).
        """
        self.get_logger().info("DOCKING — laser-guided creep")
        start = self.get_clock().now()
        deadline = start + Duration(seconds=CREEP_TIMEOUT)
        stalled_since = None
        seated = False
        while self.get_clock().now() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            fwd = self.front_clearance()
            if fwd is not None and fwd < CREEP_STOP_RANGE:
                self.stop()
                self.get_logger().info(f"DOCKED — front clearance {fwd:.3f} m")
                seated = True
                break
            if fwd is not None and fwd < 0.40 and self.speed < 0.01:
                # commanded to move but not moving, surface ahead: stalled
                if stalled_since is None:
                    stalled_since = self.get_clock().now()
                elif (self.get_clock().now() - stalled_since) > Duration(seconds=2.5):
                    self.stop()
                    self.get_logger().info(f"DOCKED — stalled, front clearance {fwd:.3f} m")
                    seated = True
                    break
            else:
                stalled_since = None
            # Wheel odom lies while pressing (wheels spin, robot held by the
            # dock) — also seat when the front clearance has stopped changing.
            if fwd is not None and fwd < 0.35:
                now = self.get_clock().now()
                self._creep_win.append((now, fwd))
                while self._creep_win and (now - self._creep_win[0][0]) > Duration(seconds=3.0):
                    self._creep_win.pop(0)
                if len(self._creep_win) >= 6:
                    fs = [f for _, f in self._creep_win]
                    if (max(fs) - min(fs)) < 0.05:
                        self.stop()
                        self.get_logger().info(f"DOCKED — pressed (clearance flat {fwd:.3f} m)")
                        seated = True
                        break
            else:
                self._creep_win.clear()
            if fwd is not None and fwd < 0.20:
                # almost there — slow down further
                cmd = Twist()
                cmd.linear.x = min(CREEP_SPEED, max(0.0, fwd - 0.10))
                self.cmd_vel_pub.publish(cmd)
            else:
                cmd = Twist()
                cmd.linear.x = CREEP_SPEED
                self.cmd_vel_pub.publish(cmd)
        self.stop()
        if not seated:
            # timeout: verify we are at least pressed against the dock
            fwd = self.front_clearance()
            seated = fwd is not None and fwd < 0.35
            if seated:
                self.get_logger().info(f"DOCKED — timeout but pressed (front {fwd:.3f} m)")
            else:
                self.get_logger().warn(
                    f"DOCKING — failed to seat (front "
                    f"{fwd if fwd is None else round(fwd, 2)} m)"
                )
        return seated

    def undock(self):
        self.get_logger().info("UNDOCKING — backing out")
        cmd = Twist()
        cmd.linear.x = UNDOCK_SPEED
        t_end = self.get_clock().now() + Duration(seconds=UNDOCK_TIME)
        while self.get_clock().now() < t_end:
            self.cmd_vel_pub.publish(cmd)
            rclpy.spin_once(self, timeout_sec=0.1)
        self.stop()

    # ------------------------------------------------------------ mission
    def run_mission(self):
        self.publish_dock_pose()
        self.get_logger().info("Waiting for Nav2 action server...")
        if not self.nav.wait_for_server(timeout_sec=60.0):
            self.get_logger().error("No /navigate_to_pose server — aborting")
            return 1
        self.get_logger().info("Nav2 up.")
        grid = self.wait_for_map()
        if grid is None:
            return 1
        bounds = self._coverage_bounds(grid)
        self.goals = self._build_goals(self.strip, bounds, grid=grid)
        self.get_logger().info(
            f"Coverage planned from live map: {len(self.goals)} goals over "
            f"x∈[{bounds[0]:.2f},{bounds[1]:.2f}] y∈[{bounds[2]:.2f},{bounds[3]:.2f}]"
        )
        self.get_logger().info("--- MISSION START (unknown-room SLAM cleaning) ---")
        self.state = "CLEANING"
        return self._cleaning_loop()

    def _cleaning_loop(self):
        if self.goals is None:
            self.get_logger().error("No coverage goals — aborting mission")
            return 2
        total = len(self.goals)
        skipped = 0
        while self.goal_idx < total:
            if self.low_battery_fired:
                ok = self._recharge_cycle()
                self.low_battery_fired = False
                # _recharge_cycle no longer aborts mission on failure

            x, y, yaw = self.goals[self.goal_idx]
            # execution-time revalidation: the plan-time snap ran against a
            # sparse map (t~5s) where furniture can still read unknown (-1);
            # re-check against the matured costmap before actually sending
            px, py = x, y
            x, y, drop = self._revalidate_goal(x, y)
            if (x, y) != (px, py):
                self.get_logger().warn(
                    f"  goal {self.goal_idx + 1}/{total} re-snapped "
                    f"({px:.2f},{py:.2f}) -> ({x:.2f},{y:.2f})"
                )
            if drop:
                self.get_logger().error(
                    f"  ✗ goal {self.goal_idx + 1}/{total} unreachable ({drop}) — skipping"
                )
                self.goal_idx += 1
                skipped += 1
                continue
            self.get_logger().info(f"=== CLEANING goal {self.goal_idx + 1}/{total} ===")
            status, err = self.send_goal(x, y, yaw)
            if self.low_battery_fired:
                # goal was cancelled by the watchdog — handled at loop top
                continue
            if status == "SUCCEEDED":
                self.get_logger().info(f"  ✓ goal {self.goal_idx + 1}/{total} done")
                self.goal_idx += 1
            elif status == "ABORTED":
                self.get_logger().error(
                    f"  ✗ goal {self.goal_idx + 1}/{total} aborted (err={err}) — retrying"
                )
                # the aborted goal may itself now be stale — revalidate again
                x2, y2, drop2 = self._revalidate_goal(x, y)
                if drop2:
                    self.get_logger().error(
                        f"  ✗ goal {self.goal_idx + 1}/{total} unreachable on retry ({drop2}) — skipping"
                    )
                    self.goal_idx += 1
                    skipped += 1
                    continue
                status2, _ = self.send_goal(x2, y2, yaw)
                if status2 == "SUCCEEDED":
                    self.get_logger().info(f"  ✓ goal {self.goal_idx + 1}/{total} done (retry)")
                    self.goal_idx += 1
                else:
                    self.get_logger().error(
                        f"  ✗ goal {self.goal_idx + 1}/{total} failed twice — skipping"
                    )
                    self.goal_idx += 1
                    skipped += 1
            elif status in ("TIMEOUT", "NO_SERVER", "REJECTED"):
                self.get_logger().error(f"  ✗ goal {self.goal_idx + 1}/{total} {status} — skipping")
                self.goal_idx += 1
                skipped += 1
            else:  # CANCELED without low battery flag
                self.get_logger().warn(f"  goal {self.goal_idx + 1}/{total} {status}")
                self.goal_idx += 1
                skipped += 1

        if skipped:
            self.get_logger().warn(
                f"--- COVERAGE COMPLETE ({total - skipped}/{total} reached, "
                f"{skipped} skipped) — returning to dock ---"
            )
        else:
            self.get_logger().info(f"--- COVERAGE COMPLETE ({total}/{total}) — returning to dock ---")
        self._recharge_cycle(final_park=True)
        pose = self.robot_pose_map()
        if pose:
            self.get_logger().info(
                f"MISSION COMPLETE — parked at dock, robot at ({pose[0]:.2f}, {pose[1]:.2f})"
            )
        else:
            self.get_logger().info("MISSION COMPLETE — parked at dock")
        return 0

    def _recharge_cycle(self, final_park=False):
        self.state = "RETURNING"
        self.get_logger().info(
            f"Battery {self.battery_pct:.1f}% — returning to dock"
        )
        # approach pose: south of the dock, facing it
        approach = (self.dock[0], self.dock[1] - DOCK_APPROACH_BACK, self.dock[2])
        status, _ = self.send_goal(approach[0], approach[1], approach[2])
        if status != "SUCCEEDED":
            self.get_logger().warn(f"Return-to-dock approach {status} — trying dock pose directly")
            # fallback: navigate straight to dock body center
            status, _ = self.send_goal(self.dock[0], self.dock[1], self.dock[2])
        dock_ok = False
        if status == "SUCCEEDED":
            self.state = "DOCKING"
            seated = self.creep_to_dock()
            if not seated:
                self.get_logger().warn("Docking failed — backing out and re-approaching")
                self.undock()
                self.state = "RETURNING"
                status, _ = self.send_goal(approach[0], approach[1], approach[2])
                self.state = "DOCKING"
                seated = self.creep_to_dock()
            if seated:
                dock_ok = True
            else:
                self.get_logger().error("Docking failed after retry — skipping dock this cycle")
        else:
            self.get_logger().error(f"Cannot reach dock ({status}) — skipping dock this cycle")

        if dock_ok:
            self.docked = True
            self.state = "CHARGING"
            self.get_logger().info(f"CHARGING — {self.battery_pct:.1f}% -> {self.charge_target:.0f}%")
            while self.battery_pct < self.charge_target and rclpy.ok():
                rclpy.spin_once(self, timeout_sec=0.5)
            self.get_logger().info(f"CHARGED to {self.battery_pct:.1f}%")
        else:
            # couldn't dock — just log and continue; mission loop will keep going
            self.get_logger().warn("Proceeding without charge this cycle")

        if final_park:
            self.state = "DONE"
            self.get_logger().info("Staying docked (mission done).")
            # hold at full while parked
            while rclpy.ok():
                rclpy.spin_once(self, timeout_sec=1.0)
            return True
        else:
            self.docked = False
            self.state = "UNDOCKING"
            self.undock()
            self.state = "CLEANING"
            self.get_logger().info("Resuming cleaning.")
            return True


def main():
    rclpy.init()
    node = HouseCleanerAssistant()
    try:
        rc = node.run_mission()
    except KeyboardInterrupt:
        rc = 0
    finally:
        node.destroy_node()
        rclpy.shutdown()
    sys.exit(rc)


if __name__ == "__main__":
    main()
