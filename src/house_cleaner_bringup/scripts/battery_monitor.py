#!/usr/bin/env python3
"""Live battery monitor for house_cleaner_assistant.

Usage:
  source /opt/ros/jazzy/setup.bash
  source /home/koko/house_cleaner_ws/env.sh
  python3 src/house_cleaner_bringup/scripts/battery_monitor.py
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
import sys


class Monitor(Node):
    def __init__(self):
        super().__init__('house_cleaner_monitor')
        self.battery_pct = None
        self.last_battery_update = None

        self.create_subscription(BatteryState, '/battery_state', self._battery_cb, 10)
        self._timer = self.create_timer(1.0, self._tick)
        self._last_print = ''

    def _battery_cb(self, msg):
        pct = msg.percentage
        self.battery_pct = pct * 100.0 if pct <= 1.0 else pct
        self.last_battery_update = self.get_clock().now()

    def _tick(self):
        battery_str = f'{self.battery_pct:.1f}%' if self.battery_pct is not None else '--'

        if self.battery_pct is not None:
            bar_len = 20
            filled = int(bar_len * self.battery_pct / 100.0)
            bar = '█' * filled + '░' * (bar_len - filled)
        else:
            bar = '░' * 20

        elapsed = ''
        if self.last_battery_update:
            age = (self.get_clock().now() - self.last_battery_update).nanoseconds / 1e9
            elapsed = f' (updated {age:.0f}s ago)'

        output = (
            f'\033[2J\033[H'
            f'╔{"═" * 58}╗\n'
            f'║  HOUSE CLEANER — BATTERY MONITOR{" " * 24}║\n'
            f'╠{"═" * 58}╣\n'
            f'║  Battery    : [{bar}] {battery_str:<10}{elapsed:<18}║\n'
            f'╚{"═" * 58}╗\n'
        )

        if output != self._last_print:
            print(output, end='', flush=True)
            self._last_print = output

    def destroy_node(self):
        print('\nMonitor stopped.')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Monitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
