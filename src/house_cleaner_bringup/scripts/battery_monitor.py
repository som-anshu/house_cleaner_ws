#!/usr/bin/env python3
"""Live battery monitor for house_cleaner_assistant.

Usage:
  source /opt/ros/jazzy/setup.bash
  source /home/koko/house_cleaner_ws/env.sh
  python3 src/house_cleaner_bringup/scripts/battery_monitor.py

Docker/tmux-safe: Uses explicit line breaks instead of cursor positioning,
and ASCII characters instead of Unicode block chars for reliable render in
docker-compose logs and tmux.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState


class Monitor(Node):
    def __init__(self):
        super().__init__('house_cleaner_monitor')
        self.battery_pct = None
        self.last_battery_update = None

        self.create_subscription(BatteryState, '/battery_state', self._battery_cb, 10)
        self._timer = self.create_timer(1.0, self._tick)

    def _battery_cb(self, msg):
        pct = msg.percentage
        self.battery_pct = pct * 100.0 if pct <= 1.0 else pct
        self.last_battery_update = self.get_clock().now()

    def _tick(self):
        battery_str = f'{self.battery_pct:.1f}%' if self.battery_pct is not None else '--'

        if self.battery_pct is not None:
            bar_len = 16
            filled = int(bar_len * self.battery_pct / 100.0)
            # Use ASCII '#' and '-' for reliable rendering in docker-compose/tmux
            bar = '#' * filled + '-' * (bar_len - filled)
        else:
            bar = '-' * 16

        # fixed interior width so the box edges align; width == the
        # separator/header rows (58 interior chars + 2 border chars).
        # bar_len 16 keeps room for the "(updated Xs ago)" staleness
        # text even at 100.0% — that indicator is the monitor's point.
        content = f'  Battery    : [{bar}] {battery_str}'
        if self.last_battery_update:
            age = (self.get_clock().now() - self.last_battery_update).nanoseconds / 1e9
            elapsed = f' (updated {age:.0f}s ago)'
            # only append if it fits, else drop — never overflow the box
            if len(content) + len(elapsed) <= 58:
                content += elapsed
        content = content.ljust(58)

        # Print each line separately with explicit newlines.
        # This avoids ANSI cursor codes (clear screen, cursor home) that
        # get mangled by docker-compose's log prefix injection.
        # Use ASCII box characters for reliable rendering in all terminals.
        print(
            '+' + '=' * 58 + '+',
            '|' + ' HOUSE CLEANER — BATTERY MONITOR'.ljust(58) + '|',
            '+' + '-' * 58 + '+',
            '|' + content + '|',
            '+' + '=' * 58 + '+',
            sep='\n',
            flush=True
        )

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