#!/usr/bin/env python3
"""
Room coverage planner for house_cleaner fake_sim stack.

Usage:
  source /opt/ros/jazzy/setup.bash
  ROS_DOMAIN_ID=30 python3 coverage_planner.py

Sends a sequence of NavigateToPose goals in boustrophedon (lawnmower)
pattern over the free area of the map. Waits for each goal to complete
before sending the next. Exits when all goals are done or a goal fails.
"""
import math
import sys
import time

import rclpy
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Point, Quaternion
from std_msgs.msg import Header


# Room bounds from map.yaml: origin [-1.195, -2.385], size 4.65 x 5.75 m
ORIGIN_X = -1.195
ORIGIN_Y = -2.385
ROOM_W  = 4.65
ROOM_H  = 5.75

# Coverage stripe width (meters). 0.6 m = ~2x the laser effective range
# overlap for a 0.22m radius robot on a 0.05m resolution map.
STRIPE_WIDTH = 0.6


def make_pose(x: float, y: float, yaw: float = 0.0) -> PoseStamped:
    hdr = Header(frame_id="map", stamp=rclpy.time.Time().to_msg())
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    return PoseStamped(
        header=hdr,
        pose=geometry_msgs.msg.Pose(
            position=Point(x=x, y=y, z=0.0),
            orientation=Quaternion(x=0.0, y=0.0, z=qz, w=qw),
        ),
    )


def generate_boustrophedon(
    xmin: float, xmax: float, ymin: float, ymax: float, stripe_w: float
):
    """Yield (x, y, yaw) poses in a boustrophedon pattern."""
    y = ymin + stripe_w / 2.0
    row = 0
    while y <= ymax:
        if row % 2 == 0:
            x_start, x_end, yaw = xmin, xmax, 0.0
        else:
            x_start, x_end, yaw = xmax, xmin, math.pi
        yield (x_start, y, yaw)
        yield (x_end, y, yaw)
        y += stripe_w
        row += 1


class CoverageClient:
    def __init__(self):
        rclpy.init()
        self.node = rclpy.create_node("coverage_planner")
        self.client = ActionClient(
            self.node, NavigateToPose, "/navigate_to_pose"
        )
        self.goals = list(
            generate_boustrophedon(
                ORIGIN_X, ORIGIN_X + ROOM_W,
                ORIGIN_Y, ORIGIN_Y + ROOM_H,
                STRIPE_WIDTH,
            )
        )
        self.node.get_logger().info(
            f"Coverage planner ready: {len(self.goals)} goals over "
            f"{ROOM_W}m x {ROOM_H}m room (stripe={STRIPE_WIDTH}m)"
        )

    def wait_for_server(self, timeout: float = 30.0):
        if not self.client.wait_for_server(timeout_sec=timeout):
            self.node.get_logger().error(
                "NavigateToPose action server not available"
            )
            return False
        return True

    def send_goal(self, x: float, y: float, yaw: float):
        goal = NavigateToPose.Goal()
        goal.pose = make_pose(x, y, yaw)
        self.node.get_logger().info(
            f"→ Sending goal ({x:.2f}, {y:.2f}, yaw={yaw:.2f})"
        )
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=30.0)
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.node.get_logger().error("Goal rejected")
            return None
        self.node.get_logger().info("  Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self.node, result_future, timeout_sec=600.0)
        result = result_future.result()
        if result:
            return result.result
        return None

    def run(self):
        if not self.wait_for_server():
            rclpy.shutdown()
            return 1
        total = len(self.goals)
        for idx, (x, y, yaw) in enumerate(self.goals):
            self.node.get_logger().info(
                f"=== Goal {idx + 1}/{total} ==="
            )
            res = self.send_goal(x, y, yaw)
            if res is None:
                self.node.get_logger().error(
                    f"Goal {idx + 1}/{total} failed (no result)"
                )
                rclpy.shutdown()
                return 1
            if res.error_code != NavigateToPose.Result.NONE:
                self.node.get_logger().error(
                    f"Goal {idx + 1}/{total} failed: "
                    f"error_code={res.error_code} msg={res.error_msg}"
                )
                rclpy.shutdown()
                return 1
            self.node.get_logger().info(
                f"  ✓ Goal {idx + 1}/{total} SUCCEEDED"
            )
            # Brief pause before next leg so any TF/costmap resets settle
            time.sleep(0.5)
        self.node.get_logger().info(
            f"Coverage complete: {total}/{total} goals succeeded"
        )
        rclpy.shutdown()
        return 0


def main():
    cov = CoverageClient()
    sys.exit(cov.run())


if __name__ == "__main__":
    main()
