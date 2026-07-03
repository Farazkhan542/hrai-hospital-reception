#!/usr/bin/env python3
"""Interaction node — social-signal perception + generation.

Report mapping: **Social signal perception** (parsing the visitor's typed
utterance into a name + requested doctor) and **Social signal generation**
(speaking the robot's response via ``tts.py``). It is the orchestrator: it calls
the reasoning node's ``VisitorRequest`` service, then, if a destination was
agreed, sends a ``GoToLocation`` action goal to the navigation node and narrates
the guidance.

Input modes (param ``input_mode``):
  * ``stdin``    (default) -- read typed lines from the terminal, interactively.
  * ``scripted``           -- replay a fixed list of utterances (the two demo
                              cases) with pauses, for the video / CI.

Intent parsing is deliberately rule-based (regex + matching against KB names) —
no NLP model, so it stays CPU-light and fully explainable in the report.
"""

from __future__ import annotations

import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from hospital_reception_interfaces.srv import VisitorRequest
from hospital_reception_interfaces.action import GoToLocation

from hospital_reception.knowledge_base import KnowledgeBase
from hospital_reception.intent_parser import parse_utterance
from hospital_reception import tts


# Default script for `input_mode:=scripted`. Mirrors scripts/run_demo.py:
#   1) EASY: returning visitor Mr. Ferrari asks for available Dr. Verdi.
#   2) HARD: someone asks for unavailable Dr. Bianchi -> negotiate Dr. Rossi.
DEFAULT_SCRIPT = [
    "Hello, I am Mr. Ferrari and I would like to see Dr. Verdi please.",
    "Hi, I need to see Dr. Bianchi in Cardiology.",
]


class InteractionNode(Node):
    """Front-end that perceives input and generates spoken responses."""

    def __init__(self):
        super().__init__('interaction_node')

        # -- parameters ---------------------------------------------------- #
        self.declare_parameter('input_mode', 'stdin')   # 'stdin' | 'scripted'
        self.declare_parameter('turn_pause', 2.0)       # pacing between turns (s)
        self.input_mode = self.get_parameter('input_mode').value
        self.turn_pause = float(self.get_parameter('turn_pause').value)

        # KB is used only for *perception* here (name/doctor matching); the
        # authoritative reasoning lives in the reasoning node.
        self.kb = KnowledgeBase()

        # -- clients ------------------------------------------------------- #
        self._req_client = self.create_client(VisitorRequest, 'visitor_request')
        self._nav_client = ActionClient(self, GoToLocation, 'goto_location')

        self.get_logger().info(
            f"Interaction node started (input_mode='{self.input_mode}')."
        )

    # ------------------------------------------------------------------ #
    # Perception: parse a raw utterance into (visitor_name, requested_doctor).
    # ------------------------------------------------------------------ #
    def parse_utterance(self, text: str):
        """Extract ``(visitor_name, requested_doctor)`` from free text.

        Thin wrapper over the ROS-free :func:`intent_parser.parse_utterance`
        (kept separate so it is unit-testable off-robot).
        """
        return parse_utterance(text, self.kb)

    # ------------------------------------------------------------------ #
    # One full turn: perceive -> reason (service) -> speak -> maybe guide.
    # ------------------------------------------------------------------ #
    def process_utterance(self, text: str) -> None:
        text = (text or '').strip()
        if not text:
            return

        print(f"\n[Visitor]: {text}", flush=True)
        visitor_name, requested_doctor = self.parse_utterance(text)
        self.get_logger().info(
            f"Perceived: visitor_name='{visitor_name}', "
            f"requested_doctor='{requested_doctor}'"
        )

        # -- call the reasoning service ------------------------------------
        if not self._req_client.wait_for_service(timeout_sec=5.0):
            tts.speak("Sorry, my reasoning system is not available right now.")
            return

        req = VisitorRequest.Request()
        req.visitor_name = visitor_name
        req.requested_doctor = requested_doctor
        req.free_text = text

        future = self._req_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
        if response is None:
            tts.speak("Sorry, I couldn't process that request.")
            return

        # -- generate: speak the robot's decided reply ---------------------
        tts.speak(response.speech)

        # -- if a destination was agreed, guide the visitor ----------------
        if response.resolved and response.goto_location:
            self.guide_to(response.goto_location)

    # ------------------------------------------------------------------ #
    # Send a GoToLocation goal and narrate feedback.
    # ------------------------------------------------------------------ #
    def guide_to(self, location_key: str) -> None:
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            tts.speak(
                "I know where to go, but my navigation system isn't ready, "
                "so I can't guide you right now."
            )
            return

        goal = GoToLocation.Goal()
        goal.location_key = location_key

        def _on_feedback(feedback_msg):
            fb = feedback_msg.feedback
            self.get_logger().info(
                f"[nav feedback] {fb.status} "
                f"({fb.distance_remaining:.2f} m remaining)"
            )

        send_future = self._nav_client.send_goal_async(
            goal, feedback_callback=_on_feedback
        )
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if goal_handle is None or not goal_handle.accepted:
            tts.speak(
                f"I'm sorry, I can't reach {location_key.replace('_', ' ')} "
                f"right now."
            )
            return

        tts.speak("Please follow me, we're on our way.")

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result if result_future.result() else None

        if result and result.arrived:
            pretty = location_key.replace('_', ' ')
            tts.speak(f"We've arrived at the {pretty}. Take care and get well soon!")
        else:
            msg = result.message if result else 'unknown error'
            tts.speak(f"I'm sorry, we couldn't complete the trip ({msg}).")

    # ------------------------------------------------------------------ #
    # Input loops.
    # ------------------------------------------------------------------ #
    def run_stdin(self) -> None:
        """Interactive loop: read typed utterances until EOF / 'quit'."""
        tts.speak(
            "Hello and welcome. Please type your request, for example: "
            "'I am Mr. Ferrari and I'd like to see Dr. Verdi'. Type 'quit' to exit."
        )
        while rclpy.ok():
            try:
                line = input("\n> ")
            except (EOFError, KeyboardInterrupt):
                break
            if line.strip().lower() in ('quit', 'exit', 'q'):
                break
            self.process_utterance(line)
        tts.speak("Goodbye!")

    def run_scripted(self, script=None) -> None:
        """Replay a fixed list of utterances with pauses (for the demo/video)."""
        script = script or DEFAULT_SCRIPT
        tts.speak("Starting scripted hospital-reception demonstration.")
        for i, utterance in enumerate(script, start=1):
            print(f"\n===== Scripted turn {i}/{len(script)} =====", flush=True)
            self.process_utterance(utterance)
            time.sleep(self.turn_pause)
        tts.speak("Demonstration complete. Thank you for watching.")


def main(args=None):
    rclpy.init(args=args)
    node = InteractionNode()
    try:
        if node.input_mode == 'scripted':
            node.run_scripted()
        else:
            node.run_stdin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
