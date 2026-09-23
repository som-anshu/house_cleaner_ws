#!/usr/bin/env python3
"""Mission supervisor for the autonomous house cleaning robot.

Runs the full cleaning lifecycle:

    INIT -> CLEANING -> (battery low) RETURNING -> DOCKING -> CHARGING
         -> UNDOCKING -> RESUME CLEANING ... -> DONE (parked at dock)

Hardware-agnostic: talks to the stack only through the shared contracts,

  * ``/navigate_to_pose``  (nav2_msgs/NavigateToPose action)
  * ``/battery_state``     (sensor_msgs/BatteryState)
  * ``/map`` + ``/global_costmap/costmap``
  * ``/dock/seated``       (std_msgs/Bool, published by docking controller;
                            TRANSIENT_LOCAL — latched)
  * ``/creep_to_dock`` + ``/undock`` services (house_cleaner_docking)
  * ``/dock/command``      (house_cleaner_msgs/DockCommand, published here)
  * ``/dock/state``        (house_cleaner_msgs/DockState — published by the
                            battery backend; not subscribed here, charge
                            completion is observed via battery percentage)

which are all provided by either the simulator or the real robot.  The same
binary runs on both.

Key differences vs. the original monolith:

  * Dock geometry (approach pose, creep, undock) lives entirely in the
    docking controller; the supervisor only says "dock now" / "undock".
  * Battery charging is driven by publishing ``/dock/command = START`` once
    seated; the backend reports ``/dock/state`` for confirmation.
  * Coverage planning and goal re-validation are in ``house_cleaner_core``
    so they are unit-testable without ROS.
"""

import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, ReliabilityPolicy

from geometry_msgs.msg import Point, Pose, PoseStamped, Quaternion
from std_msgs.msg import Bool, Header
from sensor_msgs.msg import BatteryState, LaserScan
from nav_msgs.msg import Odometry, OccupancyGrid
from nav2_msgs.action import NavigateToPose
from tf2_ros import TransformListener, Buffer
from std_srvs.srv import Trigger
from lifecycle_msgs.srv import GetState

from house_cleaner_msgs.msg import DockCommand
from house_cleaner_msgs.srv import CreepToDock
from house_cleaner_core.geometry import (
    yaw_to_quat,
    coverage_bounds,
    build_boustrophedon,
    revalidate_goal,
    cell_value,
)

# Room interior (world == initial map frame; matches house_room.world walls).
# Used only as a fallback when the SLAM map window is degenerate.
X_MIN, X_MAX = -2.325, 2.325
Y_MIN, Y_MAX = -2.875, 2.875

# Static furniture keep-out from house_room.world (AABB half-extents inflated
# by clearance).  SLAM often leaves furniture interiors unknown (-1); without
# an explicit keep-out, coverage goals land on crates/sofa and MPPI crawls
# until progress_checker/timeout.  Clearance ≈ robot 0.105 + goal tol 0.20
# + small margin — NOT full inflation (0.55 over-filtered 10/14 goals).
FURNITURE_KEEPOUT = (
    # (x_min, x_max, y_min, y_max) expanded by CLEARANCE
    (0.25, 1.85, 0.20, 0.90),    # sofa
    (-1.20, -0.30, -0.75, -0.15),  # coffee table
    (-1.6, -1.6, 1.65, 1.65),    # plant
    (1.425, 1.875, -1.925, -1.475),  # crate_a
    (-1.575, -1.125, -2.225, -1.775),  # crate_b
    # dock body only (south approach corridor must stay free for return)
    (-0.5, 0.5, 2.625, 2.875),
)
# Plant keep-out is a point AABB — expand enough that robot radius (0.105)
# + goal tol (0.20) + margin clear the plant body (r≈0.18), not just 0.32.
KEEPOUT_CLEARANCE = 0.32  # per-side expansion for full-AABB furniture
PLANT_KEEPOUT_CLEARANCE = 0.50  # plant is a point — needs extra radius


def in_furniture_keepout(x, y):
    """True when (x, y) sits in a known furniture/dock keep-out box."""
    for i, (x0, x1, y0, y1) in enumerate(FURNITURE_KEEPOUT):
        c = PLANT_KEEPOUT_CLEARANCE if i == 2 else KEEPOUT_CLEARANCE  # plant index
        if (x0 - c) <= x <= (x1 + c) and (y0 - c) <= y <= (y1 + c):
            return True
    return False


class MissionSupervisor(Node):
    def __init__(self):
        super().__init__("mission_supervisor")

        # ---- mission / battery / dock parameters
        self.declare_parameter("battery.low_threshold", 35.0)
        self.declare_parameter("battery.charge_target", 95.0)
        self.declare_parameter("mission.strip_width", 0.45)
        self.declare_parameter("mission.max_goals", 0)
        self.declare_parameter("mission.loop", False)
        self.declare_parameter("dock.x", 0.0)
        self.declare_parameter("dock.y", 2.75)
        self.declare_parameter("dock.yaw", math.pi / 2.0)
        self.declare_parameter("dock.approach_back", 0.88)

        self.low_threshold = self.get_parameter("battery.low_threshold").value
        self.charge_target = self.get_parameter("battery.charge_target").value
        self.strip = self.get_parameter("mission.strip_width").value
        self.max_goals = int(self.get_parameter("mission.max_goals").value)
        self.loop = bool(self.get_parameter("mission.loop").value)
        self.dock = (
            self.get_parameter("dock.x").value,
            self.get_parameter("dock.y").value,
            self.get_parameter("dock.yaw").value,
        )
        self.approach_back = self.get_parameter("dock.approach_back").value

        # ---- shared state
        self.battery_pct = 100.0
        self.dock_seated = False
        self.last_scan = None
        self.speed = 0.0
        self.goal_handle = None
        self.goals = None
        self.goal_idx = 0
        self.state = "INIT"
        self.low_battery_fired = False
        self.last_grid = None
        self.last_costmap = None

        # ---- pub / sub
        self.dock_cmd_pub = self.create_publisher(DockCommand, "/dock/command", 10)
        self.dock_pose_pub = self.create_publisher(PoseStamped, "/dock_pose", 10)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        self.create_subscription(LaserScan, "/scan", self._scan_cb, 10)
        self.create_subscription(BatteryState, "/battery_state", self._battery_cb, 10)
        # TRANSIENT_LOCAL matches docking_controller's latched /dock/seated.
        self.create_subscription(
            Bool,
            "/dock/seated",
            self._seated_cb,
            QoSProfile(
                depth=1,
                durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE,
            ),
        )
        self.create_subscription(OccupancyGrid, "/map", self._map_cb, 10)
        self.create_subscription(
            OccupancyGrid,
            "/global_costmap/costmap",
            self._costmap_cb,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT),
        )

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ---- action + service clients
        self.nav = ActionClient(self, NavigateToPose, "/navigate_to_pose")
        self.creep_client = self.create_client(CreepToDock, "/creep_to_dock")
        self.undock_client = self.create_client(Trigger, "/undock")

        # ---- watchdog: cancels the current goal on low battery.  Because
        # send_goal() uses spin_until_future_complete (which renders the
        # node), this timer runs while the action is in flight.
        self.create_timer(0.5, self._watchdog_cb)

        self._spin_flag = False

        self.get_logger().info(
            f"Mission supervisor ready: strip={self.strip:.2f} m "
            f"low={self.low_threshold:.0f}% target={self.charge_target:.0f}% "
            f"loop={self.loop} "
            f"dock=({self.dock[0]:.2f}, {self.dock[1]:.2f}, "
            f"yaw={math.degrees(self.dock[2]):.0f}deg)"
        )

    # ------------------------------------------------------------------ I/O
    def _odom_cb(self, msg):
        v = msg.twist.twist.linear
        self.speed = math.hypot(v.x, v.y)

    def _scan_cb(self, msg):
        self.last_scan = msg

    def _battery_cb(self, msg):
        # sensor_msgs/BatteryState.percentage is 0..1 (ROS standard).
        # -1 / NaN / out-of-range means "unknown" — keep last known reading
        # rather than treating it as a real value ( -1 would look like -100% ).
        pct = msg.percentage
        if pct is None or not math.isfinite(pct) or pct < 0.0:
            return
        self.battery_pct = pct * 100.0 if 0.0 <= pct <= 1.0 else pct

    def _seated_cb(self, msg):
        self.dock_seated = bool(msg.data)

    def _map_cb(self, msg):
        self.last_grid = msg

    def _costmap_cb(self, msg):
        self.last_costmap = msg

    def _watchdog_cb(self):
        # While cleaning, if battery drops below threshold: cancel the
        # in-flight goal so the mission loop can return to dock.
        if (
            self.state == "CLEANING"
            and not self.dock_seated
            and self.battery_pct <= self.low_threshold
            and not self.low_battery_fired
            and self.goal_handle is not None
        ):
            self.low_battery_fired = True
            self.get_logger().warn(
                f"LOW BATTERY ({self.battery_pct:.1f}%) — cancelling goal, "
                "returning to dock"
            )
            self.goal_handle.cancel_goal_async()

    # -------------------------------------------------------------- helpers
    def _pose_msg(self, x, y, yaw, frame="map"):
        # Stamp with time 0 (= "use latest TF").  A now() stamp is often a
        # few ms ahead of map→odom under load; controller_server then fails
        # with "extrapolation into the future" → FollowPath TF_ERROR (102)
        # and the goal aborts before the robot moves.
        return PoseStamped(
            header=Header(frame_id=frame),
            pose=Pose(
                position=Point(x=x, y=y, z=0.0),
                orientation=Quaternion(x=0.0, y=0.0, z=yaw_to_quat(yaw)[2], w=yaw_to_quat(yaw)[3]),
            ),
        )

    def _settle_nav(self, seconds=2.0):
        """Spin while BT/controller recover after an abort or cancel.

        Immediately re-sending a goal while the previous FollowPath /
        ComputePath handle is still winding down makes bt_navigator time out
        on action-server ack (seen as dock pose ABORTED in ~65 ms).
        """
        deadline = self.get_clock().now() + Duration(seconds=seconds)
        while rclpy.ok() and self.get_clock().now() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)

    def publish_dock_pose(self):
        msg = self._pose_msg(self.dock[0], self.dock[1], self.dock[2])
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        self.dock_pose_pub.publish(msg)

    def _goal_blocked(self, cm, x, y):
        """Costmap predicate for OccupancyGrid scale (0-100, -1 unknown).

        Blocked when the cell is unknown (not yet observed free), occupied
        (>=50), or inside furniture keep-out.  The old `c >= 100` check only
        matched lethal cells on this scale — the entire inflation band (1-99)
        and unknown furniture interiors passed, so goals landed on/near
        obstacles and the robot crawled until timeout.

        Dock goals are sent directly (no revalidation) so docking is
        unaffected by the keep-out on the dock body.
        """
        if self.state == "CLEANING" and in_furniture_keepout(x, y):
            return True
        c = cell_value(cm, x, y)
        if c is None:
            return True
        if c < 0:
            return True  # unknown — never a cleaning goal
        return c >= 50

    def _occupancy_blocked(self, grid, x, y):
        if in_furniture_keepout(x, y):
            return True
        occ = cell_value(grid, x, y)
        if occ is None or occ < 0:
            return True
        return occ >= 50

    def _resolve_blocked(self):
        """Pick the re-validation grid + predicate that are available."""
        if self.last_costmap is not None:
            return self.last_costmap, self._goal_blocked
        if self.last_grid is not None:
            return self.last_grid, self._occupancy_blocked
        return None, None

    # ------------------------------------------------------------- navigation
    def send_goal(self, x, y, yaw, timeout=None):
        """Blocking NavigateToPose; returns (status_str, error_code).

        ``timeout=None`` uses the default (90 s).  The first CLEANING goal
        passes a longer timeout (cold start: map/TF still maturing under
        host load — goal 1 previously burned the full budget and TIMEOUTd).
        """
        if timeout is None:
            timeout = 120.0 if self.goal_idx == 0 and self.state == "CLEANING" else 90.0
        goal = NavigateToPose.Goal()
        goal.pose = self._pose_msg(x, y, yaw)
        self.get_logger().info(
            f"[{self.state}] goal ({x:.2f}, {y:.2f}, yaw={math.degrees(yaw):.0f}deg)"
        )
        future = self.nav.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        if not future.done() or future.result() is None:
            self._settle_nav(1.0)
            return ("NO_SERVER", -1)
        self.goal_handle = future.result()
        if not self.goal_handle.accepted:
            self.goal_handle = None
            self._settle_nav(1.0)
            return ("REJECTED", -1)
        result_future = self.goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout)
        if not result_future.done():
            self.goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, result_future, timeout_sec=5.0)
            self.goal_handle = None
            # Let BT tear down the canceled tree before the next goal.
            self._settle_nav(2.0)
            return ("TIMEOUT", -1)
        status = result_future.result().status
        err = result_future.result().result.error_code
        # action_msgs/GoalStatus: 4=SUCCEEDED 5=CANCELED 6=ABORTED
        status_str = {
            4: "SUCCEEDED", 5: "CANCELED", 6: "ABORTED",
        }.get(status, f"STATUS_{status}")
        self.goal_handle = None
        if status_str != "SUCCEEDED":
            # Brief settle so planner/controller action servers finish
            # acknowledging halt/cancel before the next send_goal.
            self._settle_nav(1.5)
        return (status_str, err)

    def robot_pose_map(self):
        """Current robot pose in map frame (None until TF available)."""
        try:
            t = self.tf_buffer.lookup_transform(
                "map", "base_footprint", rclpy.time.Time(),
                timeout=Duration(seconds=0.2),
            )
            q = t.transform.rotation
            yaw = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z),
            )
            return (
                t.transform.translation.x,
                t.transform.translation.y,
                yaw,
            )
        except Exception:
            return None

    # ------------------------------------------------------------ wait / map
    def wait_for_map(self, timeout=120.0):
        """Wait until slam_toolbox publishes a non-empty occupancy grid."""
        got = {"grid": None}
        deadline = self.get_clock().now() + Duration(seconds=timeout)

        def cb(grid):
            if got["grid"] is None:
                got["grid"] = grid

        sub = self.create_subscription(OccupancyGrid, "/map", cb, 10)
        start = self.get_clock().now()
        last_bucket = -1
        while got["grid"] is None and self.get_clock().now() < deadline:
            rclpy.spin_once(self, timeout_sec=0.5)
            elapsed = int(
                (self.get_clock().now() - start).nanoseconds / 1e9
            )
            bucket = elapsed // 5
            if bucket > last_bucket:
                last_bucket = bucket
                self.get_logger().info(
                    f"Waiting for /map... {elapsed}s / {timeout:.0f}s"
                )
        self.destroy_subscription(sub)
        if got["grid"] is None:
            self.get_logger().error(
                "Timed out waiting for /map from slam_toolbox"
            )
            return None
        grid = got["grid"]
        occ = sum(1 for v in grid.data if v > 50)
        free = sum(1 for v in grid.data if 0 <= v <= 50)
        self.get_logger().info(
            f"Map live: {grid.info.width}x{grid.info.height} "
            f"({occ} occupied / {free} free cells)"
        )
        return grid

    # -------------------------------------------------------------- services
    def call_creep(self):
        """Call the docking controller's creep_to_dock service; returns seated."""
        if not self.creep_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error("Docking controller (creep) unavailable")
            return False, -1.0
        req = CreepToDock.Request()
        future = self.creep_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=120.0)
        if not future.done() or future.result() is None:
            return False, -1.0
        resp = future.result()
        return resp.seated, resp.front_clearance_m

    def call_undock(self):
        """Call the docking controller's undock service; returns success."""
        if not self.undock_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error("Docking controller (undock) unavailable")
            return False
        future = self.undock_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=60.0)
        if not future.done() or future.result() is None:
            return False
        return future.result().success

    # -------------------------------------------------------------- mission
    def _wait_nav2_active(self, timeout=120.0):
        """Wait until bt_navigator reaches lifecycle ACTIVE (id=3).

        The NavigateToPose action server is advertised as soon as the node
        spawns, so wait_for_server() can succeed while the node is still
        unconfigured/inactive — its executor then rejects every goal.  Under
        cold-boot load the retry bringup can lag the /map by tens of seconds,
        so gate the first goal on the observable ACTIVE state instead.
        """
        client = self.create_client(GetState, "/bt_navigator/get_state")
        deadline = self.get_clock().now() + Duration(seconds=timeout)
        while self.get_clock().now() < deadline:
            if not client.wait_for_service(timeout_sec=1.0):
                rclpy.spin_once(self, timeout_sec=0.5)
                continue
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
            if future.done() and future.result() is not None:
                state = future.result().current_state.id
                if state == 3:
                    client.destroy()
                    self.get_logger().info("Nav2 lifecycle ACTIVE.")
                    return True
            rclpy.spin_once(self, timeout_sec=0.5)
        client.destroy()
        return False

    def run_mission(self):
        self.publish_dock_pose()
        self.get_logger().info("Waiting for Nav2 action server...")
        if not self.nav.wait_for_server(timeout_sec=180.0):
            self.get_logger().error("No /navigate_to_pose server — aborting")
            return 1
        self.get_logger().info("Nav2 up.")
        if not self._wait_nav2_active(timeout=120.0):
            self.get_logger().error("Nav2 never reached ACTIVE — aborting")
            return 1
        grid = self.wait_for_map()
        if grid is None:
            return 1

        # Keep coverage goals outside the costmap inflation band (0.35 m) plus
        # robot radius + turn margin, so the robot never parks itself boxed into
        # a wall/furniture corner it can't extract from (seen at margin 0.37).
        bounds = coverage_bounds(grid, margin=0.55)
        if bounds is None:
            self.get_logger().warn(
                "Map window degenerate — using this room's fallback bounds"
            )
            bounds = (X_MIN, X_MAX, Y_MIN, Y_MAX)
        self.goals = build_boustrophedon(bounds, self.strip, grid=grid)
        # Drop anything that landed in furniture/dock keep-out even if the
        # live map still reads those cells as unknown/free.
        filtered = [g for g in self.goals if not in_furniture_keepout(g[0], g[1])]
        if len(filtered) != len(self.goals):
            self.get_logger().warn(
                f"Filtered {len(self.goals) - len(filtered)} goal(s) in furniture keep-out"
            )
            self.goals = filtered
        if self.max_goals > 0:
            self.goals = self.goals[: self.max_goals]
        self.get_logger().info(
            f"Coverage planned from live map: {len(self.goals)} goals over "
            f"x∈[{bounds[0]:.2f},{bounds[1]:.2f}] y∈[{bounds[2]:.2f},{bounds[3]:.2f}]"
        )
        self.get_logger().info("--- MISSION START (SLAM coverage cleaning) ---")
        self.state = "CLEANING"
        while True:
            self.state = "CLEANING"
            rc = self._cleaning_loop()
            if not self.loop:
                return rc
            self.get_logger().info(
                "=== MISSION LOOP — undocking, next coverage pass ==="
            )
            # Reset coverage for a fresh pass; map/goals stay valid.
            self.goal_idx = 0
            self.low_battery_fired = False
            if self.dock_seated:
                # _recharge_cycle(final_park) left us seated for loop mode.
                undocked = self.call_undock()
                if not undocked:
                    self.get_logger().error(
                        "Loop undock failed — retrying before next pass"
                    )
                    self.call_undock()
            # Small settle so odom/TF catch up after undock.
            rclpy.spin_once(self, timeout_sec=1.0)

    def _cleaning_loop(self):
        if self.goals is None:
            self.get_logger().error("No coverage goals — aborting mission")
            return 2
        total = len(self.goals)
        skipped = 0
        while self.goal_idx < total:
            # Enter recharge when the watchdog fired OR when battery is
            # already low at the top of an iteration (covers the case where
            # a failed dock cleared the latch but percent never recovered).
            need_charge = self.low_battery_fired or (
                self.battery_pct <= self.low_threshold
                and not self.dock_seated
                and self.state == "CLEANING"
            )
            if need_charge:
                self._recharge_cycle()
                self.low_battery_fired = False
                # Livelock guard: if we could not seat/charge, stop cleaning
                # instead of immediately re-sending goals that the watchdog
                # will cancel forever.
                if self.battery_pct <= self.low_threshold and not self.dock_seated:
                    self.get_logger().error(
                        "Battery still low and not seated after recharge — "
                        "aborting remaining goals to avoid livelock"
                    )
                    break

            x, y, yaw = self.goals[self.goal_idx]
            src, blocked = self._resolve_blocked()
            if src is not None:
                px, py = x, y
                x, y, drop = revalidate_goal(src, x, y, blocked=blocked)
                if (x, y) != (px, py):
                    self.get_logger().warn(
                        f"  goal {self.goal_idx + 1}/{total} re-snapped "
                        f"({px:.2f},{py:.2f}) -> ({x:.2f},{y:.2f})"
                    )
                if drop:
                    self.get_logger().error(
                        f"  goal {self.goal_idx + 1}/{total} unreachable "
                        f"({drop}) — skipping"
                    )
                    self.goal_idx += 1
                    skipped += 1
                    continue

            self.get_logger().info(
                f"=== CLEANING goal {self.goal_idx + 1}/{total} ==="
            )
            status, err = self.send_goal(x, y, yaw)
            if self.low_battery_fired:
                continue
            # TF_ERROR (102): settle then one extra retry before the normal
            # ABORTED path (map→odom lag under host load — transient).
            if status == "ABORTED" and err == 102:
                self.get_logger().warn(
                    f"  goal {self.goal_idx + 1}/{total} TF_ERROR — "
                    "settling, retrying"
                )
                self._settle_nav(3.0)
                status, err = self.send_goal(x, y, yaw)
                if self.low_battery_fired:
                    continue
                if status == "SUCCEEDED":
                    self.get_logger().info(
                        f"  goal {self.goal_idx + 1}/{total} done (TF retry)"
                    )
                    self.goal_idx += 1
                    continue
            if status == "SUCCEEDED":
                self.get_logger().info(
                    f"  goal {self.goal_idx + 1}/{total} done"
                )
                self.goal_idx += 1
            elif status == "ABORTED":
                self.get_logger().error(
                    f"  goal {self.goal_idx + 1}/{total} aborted "
                    f"(err={err}) — retrying"
                )
                if src is not None:
                    x2, y2, drop2 = revalidate_goal(src, x, y, blocked=blocked)
                    if drop2:
                        self.get_logger().error(
                            f"  goal {self.goal_idx + 1}/{total} unreachable "
                            f"on retry ({drop2}) — skipping"
                        )
                        self.goal_idx += 1
                        skipped += 1
                        continue
                    status2, _ = self.send_goal(x2, y2, yaw)
                else:
                    status2, _ = self.send_goal(x, y, yaw)
                # Low-battery cancel during the retry must not count as a
                # permanent skip — recharge first, then retry this goal.
                if self.low_battery_fired:
                    continue
                if status2 == "SUCCEEDED":
                    self.get_logger().info(
                        f"  goal {self.goal_idx + 1}/{total} done (retry)"
                    )
                    self.goal_idx += 1
                else:
                    self.get_logger().error(
                        f"  goal {self.goal_idx + 1}/{total} failed twice — skipping"
                    )
                    self.goal_idx += 1
                    skipped += 1
            elif status == "TIMEOUT":
                # Transient stall (control-loop collapse / cold map) — one
                # retry after revalidation before skipping (was: skip immediately).
                self.get_logger().error(
                    f"  goal {self.goal_idx + 1}/{total} TIMEOUT — retrying once"
                )
                if src is not None:
                    x2, y2, drop2 = revalidate_goal(src, x, y, blocked=blocked)
                    if drop2:
                        self.get_logger().error(
                            f"  goal {self.goal_idx + 1}/{total} unreachable "
                            f"on TIMEOUT retry ({drop2}) — skipping"
                        )
                        self.goal_idx += 1
                        skipped += 1
                        continue
                    status2, _ = self.send_goal(x2, y2, yaw)
                else:
                    status2, _ = self.send_goal(x, y, yaw)
                if self.low_battery_fired:
                    continue
                if status2 == "SUCCEEDED":
                    self.get_logger().info(
                        f"  goal {self.goal_idx + 1}/{total} done (timeout retry)"
                    )
                    self.goal_idx += 1
                else:
                    self.get_logger().error(
                        f"  goal {self.goal_idx + 1}/{total} TIMEOUT twice "
                        f"(last={status2}) — skipping"
                    )
                    self.goal_idx += 1
                    skipped += 1
            elif status in ("NO_SERVER", "REJECTED"):
                self.get_logger().error(
                    f"  goal {self.goal_idx + 1}/{total} {status} — skipping"
                )
                self.goal_idx += 1
                skipped += 1
            else:  # CANCELED without low-battery flag
                self.get_logger().warn(
                    f"  goal {self.goal_idx + 1}/{total} {status}"
                )
                self.goal_idx += 1
                skipped += 1

        self.get_logger().info(
            f"--- COVERAGE COMPLETE ({total - skipped}/{total} reached) "
            f"— returning to dock ---"
        )
        # Only claim "parked" if the final dock actually succeeded.
        docked = self._recharge_cycle(final_park=True)
        if docked:
            if self.loop:
                self.get_logger().info(
                    "MISSION PASS COMPLETE — looping (will undock next)"
                )
                return 0
            self.get_logger().info("MISSION COMPLETE — parked at dock")
            return 0
        self.get_logger().warn(
            "MISSION COMPLETE — could not seat at dock (battery/map issue?)"
        )
        return 0

    def _recharge_cycle(self, final_park=False):
        """Return-to-dock → creep → charge → undock (or stay for final_park).

        Returns True only when the robot is physically seated at the dock
        at the end of the cycle.  Mid-cycle failures must not livelock the
        cleaning loop: if charge/undock fails we still clear the low-battery
        latch and resume, but we log loudly.
        """
        self.state = "RETURNING"
        self.get_logger().info(
            f"Battery {self.battery_pct:.1f}% — returning to dock"
        )
        approach = (
            self.dock[0],
            self.dock[1] - self.approach_back,
            self.dock[2],
        )
        # Settle so BT finishes the last coverage goal before dock planning.
        self._settle_nav(2.0)
        status, err = self.send_goal(approach[0], approach[1], approach[2])
        for attempt in range(2):
            if status == "SUCCEEDED":
                break
            self.get_logger().warn(
                f"Return-to-dock approach {status} (err={err}) — "
                f"retry {attempt + 1}/2 after settle"
            )
            self._settle_nav(3.0)
            status, err = self.send_goal(approach[0], approach[1], approach[2])

        if status != "SUCCEEDED":
            self.get_logger().warn(
                f"Approach still {status} — trying dock pose directly"
            )
            self._settle_nav(2.0)
            status, err = self.send_goal(self.dock[0], self.dock[1], self.dock[2])
            if status != "SUCCEEDED":
                self._settle_nav(3.0)
                status, _ = self.send_goal(
                    self.dock[0], self.dock[1], self.dock[2]
                )

        dock_ok = False
        if status == "SUCCEEDED":
            self.state = "DOCKING"
            seated, _ = self.call_creep()
            dock_ok = seated
            if not seated:
                self.get_logger().warn(
                    "Docking failed after retries — skipping dock this cycle"
                )
        else:
            self.get_logger().error(
                f"Cannot reach dock ({status}) — skipping dock this cycle"
            )

        if dock_ok:
            self.dock_cmd_pub.publish(DockCommand(command=DockCommand.CMD_START))
            self.state = "CHARGING"
            self.get_logger().info(
                f"CHARGING — {self.battery_pct:.1f}% -> {self.charge_target:.0f}%"
            )
            # Bounded wait: never hang forever if charge never starts or the
            # robot leaves the dock (battery_sim stops charging on undock).
            charge_timeout = 300.0  # wall/sim seconds via node clock
            deadline = self.get_clock().now() + Duration(seconds=charge_timeout)
            while (
                self.battery_pct < self.charge_target
                and rclpy.ok()
                and self.get_clock().now() < deadline
            ):
                rclpy.spin_once(self, timeout_sec=0.5)
                if not self.dock_seated:
                    self.get_logger().warn(
                        "Left the dock mid-charge — aborting charge wait"
                    )
                    break
            if self.battery_pct >= self.charge_target:
                self.get_logger().info(f"CHARGED to {self.battery_pct:.1f}%")
            else:
                self.get_logger().warn(
                    f"Charge incomplete ({self.battery_pct:.1f}%) "
                    f"— timeout or dock lost"
                )
        else:
            self.get_logger().warn("Proceeding without charge this cycle")

        if final_park:
            self.dock_cmd_pub.publish(DockCommand(command=DockCommand.CMD_STOP))
            if dock_ok:
                if self.loop:
                    # Stay seated; run_mission's loop will undock for next pass.
                    self.state = "DONE"
                    self.get_logger().info(
                        "Parked at dock (mission loop will undock)."
                    )
                    return True
                self.state = "DONE"
                self.get_logger().info("Staying docked (mission done).")
                while rclpy.ok():
                    rclpy.spin_once(self, timeout_sec=1.0)
                return True
            # Failed final dock: do NOT claim parked-at-dock and do NOT
            # spin forever — return so the caller can report the miss.
            self.state = "DONE"
            self.get_logger().error(
                "Final dock failed — NOT parked at dock"
            )
            return False

        self.dock_cmd_pub.publish(DockCommand(command=DockCommand.CMD_STOP))
        self.state = "UNDOCKING"
        undocked = self.call_undock()
        if not undocked:
            self.get_logger().error(
                "Undock service failed — may still be seated; "
                "continuing anyway (next nav goal will reveal state)"
            )
        self.state = "CLEANING"
        self.get_logger().info("Resuming cleaning.")
        return True


def main():
    rclpy.init()
    node = MissionSupervisor()
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