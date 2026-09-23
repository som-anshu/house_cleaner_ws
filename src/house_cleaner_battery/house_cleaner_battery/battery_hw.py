#!/usr/bin/env python3
"""Real-hardware battery + dock backend for the TurtleBot3 Burger.

This node is the *hardware* counterpart of ``battery_sim``: it publishes the
same ``/battery_state`` topic and the same ``/dock/command`` <-> ``/dock/state``
contract, so the mission supervisor is unchanged between sim and real.

The custom dock exposes two digital inputs (seated, charging-fault) and one
analog input (charge current).  On the Burger the battery reads are normally
served by the OpenCR BMS over ``sensor_msgs/BatteryState`` directly; this
node wraps that stream with the dock state machine the supervisor expects.

ROS2 parameters (namespaced under ``battery.``):
  ``batt_topic``        - incoming battery state topic (default
                          /battery_state_opencr — the raw OpenCR BMS stream;
                          MUST differ from the node's own published
                          /battery_state output to avoid a feedback loop)
  ``seat_topic``        - digital-in topic reporting robot-seated (default
                          /dock/seated, std_msgs/Bool)
  ``current_topic``     - analog-in topic reporting charge current (default
                          /dock/current, std_msgs/Float64)
  ``fault_topic``       - digital-in topic reporting a dock fault (default
                          /dock/fault, std_msgs/Bool)
  ``charge_rate``       - %/s while docked (default 0.80)
  ``low_threshold``     - % at which the supervisor returns to dock (40.0)
  ``charge_target``     - % at which the supervisor resumes cleaning (95.0)
  ``voltage_full``      - V at 100 % (12.6)
  ``voltage_empty``     - V at 0 % (10.0)
"""

import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

from std_msgs.msg import Bool, Float64
from sensor_msgs.msg import BatteryState
from house_cleaner_msgs.msg import DockCommand, DockState


class BatteryHw(Node):
    def __init__(self):
        super().__init__("battery_hw")

        self.declare_parameter("batt_topic", "/battery_state_opencr")
        self.declare_parameter("seat_topic", "/dock/seated")
        self.declare_parameter("current_topic", "/dock/current")
        self.declare_parameter("fault_topic", "/dock/fault")
        self.declare_parameter("charge_rate", 0.80)
        self.declare_parameter("low_threshold", 40.0)
        self.declare_parameter("charge_target", 95.0)
        self.declare_parameter("voltage_full", 12.6)
        self.declare_parameter("voltage_empty", 10.0)

        batt_topic = self.get_parameter("batt_topic").value
        seat_topic = self.get_parameter("seat_topic").value
        current_topic = self.get_parameter("current_topic").value
        fault_topic = self.get_parameter("fault_topic").value
        self.charge_rate = self.get_parameter("charge_rate").value
        self.low_threshold = self.get_parameter("low_threshold").value
        self.charge_target = self.get_parameter("charge_target").value
        self.voltage_full = self.get_parameter("voltage_full").value
        self.voltage_empty = self.get_parameter("voltage_empty").value

        # Battery state
        self.battery_pct = 100.0
        self.seated = False
        self.charging = False
        self.fault = False
        self.current = 0.0
        self.voltage = self.voltage_full
        self.charge_cmd = DockCommand.CMD_STOP

        # Bridge the real BMS stream (OpenCR) into our contract.
        self.batt_sub = self.create_subscription(
            BatteryState, batt_topic, self._batt_cb, 10
        )
        # Digital inputs from the custom dock.
        self.seat_sub = self.create_subscription(
            Bool, seat_topic, self._seat_cb, 10
        )
        self.current_sub = self.create_subscription(
            Float64, current_topic, self._current_cb, 10
        )
        self.fault_sub = self.create_subscription(
            Bool, fault_topic, self._fault_cb, 10
        )

        self.battery_pub = self.create_publisher(BatteryState, "/battery_state", 10)
        self.dock_state_pub = self.create_publisher(DockState, "/dock/state", 10)
        self.dock_cmd_sub = self.create_subscription(
            DockCommand, "/dock/command", self._dock_cmd_cb, 10
        )

        self.create_timer(0.2, self._battery_timer_cb)

        self.get_logger().info(
            f"Battery HW ready: batt={batt_topic} seat={seat_topic} "
            f"current={current_topic} fault={fault_topic}"
        )

    # ------------------------------------------------------------------ I/O
    def _batt_cb(self, msg):
        # sensor_msgs/BatteryState.percentage is 0..1 on the OpenCR.
        pct = msg.percentage
        self.battery_pct = pct * 100.0 if 0.0 <= pct <= 1.0 else pct
        self.voltage = msg.voltage if msg.voltage > 0.0 else self.voltage

    def _seat_cb(self, msg):
        self.seated = bool(msg.data)

    def _current_cb(self, msg):
        self.current = float(msg.data)
        # Only clear charging when current is explicitly zero/negative AND
        # we are seated; a brief 0-sample between ticks must not flap the
        # dock state machine mid-charge.
        if self.current <= 0.0 and self.seated:
            self.charging = False
        elif self.current > 0.0:
            self.charging = True

    def _fault_cb(self, msg):
        self.fault = bool(msg.data)
        if self.fault:
            self.charging = False

    def _dock_cmd_cb(self, msg):
        self.charge_cmd = msg.command
        # The real dock driver latches the command to its GPIO/serial line;
        # here we just mirror it into the state machine so the supervisor
        # sees the intended action reflected in /dock/state.
        if msg.command == DockCommand.CMD_START:
            self.fault = False
            # Arm charging intent.  Actual current still gates
            # dstate.charging via _current_cb — but without this the
            # state machine never left IDLE when current was quiet at
            # CMD_START time, and a late current sample looked like a
            # spontaneous charge.
            self.charging = True
        elif msg.command == DockCommand.CMD_STOP:
            self.charging = False
        elif msg.command == DockCommand.CMD_FAULT:
            self.fault = True
            self.charging = False

    # ------------------------------------------------------------------ tick
    def _battery_timer_cb(self):
        # On real hardware the OpenCR BMS is authoritative; we only re-publish
        # the supervisor-friendly contract and the dock state machine.
        msg = BatteryState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.voltage = self.voltage
        # ROS standard: percentage is 0..1 (match battery_sim / OpenCR).
        msg.percentage = self.battery_pct / 100.0
        msg.present = True
        charging_now = self.charging and not self.fault and self.seated
        if self.seated:
            msg.power_supply_status = (
                BatteryState.POWER_SUPPLY_STATUS_FULL
                if self.battery_pct >= 99.9
                else (
                    BatteryState.POWER_SUPPLY_STATUS_CHARGING
                    if charging_now
                    else BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
                )
            )
        else:
            msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        self.battery_pub.publish(msg)

        dstate = DockState()
        dstate.seated = self.seated
        dstate.charging = self.charging and not self.fault
        dstate.state = (
            DockState.STATE_FAULT
            if self.fault
            else (DockState.STATE_CHARGING if dstate.charging else DockState.STATE_IDLE)
        )
        dstate.current = self.current
        dstate.voltage = self.voltage
        self.dock_state_pub.publish(dstate)


def main():
    rclpy.init()
    node = BatteryHw()
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