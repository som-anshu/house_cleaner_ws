#!/usr/bin/env python3
"""
Verify which LDS scan index points at the robot's forward direction.

Empirical probe (the LDS forward index is NEVER guaranteed by docs — the
buggy helper that inspired this used n//2, i.e. the BACK, and the robot
docked by watching its own rear). Run against any running stack that
publishes /scan + /map and has map->base_footprint TF:

  source /home/koko/house_cleaner_ws/env.sh
  python3 scripts/verify_scan_forward_index.py

For each candidate index (0, n//4, n//2, 3n//4) it raycasts the expected
wall distance along that beam's heading in the occupancy grid, then
compares against the live scan reading. The index whose reading matches
its raycast best is the forward index.

Exit 0 = verdict forward==index 0 (as expected for the Burger LDS);
exit 2  = forward index is NOT 0 (a real sensor-mounting difference).
"""
import math
import sys
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid
from tf2_ros import Buffer, TransformListener

OCC_THRESHOLD = 50        # cell occupancy % treated as a wall
MATCH_TOL = 0.35          # meters of agreement needed to call it a match
RANGE_MAX = 8.0           # raycast cap, meters


class ForwardIndexProbe(Node):
    def __init__(self):
        super().__init__("verify_scan_forward_index")
        self.map_msg = None
        self.latest_scan = None

        map_qos = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE)
        scan_qos = QoSProfile(
            depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)

        self.create_subscription(OccupancyGrid, "/map", self._on_map, map_qos)
        self.create_subscription(LaserScan, "/scan", self._on_scan, scan_qos)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def _on_map(self, msg):
        if self.map_msg is None:
            self.get_logger().info(
                f"/map: {msg.info.width}x{msg.info.height} @ "
                f"{msg.info.resolution:.3f} m/px, origin "
                f"({msg.info.origin.position.x:.3f}, "
                f"{msg.info.origin.position.y:.3f})")
        self.map_msg = msg

    def _on_scan(self, msg):
        self.latest_scan = msg

    def _cell(self, x, y):
        """Map-frame point -> (occupied?, distance-to-wall along +x ray)."""
        m = self.map_msg
        res = m.info.resolution
        ox = m.info.origin.position.x
        oy = m.info.origin.position.y
        cx = int((x - ox) / res)
        cy = int((y - oy) / res)
        if not (0 <= cx < m.info.width and 0 <= cy < m.info.height):
            return None
        idx = cy * m.info.width + cx
        return m.data[idx]

    def raycast(self, x0, y0, heading, cap=RANGE_MAX):
        """Distance (m) to first occupied cell from (x0,y0) along heading."""
        m = self.map_msg
        res = m.info.resolution
        step = res * 0.5
        d = 0.0
        while d < cap:
            x = x0 + math.cos(heading) * d
            y = y0 + math.sin(heading) * d
            occ = self._cell(x, y)
            if occ is None:
                return cap
            if occ >= OCC_THRESHOLD:
                return d
            d += step
        return cap

    def run(self):
        # wait for map + scan (DDS discovery for a new participant is
        # flaky on busy boxes — some runs connect in <2 s, others take
        # 30 s+; never conclude "no stack" from a short window)
        wait_until = time.monotonic() + 60.0
        last_log = 0.0
        while time.monotonic() < wait_until:
            rclpy.spin_once(self, timeout_sec=0.2)
            if self.map_msg is not None and self.latest_scan is not None:
                break
            if time.monotonic() - last_log > 10.0:
                last_log = time.monotonic()
                self.get_logger().info(
                    f"waiting for /map + /scan "
                    f"({int(wait_until - time.monotonic())} s left)...")
        if self.map_msg is None or self.latest_scan is None:
            self.get_logger().error("No /map and/or /scan within 60 s — "
                                    "is a nav stack running?")
            return 1

        tf = None
        # IMPORTANT: never lookup_transform(timeout=...) from a spin_once
        # loop — the blocking wait starves the node's callbacks, so the
        # buffer never receives the transforms it's waiting for and the
        # timeout always fires. Spin-poll with instant lookups instead
        # (a fresh python buffer needs ~5-10 s to receive latched
        # /tf_static).
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.2)
            try:
                tf = self.tf_buffer.lookup_transform(
                    "map", self.latest_scan.header.frame_id,
                    rclpy.time.Time())
                break
            except Exception:
                pass
        if tf is None:
            self.get_logger().error(
                f"TF map -> {self.latest_scan.header.frame_id} never "
                f"resolved after 30 s")
            return 1

        rx = tf.transform.translation.x
        ry = tf.transform.translation.y
        yaw = 2.0 * math.atan2(tf.transform.rotation.z,
                               tf.transform.rotation.w)

        n = len(self.latest_scan.ranges)
        candidates = {0: 0.0, n // 4: math.pi / 2,
                      n // 2: math.pi, 3 * n // 4: -math.pi / 2}
        print(f"\nscan: {n} rays, robot at map ({rx:.2f}, {ry:.2f}) "
              f"yaw {math.degrees(yaw):.0f} deg")
        print(f"{'index':>6} {'heading':>8} {'raycast(m)':>11} "
              f"{'scan(m)':>8} {'match':>6}")
        best = None
        best_err = 1e9
        for idx, rel in sorted(candidates.items(),
                               key=lambda kv: kv[1]):
            heading = yaw + rel
            expected = self.raycast(rx, ry, heading)
            r = self.latest_scan.ranges[idx]
            reading = r if math.isfinite(r) else float("nan")
            err = abs(expected - reading) if math.isfinite(reading) else 1e9
            match = err <= MATCH_TOL
            print(f"{idx:>6} {math.degrees(heading):>7.0f} "
                  f"{expected:>11.2f} {reading:>8.2f} "
                  f"{'YES' if match else 'no':>6}")
            if err < best_err:
                best_err = err
                best = idx

        print(f"\nforward index == {best} (expected 0)")
        if best == 0:
            print("VERDICT: index 0 = forward  ✓")
            return 0
        print("VERDICT: forward index is NOT 0 — sensor mounting differs!")
        return 2


def main():
    rclpy.init()
    probe = ForwardIndexProbe()
    try:
        sys.exit(probe.run())
    finally:
        probe.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
