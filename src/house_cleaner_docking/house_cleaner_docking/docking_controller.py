#!/usr/bin/env python3
"""Laser-guided docking controller for the house cleaner robot.

Owns everything that happens at the dock:

  * ``creep_to_dock``  (service, house_cleaner_msgs/CreepToDock): drives the
    robot forward at ``creep.speed`` until the front laser sector reads below
    ``creep.stop_range`` (seated), or a stall / flat-clearance condition
    fires within ``creep.timeout``, or ``creep.max_attempts`` retries.
  * ``undock``         (service, std_srvs/Trigger): backs out ``undock.meters``
    then republishes ``/dock/seated = false``.

The controller is handed full ownership of velocity during a creep/undock:
it publishes on the topic given by ``velocity_topic``.  The stack launch wires
this to ``/cmd_vel_nav`` so the creep flows through Nav2's velocity_smoother
and collision_monitor exactly like any other command; the collision monitor's
front polygon acts as the last-resort bumper and the stall/flat-window latches
below decide "seated".  It reports state to the rest of the stack via the
``/dock/seated`` bool, and the battery backend consumes that to flip its own
dock/charge state machine.

Front-sector detection is azimuth-aware: the forward sector is computed from
``angle_min`` and ``angle_increment``, not by assuming index 0 is forward.
"""

import math
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import (
    QoSProfile,
    QoSDurabilityPolicy,
    ReliabilityPolicy,
)

from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from house_cleaner_msgs.srv import CreepToDock


class DockingController(Node):
    def __init__(self):
        super().__init__("docking_controller")

        self.declare_parameter("creep.speed", 0.04)
        self.declare_parameter("creep.stop_range", 0.13)
        self.declare_parameter("creep.timeout", 30.0)
        self.declare_parameter("creep.sector_deg", 12.0)
        self.declare_parameter("creep.max_attempts", 2)
        self.declare_parameter("undock.speed", -0.06)
        self.declare_parameter("undock.meters", 0.48)
        self.declare_parameter("velocity_topic", "/cmd_vel")

        self.creep_speed = self.get_parameter("creep.speed").value
        self.stop_range = self.get_parameter("creep.stop_range").value
        self.creep_timeout = self.get_parameter("creep.timeout").value
        self.sector_deg = self.get_parameter("creep.sector_deg").value
        self.max_attempts = int(self.get_parameter("creep.max_attempts").value)
        self.undock_speed = self.get_parameter("undock.speed").value
        self.undock_meters = self.get_parameter("undock.meters").value
        velocity_topic = self.get_parameter("velocity_topic").value

        self.cmd_vel_pub = self.create_publisher(Twist, velocity_topic, 10)
        # Must exist before the first seated publish below.
        self.last_scan = None
        self._creep_win = []
        self.seated = False
        # transient_local so a late/restarted subscriber still learns the
        # current seated state (volatile edge-only publish was lossy).
        self.seated_pub = self.create_publisher(
            Bool,
            "/dock/seated",
            QoSProfile(
                depth=1,
                durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE,
            ),
        )
        # Publish current seated state once at startup for late joiners.
        self.seated_pub.publish(Bool(data=self.seated))
        self.scan_sub = self.create_subscription(
            LaserScan, "/scan", self._scan_cb, 10
        )
        from nav_msgs.msg import Odometry
        self._odom_speed = 0.0
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)

        self.cb_group = MutuallyExclusiveCallbackGroup()
        self.creep_srv = self.create_service(
            CreepToDock, "/creep_to_dock", self._creep_srv_cb,
            callback_group=self.cb_group,
        )
        self.undock_srv = self.create_service(
            Trigger, "/undock", self._undock_srv_cb,
            callback_group=self.cb_group,
        )

        self._lock = threading.Lock()

        self.get_logger().info(
            f"Docking controller ready: creep={self.creep_speed:.2f} m/s "
            f"stop<{self.stop_range:.2f} m sector={self.sector_deg:.0f}deg "
            f"timeout={self.creep_timeout:.0f}s attempt(s)={self.max_attempts}"
        )

    # ------------------------------------------------------------------ I/O
    def _scan_cb(self, msg):
        with self._lock:
            self.last_scan = msg

    def _odom_cb(self, msg):
        v = msg.twist.twist.linear
        with self._lock:
            self._odom_speed = math.hypot(v.x, v.y)

    def _set_seated(self, seated):
        if self.seated != seated:
            self.seated = seated
            self.seated_pub.publish(Bool(data=seated))
            self.get_logger().info(
                f"DOCK /dock/seated = {seated}"
            )

    def front_clearance(self):
        """Min laser range within ±sector_deg of the robot's forward axis.

        The forward direction is angle 0; because the LDS on the Burger
        publishes ``angle_min=−π``, the index of the forward ray is
        ``(−angle_min)/increment``.  Returns None when no scan is available.
        """
        with self._lock:
            s = self.last_scan
        if s is None or len(s.ranges) == 0:
            return None
        n = len(s.ranges)
        inc = s.angle_increment
        # index of the ray closest to angle 0
        mid = int(round(-s.angle_min / inc))
        sector = max(1, int(round(math.radians(self.sector_deg) / inc)))
        vals = []
        for i in range(mid - sector, mid + sector + 1):
            r = s.ranges[i % n]
            if math.isfinite(r) and r > s.range_min:
                vals.append(r)
        return min(vals) if vals else None

    def stop(self):
        self.cmd_vel_pub.publish(Twist())

    def _sleep_blocking(self, seconds):
        # Plain wall-clock sleep.  Callbacks keep flowing on the executor's
        # other threads (MultiThreadedExecutor, see main()), so this must NOT
        # call rclpy.spin_once here: nested spinning inside a service callback
        # raises "Executor is already spinning" and kills the node.
        end = self.get_clock().now() + Duration(seconds=seconds)
        while self.get_clock().now() < end and rclpy.ok():
            time.sleep(0.05)

    def sleep_for_clock(self, seconds):
        """Blocking sleep that advances with sim time (rclpy interop)."""
        self._sleep_blocking(seconds)

    # ------------------------------------------------------------ creep/undock
    def creep_to_dock_once(self):
        """Single creep pass; returns (seated, front_clearance)."""
        self.get_logger().info("DOCKING — laser-guided creep")
        start = self.get_clock().now()
        deadline = start + Duration(seconds=self.creep_timeout)
        stalled_since = None
        seated = False
        self._creep_win.clear()

        while self.get_clock().now() < deadline and rclpy.ok():
            # Pace the loop only; sensor callbacks run on executor threads.
            # (Nested rclpy.spin_once here crashes the node: the service
            # callback already executes inside the executor.)
            time.sleep(0.05)
            fwd = self.front_clearance()
            if fwd is None:
                # No laser: NEVER creep blind — stop and wait for a scan.
                self.stop()
                continue
            if fwd < self.stop_range:
                seated = True
                break
            # Stall: commanded but not moving while a surface is close.
            # Only trust this as "seated" when we are already inside the
            # dock envelope (stop_range + slack).  A 0.40 m stall away from
            # the dock (wedged on furniture) used to false-seat and start
            # charging in free space.
            if fwd < (self.stop_range + 0.22) and self._robot_speed() < 0.01:
                if stalled_since is None:
                    stalled_since = self.get_clock().now()
                elif (
                    self.get_clock().now() - stalled_since
                ) > Duration(seconds=2.5):
                    seated = True
                    break
            else:
                stalled_since = None
            # flat-clearance window: wheel odom lies while pressing.
            if fwd < 0.35:
                now = self.get_clock().now()
                self._creep_win.append((now, fwd))
                while (
                    self._creep_win
                    and (now - self._creep_win[0][0]) > Duration(seconds=3.0)
                ):
                    self._creep_win.pop(0)
                if len(self._creep_win) >= 6:
                    fs = [f for _, f in self._creep_win]
                    if (max(fs) - min(fs)) < 0.05 and min(fs) < (self.stop_range + 0.22):
                        seated = True
                        break
            else:
                self._creep_win.clear()

            cmd = Twist()
            if fwd < 0.20:
                cmd.linear.x = min(self.creep_speed, max(0.0, fwd - 0.10))
            else:
                cmd.linear.x = self.creep_speed
            self.cmd_vel_pub.publish(cmd)

        self.stop()
        if not seated:
            fwd = self.front_clearance()
            seated = fwd is not None and fwd < 0.35
            if seated:
                self.get_logger().info(
                    f"DOCKED — timeout but pressed (front {fwd:.3f} m)"
                )
            else:
                self.get_logger().warn(
                    f"DOCKING — failed to seat this pass "
                    f"(front {fwd if fwd is None else round(fwd, 2)} m)"
                )
        else:
            self.get_logger().info("DOCKED — seated")
        return seated, self.front_clearance()

    def _robot_speed(self):
        with self._lock:
            return self._odom_speed

    # ------------------------------------------------------------- services
    def _creep_srv_cb(self, request, response):
        attempts = 0
        seated = False
        fwd = None
        while attempts < self.max_attempts and not seated:
            seated, fwd = self.creep_to_dock_once()
            attempts += 1
            if not seated and attempts < self.max_attempts:
                self.get_logger().info("Re-approaching dock (retry)")
                # back out, then re-creep
                self._undock_impl()
        response.seated = seated
        response.front_clearance_m = fwd if fwd is not None else -1.0
        self._set_seated(seated)
        return response

    def _undock_srv_cb(self, request, response):
        ok = self._undock_impl()
        if ok:
            self._set_seated(False)
            response.success = True
            response.message = "undocked"
        else:
            # Do NOT force seated=False if we never actually moved — the
            # battery backend would start "charging" while still pressed.
            response.success = False
            response.message = "undock did not move (still seated?)"
        return response

    def _undock_impl(self):
        """Back out ``undock.meters``.  Returns True if odom shows motion."""
        self.get_logger().info("UNDOCKING — backing out")
        # Integrated |v|*dt is a simple progress proxy (no TF required).
        integrated = 0.0
        cmd = Twist()
        cmd.linear.x = self.undock_speed
        t_end = self.get_clock().now() + Duration(
            seconds=self.undock_meters / abs(self.undock_speed) + 1.0
        )
        while self.get_clock().now() < t_end and rclpy.ok():
            self.cmd_vel_pub.publish(cmd)
            time.sleep(0.05)
            integrated += abs(self._robot_speed()) * 0.05
        self.stop()
        # Require meaningful reverse progress (~half the commanded distance)
        # so a blocked undock reports failure instead of silent success.
        moved = integrated >= (self.undock_meters * 0.5)
        if not moved:
            self.get_logger().warn(
                f"UNDOCK blocked (integrated {integrated:.2f} m "
                f"< {self.undock_meters * 0.5:.2f} m)"
            )
        return moved


def main():
    rclpy.init()
    node = DockingController()
    # Multi-threaded: the blocking creep/undock service callbacks must not
    # starve the scan/odom subscriptions they read (and must never nest
    # rclpy.spin_once, which fatally raises "Executor is already spinning").
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()