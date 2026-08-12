#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster
from geometry_msgs.msg import TransformStamped, PoseWithCovarianceStamped
import math
import time
import argparse

class FakeSim(Node):
    def __init__(self, room_width=4.65, room_height=5.75, robot_radius=0.22, map_to_odom_x=0.0, map_to_odom_y=0.0):
        super().__init__('fake_sim')
        self.declare_parameter('room_width', room_width)
        self.declare_parameter('room_height', room_height)
        self.declare_parameter('wall_thickness', 0.2)
        self.declare_parameter('robot_radius', robot_radius)
        self.declare_parameter('map_to_odom_x', map_to_odom_x)
        self.declare_parameter('map_to_odom_y', map_to_odom_y)
        
        self.room_width = self.get_parameter('room_width').value
        self.room_height = self.get_parameter('room_height').value
        self.wall_thickness = self.get_parameter('wall_thickness').value
        self.robot_radius = self.get_parameter('robot_radius').value
        self.map_to_odom_x = self.get_parameter('map_to_odom_x').value
        self.map_to_odom_y = self.get_parameter('map_to_odom_y').value
        
        # Robot state
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        
        # Walls for collision [x1, y1, x2, y2] - matching map boundaries
        # Map origin: [-2.325, -2.875], size: 4.65m x 5.75m interior.
        # Default map_to_odom (0,0) = room centered at odom origin, which
        # puts the spawn inside the room interior (walls at +/-2.325/2.875).
        # OLD defaults (-2.360, -2.914) spawned the robot OUTSIDE the room
        # (odom (0,0) == map (2.36, 2.914), past the top-right corner): the
        # wall clamp wedged it in the corner, the laser saw walls everywhere,
        # and collision_monitor zeroed all cmd_vel - Nav2 could never move.
        half_w = self.room_width / 2
        half_h = self.room_height / 2
        # Map is centered at (map_to_odom_x, map_to_odom_y) in odom frame
        # So walls are at map_to_odom_x +/- half_w, map_to_odom_y +/- half_h
        mx = self.map_to_odom_x
        my = self.map_to_odom_y
        self.walls = [
            # Bottom wall
            [mx - half_w, my - half_h, mx + half_w, my - half_h],
            # Top wall
            [mx - half_w, my + half_h, mx + half_w, my + half_h],
            # Left wall
            [mx - half_w, my - half_h, mx - half_w, my + half_h],
            # Right wall
            [mx + half_w, my - half_h, mx + half_w, my + half_h],
        ]
        
        # Publishers
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 1)
        
        # Subscribers
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        
        # TF broadcasters
        self.odom_tf_broadcaster = TransformBroadcaster(self)
        self.static_tf_broadcaster = StaticTransformBroadcaster(self)
        
        # Broadcast static transforms
        self.broadcast_static_transforms()
        
        # Publish initial odom->base_footprint transform immediately so Nav2 can start
        self._publish_initial_odom_tf()
        
        # Timer for simulation step
        self.last_time = self.get_clock().now()
        self.timer = self.create_timer(0.02, self.sim_step)
        
        # Publish initial pose after AMCL has had time to activate
        self._initial_pose_timer = self.create_timer(3.5, self._publish_initial_pose_once)
        
        self.get_logger().info('Fake sim started')
    
    def _publish_initial_pose_once(self, *args):
        self.publish_initial_pose()
        if hasattr(self, '_initial_pose_timer'):
            self.destroy_timer(self._initial_pose_timer)
    
    def _publish_initial_odom_tf(self):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = 0.0
        t.transform.rotation.w = 1.0
        self.odom_tf_broadcaster.sendTransform(t)
    
    def broadcast_static_transforms(self):
        # base_footprint -> base_link
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_footprint'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.01
        t.transform.rotation.w = 1.0
        self.static_tf_broadcaster.sendTransform(t)
        
        # base_link -> imu
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_link'
        t.child_frame_id = 'imu'
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.1
        t.transform.rotation.w = 1.0
        self.static_tf_broadcaster.sendTransform(t)
        
        # base_link -> scan
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'base_link'
        t.child_frame_id = 'base_scan'
        t.transform.translation.x = 0.0
        t.transform.translation.y = 0.0
        t.transform.translation.z = 0.15
        t.transform.rotation.w = 1.0
        self.static_tf_broadcaster.sendTransform(t)
    
    def cmd_vel_callback(self, msg):
        self.vx = msg.linear.x
        self.vy = msg.linear.y
        self.vz = msg.angular.z
    
    def publish_initial_pose(self):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose.position.x = self.x
        msg.pose.pose.position.y = self.y
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = 0.0
        msg.pose.pose.orientation.w = 1.0
        cov = [0.0] * 36
        cov[0] = 0.25
        cov[7] = 0.25
        cov[35] = 0.0685
        msg.pose.covariance = cov
        self.initial_pose_pub.publish(msg)
        self.get_logger().info(f'Published initial pose: ({self.x:.2f}, {self.y:.2f})')
    
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
        ray_end_x = ox + cos_a * 10.0
        ray_end_y = oy + sin_a * 10.0
        
        for wall in self.walls:
            pt = self.line_intersection(ox, oy, ray_end_x, ray_end_y,
                                       wall[0], wall[1], wall[2], wall[3])
            if pt:
                dist = math.sqrt((pt[0]-ox)**2 + (pt[1]-oy)**2)
                min_dist = min(min_dist, dist)
        
        return min_dist
    
    def sim_step(self):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now
        
        # Update position
        self.yaw += self.vz * dt
        self.x += (self.vx * math.cos(self.yaw) - self.vy * math.sin(self.yaw)) * dt
        self.y += (self.vx * math.sin(self.yaw) + self.vy * math.cos(self.yaw)) * dt
        
        # Wall collision - keep robot within map bounds
        half_w = self.room_width/2 - self.robot_radius
        half_h = self.room_height/2 - self.robot_radius
        mx = self.map_to_odom_x
        my = self.map_to_odom_y
        self.x = max(mx - half_w, min(mx + half_w, self.x))
        self.y = max(my - half_h, min(my + half_h, self.y))
        
        # Publish odom TF
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = math.sin(self.yaw/2)
        t.transform.rotation.w = math.cos(self.yaw/2)
        self.odom_tf_broadcaster.sendTransform(t)
        
        # Publish odometry
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = math.sin(self.yaw/2)
        odom.pose.pose.orientation.w = math.cos(self.yaw/2)
        odom.twist.twist.linear.x = self.vx
        odom.twist.twist.linear.y = self.vy
        odom.twist.twist.angular.z = self.vz
        self.odom_pub.publish(odom)
        
        # Publish laser scan
        scan = LaserScan()
        scan.header.stamp = now.to_msg()
        scan.header.frame_id = 'base_scan'
        scan.angle_min = 0.0
        scan.angle_max = 2.0 * math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.1
        scan.range_max = 10.0
        scan.ranges = []
        scan.intensities = []
        
        for i in range(360):
            angle = i * math.pi / 180.0
            dist = self.cast_ray(self.x, self.y, self.yaw + angle)
            scan.ranges.append(dist)
            scan.intensities.append(100.0)
        
        self.scan_pub.publish(scan)

def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--room-width', type=float, default=4.65)
    parser.add_argument('--room-height', type=float, default=5.75)
    parser.add_argument('--robot-radius', type=float, default=0.22)
    parser.add_argument('--map-to-odom-x', type=float, default=0.0)
    parser.add_argument('--map-to-odom-y', type=float, default=0.0)
    parsed_args, _ = parser.parse_known_args(args)
    
    rclpy.init(args=args)
    node = FakeSim(
        room_width=parsed_args.room_width,
        room_height=parsed_args.room_height,
        robot_radius=parsed_args.robot_radius,
        map_to_odom_x=parsed_args.map_to_odom_x,
        map_to_odom_y=parsed_args.map_to_odom_y
    )
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()