#!/usr/bin/env python3
"""Live battery + mission monitor for house_cleaner_assistant.

Usage:
  source /opt/ros/jazzy/setup.bash
  source /home/koko/house_cleaner_ws/env.sh
  python3 src/house_cleaner_bringup/scripts/battery_monitor.py
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from nav2_msgs.msg import NavigateToPoseFeedback
from geometry_msgs.msg import PoseStamped
import sys


class Monitor(Node):
    def __init__(self):
        super().__init__('house_cleaner_monitor')
        self.battery_pct = None
        self.current_goal = None
        self.state = 'INIT'
        self.goal_num = 0
        self.total_goals = 16

        self.create_subscription(BatteryState, '/battery_state', self._battery_cb, 10)
        self.create_subscription(PoseStamped, '/current_goal', self._goal_cb, 10)
        self.create_subscription(NavigateToPoseFeedback, '/navigate_to_pose/_action/feedback', self._feedback_cb, 10)

        self._timer = self.create_timer(1.0, self._tick)
        self._last_print = ''

    def _battery_cb(self, msg):
        pct = msg.percentage
        self.battery_pct = pct * 100.0 if pct <= 1.0 else pct
        # Infer state from battery when no goal yet
        if self.state in ('INIT', 'CHARGING', 'DONE'):
            if self.battery_pct < 35.0:
                self.state = 'RETURNING'

    def _goal_cb(self, msg):
        x = msg.pose.position.x
        y = msg.pose.position.y
        self.current_goal = (x, y)

        # Infer state from goal coordinates
        if abs(x) < 0.3 and y > 2.0:
            self.state = 'DOCKING'
        elif abs(x) < 0.3 and 1.5 < y < 2.2:
            self.state = 'RETURNING'
        else:
            if self.state not in ('CHARGING', 'DONE', 'DOCKING'):
                self.state = 'CLEANING'

    def _feedback_cb(self, msg):
        # Extract goal number from feedback if available
        if hasattr(msg, 'current_pose') and self.state == 'CLEANING':
            pass  # Could track distance remaining

    def _tick(self):
        battery_str = f'{self.battery_pct:.1f}%' if self.battery_pct is not None else '--'
        goal_str = f'({self.current_goal[0]:.2f}, {self.current_goal[1]:.2f})' if self.current_goal else '--'

        # Battery bar
        if self.battery_pct is not None:
            bar_len = 20
            filled = int(bar_len * self.battery_pct / 100.0)
            bar = '█' * filled + '░' * (bar_len - filled)
        else:
            bar = '░' * 20

        output = (
            f'\033[2J\033[H'  # clear screen
            f'╔{"═" * 58}╗\n'
            f'║  HOUSE CLEANER — LIVE MONITOR{" " * 27}║\n'
            f'╠{"═" * 58}╣\n'
            f'║  State      : {self.state:<20} Goal: {self.goal_num:>2}/{self.total_goals:<14}║\n'
            f'║  Battery    : [{bar}] {battery_str:<10}║\n'
            f'║  Current goal: {goal_str:<39}║\n'
            f'╚{"═" * 58}╝\n'
            f'  Watching: /battery_state, /current_goal, /navigate_to_pose\n'
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
