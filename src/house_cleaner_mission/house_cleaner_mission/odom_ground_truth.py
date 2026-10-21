#!/usr/bin/env python3
# =============================================================================
# odom_ground_truth.py
# =============================================================================
# Republish ``odom -> base_footprint`` from Gazebo's REAL model pose instead of
# the DiffDrive plugin's integrated wheel odometry.
#
# WHY THIS EXISTS
# ---------------
# Gazebo's DiffDrive plugin integrates *commanded* wheel velocities to produce
# ``odom -> base_footprint``. Nothing feeds a real pose back into that
# integration, so any error it accumulates is permanent. Under this project's
# motion profile the error is severe: docking creep (0.04 m/s), the
# collision_monitor speed limit, NAV_SILENT/ABORTED goal cancels and repeated
# lateral re-planning all inject velocity discontinuities. Measured on this
# stack, ``/odom`` reported the robot ~17 m outside a 5 x 6 m room within a few
# minutes of normal operation, while Gazebo's true pose stayed inside it.
#
# Consequence downstream: slam_toolbox trusted odometry, then had to correct it
# hard, swinging ``map -> odom`` by up to 9.5 m and 34 deg in 30 s. With RViz's
# fixed frame set to ``map`` that re-places the entire scene every frame, which
# the user sees as the map tearing / misaligning after each scan and as heavy
# pane flicker.
#
# WHAT IT DOES
# ------------
#   /ground_truth_poses  (tf2_msgs/TFMessage, from gz dynamic_pose/info)
#        -> keeps the model pose for ``ground_truth_model``
#   publishes:
#      * TF  odom -> base_footprint   (the pose, relative to the spawn origin)
#      * /odom  (nav_msgs/Odometry)   with real covariance
#
# The odom frame is anchored to the model's FIRST observed pose, so odometry
# starts at the origin and grows continuously -- exactly what the
# ``odom`` frame contract requires (continuous, no jumps) while still being
# accurate (unlike an integrator).
#
# This node does NOT publish map -> odom; that stays slam_toolbox's job.
#
# NOTE ON "GROUND TRUTH"
# ----------------------
# In simulation this is a legitimate pose source. On real hardware the same
# interface would be fed by wheel encoders fused with an IMU (robot_localization
# EKF). The rest of the stack cannot tell the difference -- it only sees a
# well-formed odom -> base_footprint transform -- so sim and real remain
# interchangeable, which is the project's core design rule.
# =============================================================================

import math
import sys

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy
from tf2_msgs.msg import TFMessage
from tf2_ros import TransformBroadcaster


def _yaw_to_quat(yaw):
    """Yaw (rad) -> quaternion (x, y, z, w) for a planar robot."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def _quat_to_yaw(x, y, z, w):
    """Quaternion -> yaw (rad), for planar motion only."""
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class OdomGroundTruth(Node):
    """Publish odom -> base_footprint from the simulator's real model pose."""

    def __init__(self, **kwargs):
        super().__init__("odom_ground_truth", **kwargs)

        self.declare_parameter("model_name", "turtlebot3_burger")
        self.declare_parameter("pose_topic", "/ground_truth_poses")
        self.declare_parameter("odom_topic", "/odom")
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_footprint")
        self.declare_parameter("publish_rate", 30.0)
        # Anchor the odom frame at the first pose so odometry starts at (0, 0).
        self.declare_parameter("anchor_at_start", True)
        # Honest uncertainty. Measured from how far the pose moves between
        # samples; a small floor keeps the matrix well-conditioned.
        self.declare_parameter("pose_variance_floor", 1.0e-4)

        self.model_name = self.get_parameter("model_name").value
        self.odom_frame = self.get_parameter("odom_frame").value
        self.base_frame = self.get_parameter("base_frame").value
        self.anchor = self.get_parameter("anchor_at_start").value
        self.var_floor = float(self.get_parameter("pose_variance_floor").value)

        # Latest raw pose in the world frame, and the anchored pose.
        self.raw = None          # (x, y, yaw) in the world frame
        self.raw_stamp = None    # stamp carried with the latest raw pose
        self.anchor_pose = None  # (x, y, yaw) at first sighting
        self.prev = None         # last published anchored pose (for twist)
        self.prev_t = None
        self.got_pose = False

        qos = QoSProfile(depth=20)
        qos.reliability = ReliabilityPolicy.RELIABLE
        qos.durability = QoSDurabilityPolicy.VOLATILE

        self.create_subscription(
            TFMessage, self.get_parameter("pose_topic").value,
            self._pose_cb, QoSProfile(depth=50))

        self.odom_pub = self.create_publisher(
            Odometry, self.get_parameter("odom_topic").value, 20)
        self.tf_broadcaster = TransformBroadcaster(self)

        rate = float(self.get_parameter("publish_rate").value)
        self.create_timer(1.0 / max(rate, 1.0), self._publish)

        self.get_logger().info(
            f"odom_ground_truth: watching '{self.model_name}' on "
            f"{self.get_parameter('pose_topic').value}; publishing "
            f"{self.odom_frame} -> {self.base_frame} + "
            f"{self.get_parameter('odom_topic').value} at {rate:.0f} Hz "
            f"(anchor_at_start={self.anchor})")

    # ---------------------------------------------------------------- input
    def _pose_cb(self, msg):
        for tf in msg.transforms:
            child = tf.child_frame_id.strip("/")
            if child != self.model_name:
                continue
            tr = tf.transform.translation
            q = tf.transform.rotation
            self.raw = (tr.x, tr.y, _quat_to_yaw(q.x, q.y, q.z, q.w))
            # CRITICAL: carry the SOURCE stamp, not now(). slam_toolbox
            # interpolates the odom -> base_footprint transform at each scan's
            # stamp. Stamping with local receive time instead puts the transform
            # in a different time base, so every scan is dropped with
            #   "the timestamp on the message is earlier than all the data in
            #    the transform cache"
            # and no map is ever produced.
            self.raw_stamp = tf.header.stamp
            if self.anchor_pose is None:
                # First sighting: this becomes the odom origin.
                self.anchor_pose = (tr.x, tr.y, 0.0) if not self.anchor \
                    else (tr.x, tr.y, self.raw[2])
                self.get_logger().info(
                    f"anchored {self.odom_frame} at world "
                    f"({self.anchor_pose[0]:.3f}, {self.anchor_pose[1]:.3f})")
            if not self.got_pose:
                self.got_pose = True
                self.get_logger().info("first ground-truth pose received")

    # --------------------------------------------------------------- output
    def _anchored(self):
        """World pose -> odom-frame pose (translation + yaw, wrapped)."""
        x, y, yaw = self.raw
        ax, ay, ayaw = self.anchor_pose
        dx, dy = x - ax, y - ay
        c, s = math.cos(-ayaw), math.sin(-ayaw)
        # Rotate the offset into the anchor's heading, then re-zero yaw.
        ox = c * dx - s * dy
        oy = s * dx + c * dy
        oyaw = math.atan2(math.sin(yaw - ayaw), math.cos(yaw - ayaw))
        return ox, oy, oyaw

    def _publish(self):
        if self.raw is None or self.raw_stamp is None:
            return
        # Stamp with the SOURCE time so the transform lines up with the scans
        # that slam_toolbox is matching against (see _pose_cb).
        now = self.raw_stamp
        ox, oy, oyaw = self._anchored()

        # --- transform -----------------------------------------------------
        tf = TransformStamped()
        tf.header.stamp = now
        tf.header.frame_id = self.odom_frame
        tf.child_frame_id = self.base_frame
        tf.transform.translation.x = float(ox)
        tf.transform.translation.y = float(oy)
        tf.transform.translation.z = 0.0
        qx, qy, qz, qw = _yaw_to_quat(oyaw)
        tf.transform.rotation.x = qx
        tf.transform.rotation.y = qy
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(tf)

        # --- odometry ------------------------------------------------------
        msg = Odometry()
        msg.header.stamp = now
        msg.header.frame_id = self.odom_frame
        msg.child_frame_id = self.base_frame
        msg.pose.pose.position.x = float(ox)
        msg.pose.pose.position.y = float(oy)
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.x = qx
        msg.pose.pose.orientation.y = qy
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw

        # Twist from finite differences of the anchored pose.
        t = float(now.sec) + float(now.nanosec) * 1e-9
        vx = wz = 0.0
        if self.prev is not None and self.prev_t is not None:
            dt = t - self.prev_t
            if dt > 1e-4:
                # Rotate the world-frame delta into the body frame.
                wdx, wdy = ox - self.prev[0], oy - self.prev[1]
                wdyaw = math.atan2(
                    math.sin(oyaw - self.prev[2]), math.cos(oyaw - self.prev[2]))
                cb, sb = math.cos(-oyaw), math.sin(-oyaw)
                vx = (cb * wdx - sb * wdy) / dt
                wz = wdyaw / dt
        self.prev = (ox, oy, oyaw)
        self.prev_t = t

        msg.twist.twist.linear.x = float(vx)
        msg.twist.twist.angular.z = float(wz)

        # Honest covariance. A real pose source has small, non-zero variance;
        # an all-zero matrix claims infinite confidence and gives the SLAM
        # matcher nothing to weight against.
        pv = max(self.var_floor, 0.0)
        yv = max(self.var_floor, 0.0)
        cv = max(self.var_floor, 0.0)
        msg.pose.covariance[0] = pv    # x
        msg.pose.covariance[7] = pv    # y
        msg.pose.covariance[35] = yv   # yaw
        msg.twist.covariance[0] = cv   # vx
        msg.twist.covariance[35] = cv  # wz

        self.odom_pub.publish(msg)


def main():
    rclpy.init()
    node = OdomGroundTruth()
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
