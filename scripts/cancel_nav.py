#!/usr/bin/env python3
"""Cancel any active NavigateToPose goals (best-effort recovery helper)."""
import sys

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from action_msgs.srv import CancelGoal
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient


def main():
    rclpy.init()
    node = rclpy.create_node("cancel_nav")
    client = ActionClient(node, NavigateToPose, "/navigate_to_pose")
    if not client.wait_for_server(timeout_sec=5.0):
        print("no navigate_to_pose server", file=sys.stderr)
        # Still try low-level cancel below.
    statuses = []
    sub = node.create_subscription(
        GoalStatusArray,
        "/navigate_to_pose/_action/status",
        lambda m: statuses.extend(m.status_list),
        10,
    )
    for _ in range(25):
        rclpy.spin_once(node, timeout_sec=0.2)
        if statuses:
            break
    active = [
        s for s in statuses
        if s.status in (GoalStatus.STATUS_ACCEPTED, GoalStatus.STATUS_EXECUTING)
    ]
    if not active:
        print("no active goals")
    else:
        cli = node.create_client(
            CancelGoal, "/navigate_to_pose/_action/cancel_goal"
        )
        for st in active:
            try:
                from action_msgs.msg import GoalInfo

                gi = GoalInfo()
                gi.goal_id = st.goal_id
                if cli.wait_for_service(timeout_sec=2.0):
                    req = CancelGoal.Request()
                    req.goal_info = gi
                    fut = cli.call_async(req)
                    rclpy.spin_until_future_complete(node, fut, timeout_sec=3.0)
                    print("cancelled", bytes(st.goal_id.uuid).hex()[:8])
                else:
                    # Fallback: ActionClient cancel-all path
                    client._cancel_goal_async(None)
                    print("fallback cancel attempted")
            except Exception as e:
                print("err", e, file=sys.stderr)
    # Also try empty-uuid cancel (some Nav2 versions accept it).
    try:
        client._cancel_goal_async(None)
    except Exception:
        pass
    node.destroy_subscription(sub)
    node.destroy_node()
    rclpy.shutdown()
    print("done")


if __name__ == "__main__":
    main()
