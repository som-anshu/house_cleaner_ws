#!/usr/bin/env python3
"""
house_cleaner_assistant_lyrical.py

Autonomous cleaning supervisor for ROS2 Lyrical (no Nav2 dependency).
Uses direct /cmd_vel publishing instead of Nav2 actions.

Features:
- Boustrophedon coverage from grid bounds
- Battery simulation (/battery_state)
- Auto-return to dock at low battery
- Collision-avoidance via laser scan
"""
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PoseStamped
from sensor_msgs.msg import BatteryState, LaserScan
from nav_msgs.msg import Odometry, OccupancyGrid

# Room bounds (from house_room.world)
X_MIN, X_MAX = -2.325, 2.325
Y_MIN, Y_MAX = -2.875, 2.875

# Dock parameters
DOCK_X, DOCK_Y = 0.0, 2.75
DOCK_YAW = math.pi / 2.0
CREEP_STOP_RANGE = 0.13  # Laser front reading when seated

# Battery constants
VOLTAGE_FULL = 12.6
VOLTAGE_EMPTY = 10.0


def yaw_from_quat(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def normalize_angle(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class HouseCleanerAssistantLyrical(Node):
    def __init__(self):
        super().__init__('house_cleaner_assistant_lyrical')

        # Parameters
        self.declare_parameter('battery.drain_rate', 0.12)
        self.declare_parameter('battery.charge_rate', 1.20)
        self.declare_parameter('battery.low_threshold', 35.0)
        self.declare_parameter('battery.charge_target', 95.0)
        self.declare_parameter('mission.strip_width', 0.60)

        self.drain_rate = self.get_parameter('battery.drain_rate').value
        self.charge_rate = self.get_parameter('battery.charge_rate').value
        self.low_threshold = self.get_parameter('battery.low_threshold').value
        self.charge_target = self.get_parameter('battery.charge_target').value
        self.strip_width = self.get_parameter('mission.strip_width').value

        # State
        self.battery_pct = 100.0
        self.docked = False
        self.state = "INITIALIZING"
        self.goals = []
        self.goal_idx = 0
        self.current_goal = None
        self.last_scan = None
        self.current_pose = (0.0, 0.0, 0.0)

        # Publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.battery_pub = self.create_publisher(BatteryState, '/battery_state', 10)
        self.goal_pub = self.create_publisher(PoseStamped, '/current_goal', 10)

        # Subscribers
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.create_subscription(OccupancyGrid, '/map', self.map_callback, 10)

        # Timer for main loop
        self.create_timer(0.1, self.control_loop)

        # Generate initial goals
        self.generate_coverage_goals()

        self.get_logger().info(
            f"Assistant ready: battery={self.battery_pct}%, "
            f"low={self.low_threshold}%, strip={self.strip_width}m"
        )

    def odom_callback(self, msg):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        q = msg.pose.pose.orientation
        yaw = yaw_from_quat(q)
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.current_pose = (x, y, yaw)

    def scan_callback(self, msg):
        self.last_scan = msg

    def map_callback(self, msg):
        # Would regenerate goals on large map updates, but for now use fixed bounds
        pass

    def generate_coverage_goals(self):
        """Generate boustrophedon coverage grid."""
        margin = 0.37  # Safety margin from walls
        y = Y_MIN + self.strip_width / 2
        row = 0

        while y <= Y_MAX - self.strip_width / 2:
            if row % 2 == 0:
                x0, x1, yaw0, yaw1 = X_MIN + margin, X_MAX - margin, 0.0, 0.0
            else:
                x0, x1, yaw0, yaw1 = X_MAX - margin, X_MIN + margin, math.pi, 0.0

            x = x0
            while (row % 2 == 0 and x < x1) or (row % 2 == 1 and x > x1):
                self.goals.append((x, y, yaw0))
                x += 0.5 if (row % 2 == 0) else -0.5
            y += self.strip_width
            row += 1

        self.get_logger().info(f"Generated {len(self.goals)} coverage goals")

    def front_clearance(self):
        if self.last_scan is None:
            return None
        n = len(self.last_scan.ranges)
        mid = 0  # Forward is index 0
        sector = max(1, int(n * (15.0 / 360.0)))
        vals = [self.last_scan.ranges[(mid + i) % n] for i in range(-sector, sector + 1)]
        vals = [v for v in vals if math.isfinite(v) and v > self.last_scan.range_min]
        return min(vals) if vals else None

    def simple_navigation(self, target_x, target_y, target_yaw):
        """Simple proportional navigation to goal."""
        x, y, yaw = self.current_pose
        
        # Angle to target
        angle_to = math.atan2(target_y - y, target_x - x)
        angle_error = normalize_angle(angle_to - yaw)
        
        # Distance
        dist = math.hypot(target_x - x, target_y - y)
        
        cmd = Twist()
        
        # Rotate to face target
        if abs(angle_error) > 0.1:
            cmd.angular.z = 0.5 if angle_error > 0 else -0.5
        # Move forward if facing target and far enough
        elif dist > 0.1:
            # Check for obstacles
            clearance = self.front_clearance()
            if clearance is None or clearance > 0.3:
                cmd.linear.x = min(0.5, dist * 0.5)
        
        return cmd, dist < 0.15

    def go_to_dock(self):
        """Simple dock approach."""
        x, y, yaw = self.current_pose
        
        # Turn to face dock
        target_yaw = DOCK_YAW
        angle_error = normalize_angle(target_yaw - yaw)
        
        cmd = Twist()
        cmd.angular.z = 0.3 if angle_error > 0.05 else (-0.3 if angle_error < -0.05 else 0.0)
        
        if abs(angle_error) < 0.05:
            # Move forward to dock
            dist_to_dock = math.hypot(DOCK_X - x, DOCK_Y - y)
            if dist_to_dock > 0.5:
                cmd.linear.x = 0.2
            else:
                # Creep to dock
                cmd.linear.x = 0.05
        
        return cmd

    def control_loop(self):
        """Main control loop."""
        dt = 0.1
        
        # Update battery
        if not self.docked and self.state == "CLEANING":
            self.battery_pct = max(0.0, self.battery_pct - self.drain_rate * dt)

        # Publish battery state
        battery = BatteryState()
        battery.header.stamp = self.get_clock().now().to_msg()
        battery.voltage = VOLTAGE_EMPTY + (VOLTAGE_FULL - VOLTAGE_EMPTY) * (self.battery_pct / 100.0)
        battery.percentage = self.battery_pct
        battery.power_supply_status = (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING if self.docked
            else BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        )
        self.battery_pub.publish(battery)

        # State machine
        if self.state == "INITIALIZING":
            self.generate_coverage_goals()
            self.state = "CLEANING"
            self.goal_idx = 0

        elif self.state == "CLEANING":
            # Check battery
            if self.battery_pct <= self.low_threshold:
                self.state = "RETURNING"
                self.get_logger().warn(f"Low battery ({self.battery_pct:.1f}%) - returning to dock")
            elif self.goal_idx < len(self.goals):
                # Navigate to next goal
                gx, gy, gyaw = self.goals[self.goal_idx]
                cmd, reached = self.simple_navigation(gx, gy, gyaw)
                self.cmd_vel_pub.publish(cmd)

                if reached:
                    self.goal_idx += 1
                    self.get_logger().info(f"Goal {self.goal_idx}/{len(self.goals)}")

        elif self.state == "RETURNING":
            # Dock
            cmd = self.go_to_dock()
            clearance = self.front_clearance()
            if clearance is not None and clearance < CREEP_STOP_RANGE:
                self.docked = True
                self.state = "CHARGING"
                self.get_logger().info("DOCKED - charging...")
            else:
                self.cmd_vel_pub.publish(cmd)

        elif self.state == "CHARGING":
            if self.battery_pct < self.charge_target:
                self.battery_pct = min(100.0, self.battery_pct + self.charge_rate * dt)
            else:
                self.state = "UNDOCKING"

        elif self.state == "UNDOCKING":
            # Back out of dock
            cmd = Twist()
            cmd.linear.x = -0.1
            self.cmd_vel_pub.publish(cmd)
            
            # Undock when backed up enough
            dist = math.hypot(DOCK_X - self.current_pose[0], DOCK_Y - self.current_pose[1])
            if dist > 0.6:
                self.docked = False
                self.state = "CLEANING"
                self.get_logger().info("Undocked - resuming cleaning")

        # Check if all goals done
        if self.state == "CLEANING" and self.goal_idx >= len(self.goals):
            self.state = "RETURNING"


def main(args=None):
    rclpy.init(args=args)
    node = HouseCleanerAssistantLyrical()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()