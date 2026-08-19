#!/usr/bin/env python3
"""Wrapper to run fake_sim_lyrical with proper ROS2 initialization."""
import os
import sys

# Set environment before importing rclpy
os.environ['ROS_DOMAIN_ID'] = '30'

# Add src to path
sys.path.insert(0, '/home/koko/house_cleaner_ws/src')
sys.path.insert(0, '/home/koko/house_cleaner_ws/src/house_cleaner_bringup')

# Now import and run
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster
import math

class FakeSimLyrical(Node):
    def __init__(self):
        super().__init__('fake_sim_lyrical')
        self.declare_parameter('room_width', 4.65)
        self.declare_parameter('room_height', 5.75)
        self.declare_parameter('robot_radius', 0.22)

        self.room_width = self.get_parameter('room_width').value
        self.room_height = self.get_parameter('room_height').value
        self.robot_radius = self.get_parameter('robot_radius').value

        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0

        half_w = self.room_width / 2
        half_h = self.room_height / 2
        self.walls = [
            [-half_w, -half_h, half_w, -half_h],
            [-half_w, half_h, half_w, half_h],
            [-half_w, -half_h, -half_w, half_h],
            [half_w, -half_h, half_w, half_h],
        ]

        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/initialpose', 1)

        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)

        self.odom_tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)

        self.broadcast_static_transforms()
        self._publish_initial_odom_tf()

        self.last_time = self.get_clock().now()
        self.timer = self.create_timer(0.02, self.sim_step)

        self.get_logger().info('Fake_sim_lyrical started')

    def cmd_vel_callback(self, msg):
        self.vx = msg.linear.x
        self.vy = msg.linear.y
        self.vz = msg.angular.z

    def line_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        u = -((x1-x2)*(y1-y3) - (y1-y2)*(x1-x3)) / denom
        if 0 <= t <= 1 and 0 <= u <= 1:
            return (x1 + t*(x2-x1), y1 + t*(y2-y1))
        return None

    def cast_ray(self, ox, oy, angle):
        min_dist = 10.0
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        for wall in self.walls:
            pt = self.line_intersection(ox, oy, ox + cos_a*10, oy + sin_a*10,
                                       wall[0], wall[1], wall[2], wall[3])
            if pt:
                dist = math.hypot(pt[0]-ox, pt[1]-oy)
                min_dist = min(min_dist, dist)
        return min_dist

    def sim_step(self):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now

        self.yaw += self.vz * dt
        self.x += (self.vx * math.cos(self.yaw) - self.vy * math.sin(self.yaw)) * dt
        self.y += (self.vx * math.sin(self.yaw) + self.vy * math.cos(self.yaw)) * dt

        half_w = self.room_width/2 - self.robot_radius
        half_h = self.room_height/2 - self.robot_radius
        self.x = max(-half_w, min(half_w, self.x))
        self.y = max(-half_h, min(half_h, self.y))

        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.w = math.cos(self.yaw/2)
        t.transform.rotation.z = math.sin(self.yaw/2)
        self.odom_tf_broadcaster.sendTransform(t)

        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.w = math.cos(self.yaw/2)
        odom.twist.twist.angular.z = self.vz
        self.odom_pub.publish(odom)

        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = 'base_scan'
        scan.angle_min = 0.0
        scan.angle_max = 2.0 * math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.1
        scan.range_max = 10.0
        scan.ranges = [self.cast_ray(self.x, self.y, i * math.pi / 180.0) 
                       for i in range(360)]
        scan.intensities = [100.0] * 360
        self.scan_pub.publish(scan)

    def broadcast_static_transforms(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_footprint'
        t.child_frame_id = 'base_link'
        t.transform.translation.z = 0.01
        t.transform.rotation.w = 1.0
        self.static_tf_broadcaster.sendTransform(t)

    def _publish_initial_odom_tf(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.rotation.w = 1.0
        self.odom_tf_broadcaster.sendTransform(t)


def main():
    rclpy.init()
    node = FakeSimLyrical()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()