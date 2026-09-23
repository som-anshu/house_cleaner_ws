#!/usr/bin/env python3
"""Battery simulator backend for the house cleaner robot.

Publishes ``/battery_state`` (sensor_msgs/BatteryState) and drives the
``/dock/command`` <-> ``/dock/state`` contract that the mission supervisor
relies on.  The real dock backend (``battery_hw``) publishes the same
topics, so the supervisor never knows whether it is talking to a
simulated or a physical battery.

Drain model: ``drain_rate`` %/s while the robot is moving (|v| > speed
threshold).  Charge model: ``charge_rate`` %/s while the dock reports
``seated`` and ``charging``.  Voltage is interpolated linearly between
``voltage_empty`` and ``voltage_full`` so the percentage maps to a real-ish
voltage curve.

ROS2 parameters (all namespaced under ``battery.``):
  ``drain_rate``        - %/s while driving (default 0.20)
  ``charge_rate``       - %/s while docked (default 0.80)
  ``low_threshold``     - % at which the supervisor returns to dock (40.0)
  ``charge_target``     - % at which the supervisor resumes cleaning (95.0)
  ``voltage_full``      - V at 100 % (12.6)
  ``voltage_empty``     - V at 0 % (10.0)
  ``speed_threshold``   - m/s above which the robot is "moving" (0.03)
"""

import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile,
    QoSDurabilityPolicy,
    ReliabilityPolicy,
)

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, Header

from house_cleaner_msgs.msg import DockCommand, DockState


class BatterySim(Node):
    def __init__(self):
        super().__init__("battery_sim")

        self.declare_parameter("drain_rate", 0.20)
        self.declare_parameter("charge_rate", 0.80)
        self.declare_parameter("low_threshold", 40.0)
        self.declare_parameter("charge_target", 95.0)
        self.declare_parameter("voltage_full", 12.6)
        self.declare_parameter("voltage_empty", 10.0)
        self.declare_parameter("speed_threshold", 0.03)

        self.drain_rate = self.get_parameter("drain_rate").value
        self.charge_rate = self.get_parameter("charge_rate").value
        self.low_threshold = self.get_parameter("low_threshold").value
        self.charge_target = self.get_parameter("charge_target").value
        self.voltage_full = self.get_parameter("voltage_full").value
        self.voltage_empty = self.get_parameter("voltage_empty").value
        self.speed_threshold = self.get_parameter("speed_threshold").value

        # Battery state
        self.battery_pct = 100.0
        self.docked = False
        self.charging = False
        self.seated = False
        self.speed = 0.0
        self.charge_cmd = DockCommand.CMD_STOP
        self.empty_latched = False

        # Publishers / subscribers
        self.battery_pub = self.create_publisher(BatteryState, "/battery_state", 10)
        self.dock_state_pub = self.create_publisher(DockState, "/dock/state", 10)
        self.dock_cmd_sub = self.create_subscription(
            DockCommand, "/dock/command", self._dock_cmd_cb, 10
        )
        # The docking controller reports robot-seated state on /dock/seated;
        # we mirror it here so the supervisor's /dock/state contract is
        # identical whether the dock is simulated or physical.
        # TRANSIENT_LOCAL matches the publisher so a late subscriber still
        # receives the latched seated state (volatile would miss it).
        self.seated_sub = self.create_subscription(
            Bool,
            "/dock/seated",
            self._seated_cb,
            QoSProfile(
                depth=1,
                durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE,
            ),
        )
        # Listen to the smoothed cmd_vel (the chain that actually reaches the
        # robot) so drain matches real motion, not the raw controller output.
        self.cmd_sub = self.create_subscription(
            Twist, "/cmd_vel_smoothed", self._cmd_cb, 10
        )
        # Fallback: also drain on the raw /cmd_vel so the node works even
        # before the smoother/collision_monitor chain is up.
        self.cmd_sub_raw = self.create_subscription(
            Twist, "/cmd_vel", self._cmd_cb, 10
        )
        # Odom is the ground-truth motion source and is always present (Nav2's
        # EKF publishes it even if the cmd_vel smoothing chain is restarted or
        # renamed).  Draining from odometry makes low-battery reachable and
        # testable in every mode instead of only when a specific velocity
        # topic happens to be alive.
        self.odom_sub = self.create_subscription(
            Odometry, "/odom", self._odom_cb, 10
        )

        self.create_timer(0.2, self._battery_timer_cb)

        self.get_logger().info(
            f"Battery sim ready: drain={self.drain_rate:.2f}%/s "
            f"charge={self.charge_rate:.2f}%/s "
            f"low={self.low_threshold:.0f}% target={self.charge_target:.0f}%"
        )

    # ------------------------------------------------------------------ I/O
    def _cmd_cb(self, msg):
        # Only the linear speed matters for drain; angular velocity (spin in
        # place) does not consume meaningful energy.
        self.speed = math.hypot(msg.linear.x, msg.linear.y)

    def _odom_cb(self, msg):
        # Ground-truth motion source (always published).  Same speed model as
        # the cmd_vel callbacks — linear magnitude only.
        self.speed = math.hypot(
            msg.twist.twist.linear.x, msg.twist.twist.linear.y
        )

    def _dock_cmd_cb(self, msg):
        self.charge_cmd = msg.command
        if msg.command == DockCommand.CMD_START:
            self.charging = True
        elif msg.command == DockCommand.CMD_STOP:
            self.charging = False
        elif msg.command == DockCommand.CMD_FAULT:
            self.charging = False

    def _seated_cb(self, msg):
        # The docking controller is the single authority on whether the robot
        # is physically at the dock; we just mirror it into the state machine.
        was_seated = self.seated
        self.seated = bool(msg.data)
        self.docked = self.seated
        if self.seated and not was_seated:
            self.get_logger().info("DOCKED — robot seated, charging enabled")
        elif not self.seated and was_seated:
            self.charging = False
            self.get_logger().info("UNDOCKED — robot left the dock")

    # ------------------------------------------------------------------ tick
    def _battery_timer_cb(self):
        dt = 0.2
        # Re-read the rates each tick so operators can accelerate (or decelerate)
        # drain/charge on a live mission with `ros2 param set` — no relaunch or
        # rebuild needed.  The defaults from init are used when the params are
        # never touched.
        drain = self.get_parameter("drain_rate").value
        charge = self.get_parameter("charge_rate").value
        if self.seated and self.charging and self.battery_pct < 100.0:
            self.battery_pct = min(100.0, self.battery_pct + charge * dt)
            if self.battery_pct > 0.5 and self.empty_latched:
                self.empty_latched = False
                self.get_logger().info("Battery recovered from empty latch")
        elif not self.docked and self.speed > self.speed_threshold:
            self.battery_pct = max(0.0, self.battery_pct - drain * dt)

        # Hard empty event: latch once so supervisors/watchdogs can treat
        # 0 % as a fault, not a soft clamp that keeps looking "fine".
        if self.battery_pct <= 0.0 and not self.docked and not self.empty_latched:
            self.empty_latched = True
            self.get_logger().error(
                "BATTERY EMPTY (0%) — latched; mission should halt or dock"
            )
            # Stop any charge command so state is unambiguous.
            self.charging = False
            self.charge_cmd = DockCommand.CMD_STOP

        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = self.voltage_empty + (
            self.voltage_full - self.voltage_empty
        ) * (self.battery_pct / 100.0)
        # sensor_msgs/BatteryState.percentage is 0..1 (ROS standard).
        # Publishing 0..100 made the supervisor's "scale if <=1" heuristic
        # treat real 0.96% as 96% → charge exits immediately → dock loop.
        msg.percentage = self.battery_pct / 100.0
        msg.present = True
        charging_now = self.seated and self.charging
        if self.docked:
            msg.power_supply_status = (
                BatteryState.POWER_SUPPLY_STATUS_FULL
                if self.battery_pct >= 99.9
                else (
                    BatteryState.POWER_SUPPLY_STATUS_CHARGING
                    if charging_now
                    else BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
                )
            )
        elif self.empty_latched:
            # Dead / unknown residual — not a healthy "discharging" pack.
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
        else:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        self.battery_pub.publish(msg)

        # Publish dock state so the supervisor can read seated/charging.
        dstate = DockState()
        dstate.seated = self.seated
        dstate.charging = self.charging
        dstate.state = (
            DockState.STATE_CHARGING
            if self.seated and self.charging
            else DockState.STATE_IDLE
        )
        dstate.current = self.charge_rate if self.charging else 0.0
        dstate.voltage = msg.voltage
        self.dock_state_pub.publish(dstate)


def main():
    rclpy.init()
    node = BatterySim()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    sys.exit(0)


if __name__ == "__main__":
    main()