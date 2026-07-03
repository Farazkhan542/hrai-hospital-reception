#!/usr/bin/env python3
"""Navigation node — the robot's motion primitives, via Nav2.

Report mapping: **Robot primitives**. This node is a ROS2 *action server* for
``GoToLocation``. It turns a semantic location key (e.g. ``cardiology_room``)
into a metric pose using the knowledge base, then drives the robot there.

Two execution paths, selected by the ``use_nav2`` parameter:

  use_nav2 = true  (default) -- forward the pose to Nav2's ``/navigate_to_pose``
                                 action (real path planning + obstacle avoidance
                                 via the local planner) and relay feedback.
  use_nav2 = false           -- SIMULATION FALLBACK: no Gazebo/Nav2 needed. We
                                 fake the motion with a timed countdown and log
                                 the pose. This keeps the dialogue+reasoning demo
                                 runnable on a weak, no-GPU Windows/WSL2 machine.

The fallback is important for the CPU-only target: it lets the graded social
reasoning be demonstrated end-to-end even when Nav2 is too heavy to run.
"""

from __future__ import annotations

import math
import time

import rclpy
from rclpy.action import ActionServer, ActionClient, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from hospital_reception_interfaces.action import GoToLocation

from hospital_reception.knowledge_base import KnowledgeBase


def _yaw_to_quaternion(yaw: float):
    """Return (z, w) of a quaternion for a planar rotation about Z.

    We avoid a hard dependency on tf_transformations for this simple 2D case.
    """
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class NavigationNode(Node):
    """Action server that guides the robot to named locations."""

    def __init__(self):
        super().__init__('navigation_node')

        # -- parameters ---------------------------------------------------- #
        # use_nav2=false => simulated motion (no Gazebo/Nav2). Default true.
        self.declare_parameter('use_nav2', True)
        # Frame Nav2 goals are expressed in (map for a localized robot).
        self.declare_parameter('goal_frame', 'map')
        # Simulated-motion pacing (seconds of fake travel) for the fallback.
        self.declare_parameter('sim_travel_time', 6.0)

        self.use_nav2 = self.get_parameter('use_nav2').value
        self.goal_frame = self.get_parameter('goal_frame').value
        self.sim_travel_time = float(self.get_parameter('sim_travel_time').value)

        self.kb = KnowledgeBase()

        # Reentrant group so action feedback and (optional) Nav2 client calls can
        # interleave under a multi-threaded executor.
        self._cb_group = ReentrantCallbackGroup()

        # -- our action server (interaction node is the client) ------------ #
        self._action_server = ActionServer(
            self,
            GoToLocation,
            'goto_location',
            execute_callback=self.execute_callback,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
            callback_group=self._cb_group,
        )

        # -- optional Nav2 client ------------------------------------------ #
        self._nav2_client = None
        if self.use_nav2:
            # Imported lazily so the fallback path has zero Nav2 dependency.
            from nav2_msgs.action import NavigateToPose
            self._NavigateToPose = NavigateToPose
            self._nav2_client = ActionClient(
                self, NavigateToPose, 'navigate_to_pose',
                callback_group=self._cb_group,
            )

        mode = 'Nav2' if self.use_nav2 else 'SIMULATED (use_nav2=false)'
        self.get_logger().info(
            f"Navigation node ready on action /goto_location. Mode: {mode}."
        )

    # ------------------------------------------------------------------ #
    # Goal / cancel acceptance policy.
    # ------------------------------------------------------------------ #
    def _goal_callback(self, goal_request):
        key = goal_request.location_key
        if self.kb.coords_for(key) is None:
            self.get_logger().warn(f"Rejecting goal: unknown location '{key}'.")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        return CancelResponse.ACCEPT

    # ------------------------------------------------------------------ #
    # Main execution: dispatch to Nav2 or the simulated fallback.
    # ------------------------------------------------------------------ #
    def execute_callback(self, goal_handle):
        key = goal_handle.request.location_key
        coords = self.kb.coords_for(key)
        result = GoToLocation.Result()

        # Defensive: goal_callback already validated, but re-check for safety.
        if coords is None:
            goal_handle.abort()
            result.arrived = False
            result.message = f"Unknown location '{key}'."
            return result

        x, y, yaw = coords
        self.get_logger().info(
            f"Guiding to '{key}' at (x={x:.2f}, y={y:.2f}, yaw={yaw:.2f})."
        )

        if self.use_nav2 and self._nav2_client is not None:
            return self._execute_nav2(goal_handle, key, x, y, yaw, result)
        return self._execute_simulated(goal_handle, key, x, y, result)

    # ------------------------------------------------------------------ #
    # Simulated motion (no Gazebo / no Nav2) — CPU-only fallback.
    # ------------------------------------------------------------------ #
    def _execute_simulated(self, goal_handle, key, x, y, result):
        """Fake the trip with a timed countdown, streaming feedback."""
        total = max(1.0, self.sim_travel_time)
        # Straight-line distance from origin as a stand-in "remaining distance".
        start_dist = math.hypot(x, y) or 1.0
        steps = 6
        for i in range(steps):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.arrived = False
                result.message = f"Navigation to '{key}' cancelled."
                self.get_logger().info(result.message)
                return result

            frac_done = (i + 1) / steps
            remaining = start_dist * (1.0 - frac_done)
            fb = GoToLocation.Feedback()
            fb.distance_remaining = float(remaining)
            fb.status = f"[SIM] en route to {key} ({int(frac_done * 100)}%)"
            goal_handle.publish_feedback(fb)
            self.get_logger().info(fb.status)
            time.sleep(total / steps)

        goal_handle.succeed()
        result.arrived = True
        result.message = f"[SIM] Arrived at {key}."
        self.get_logger().info(result.message)
        return result

    # ------------------------------------------------------------------ #
    # Real Nav2 path: forward NavigateToPose and relay feedback.
    # ------------------------------------------------------------------ #
    def _execute_nav2(self, goal_handle, key, x, y, yaw, result):
        # Wait briefly for the Nav2 server; if absent, degrade to simulation so
        # the demo still completes (important on the no-GPU target).
        if not self._nav2_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().warn(
                "Nav2 /navigate_to_pose not available; falling back to SIM."
            )
            return self._execute_simulated(goal_handle, key, x, y, result)

        goal_msg = self._NavigateToPose.Goal()
        pose = goal_msg.pose
        pose.header.frame_id = self.goal_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        qz, qw = _yaw_to_quaternion(float(yaw))
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw

        # Relay Nav2 feedback -> our GoToLocation feedback.
        def _on_nav2_feedback(fb_msg):
            remaining = float(getattr(fb_msg.feedback, 'distance_remaining', 0.0))
            fb = GoToLocation.Feedback()
            fb.distance_remaining = remaining
            fb.status = f"en route to {key} ({remaining:.2f} m remaining)"
            goal_handle.publish_feedback(fb)

        # NOTE: this execute callback already runs inside the node's
        # MultiThreadedExecutor. We must NOT call rclpy.spin_until_future_complete
        # here (it would try to add the node to a second executor and fail).
        # Instead we poll ``future.done()`` and sleep — the executor's other
        # threads drive the callbacks that resolve these futures (safe because
        # the action server uses a ReentrantCallbackGroup).
        send_future = self._nav2_client.send_goal_async(
            goal_msg, feedback_callback=_on_nav2_feedback
        )
        while rclpy.ok() and not send_future.done():
            time.sleep(0.05)
        nav2_handle = send_future.result()

        if nav2_handle is None or not nav2_handle.accepted:
            goal_handle.abort()
            result.arrived = False
            result.message = f"Nav2 rejected the goal for '{key}'."
            self.get_logger().warn(result.message)
            return result

        # Wait for Nav2 to finish, honouring cancellation from our client.
        get_result_future = nav2_handle.get_result_async()
        while rclpy.ok() and not get_result_future.done():
            if goal_handle.is_cancel_requested:
                nav2_handle.cancel_goal_async()
                goal_handle.canceled()
                result.arrived = False
                result.message = f"Navigation to '{key}' cancelled."
                self.get_logger().info(result.message)
                return result
            time.sleep(0.1)

        goal_handle.succeed()
        result.arrived = True
        result.message = f"Arrived at {key}."
        self.get_logger().info(result.message)
        return result


def main(args=None):
    rclpy.init(args=args)
    node = NavigationNode()
    # Multi-threaded executor so the action server can spin nested Nav2 futures.
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
