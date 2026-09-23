#!/usr/bin/env python3
"""Sample odom + full cmd_vel chain to localize a velocity stall."""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class D(Node):
    def __init__(self):
        super().__init__("diag_stuck")
        self.odom = None
        self.cmd_out = None
        self.cmd_nav = None
        self.cmd_smooth = None
        self.path = None
        self.scan = None
        self.t_out = None
        self.t_nav = None
        self.t_smooth = None
        self.create_subscription(Odometry, "/odom", self._o, 10)
        self.create_subscription(Twist, "/cmd_vel", self._c_out, 10)
        self.create_subscription(Twist, "/cmd_vel_nav", self._c_nav, 10)
        self.create_subscription(Twist, "/cmd_vel_smoothed", self._c_smooth, 10)
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(Path, "/plan", self._p, qos)
        self.create_subscription(LaserScan, "/scan", self._s, 10)

    def _o(self, m):
        self.odom = m

    def _c_out(self, m):
        self.cmd_out = m
        self.t_out = time.time()

    def _c_nav(self, m):
        self.cmd_nav = m
        self.t_nav = time.time()

    def _c_smooth(self, m):
        self.cmd_smooth = m
        self.t_smooth = time.time()

    def _p(self, m):
        self.path = m

    def _s(self, m):
        self.scan = m

    def poll(self, n=5, dt=0.4):
        xs = []
        now = time.time()
        for _ in range(n):
            rclpy.spin_once(self, timeout_sec=dt)
            if self.odom:
                xs.append(self.odom.pose.pose.position.x)
        pos = None
        spd = None
        if self.odom:
            p = self.odom.pose.pose.position
            pos = (p.x, p.y)
            spd = self.odom.twist.twist.linear.x

        def age(t):
            return None if t is None else now - t

        def cmdv(m):
            if m is None:
                return None
            return (m.linear.x, m.angular.z)

        path_n = len(self.path.poses) if self.path else 0
        rng = None
        if self.scan:
            rs = [r for r in self.scan.ranges if math.isfinite(r) and r > 0]
            if rs:
                rng = (min(rs), max(rs))
        disp = (max(xs) - min(xs)) if len(xs) > 1 else 0.0
        return dict(
            pos=pos,
            spd=spd,
            nav=cmdv(self.cmd_nav),
            smooth=cmdv(self.cmd_smooth),
            out=cmdv(self.cmd_out),
            age_nav=age(self.t_nav),
            age_smooth=age(self.t_smooth),
            age_out=age(self.t_out),
            path_n=path_n,
            scan=rng,
            disp=disp,
        )


def main():
    rclpy.init()
    d = D()
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    t0 = time.time()
    print(
        "t  x  y  spd  nav(x)  age_nav  smooth(x)  age_sm  out(x)  age_out  path  disp"
    )
    while time.time() - t0 < dur:
        r = d.poll()
        if not r["pos"]:
            continue
        t = time.time() - t0
        nav_x = r["nav"][0] if r["nav"] else float("nan")
        sm_x = r["smooth"][0] if r["smooth"] else float("nan")
        out_x = r["out"][0] if r["out"] else float("nan")
        an = r["age_nav"]
        asm = r["age_smooth"]
        ao = r["age_out"]
        print(
            f"{t:5.1f} {r['pos'][0]:7.3f} {r['pos'][1]:7.3f} "
            f"{(r['spd'] or 0):7.3f} "
            f"{nav_x:7.3f} {('%.2f' % an) if an is not None else 'NA':>7} "
            f"{sm_x:8.3f} {('%.2f' % asm) if asm is not None else 'NA':>7} "
            f"{out_x:7.3f} {('%.2f' % ao) if ao is not None else 'NA':>7} "
            f"{r['path_n']:5d} {r['disp']:7.4f}"
        )
    d.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
