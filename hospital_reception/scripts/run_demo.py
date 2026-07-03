#!/usr/bin/env python3
"""Scripted demo driver for the ~3-minute video.

This is a self-contained ROS2 node (service client + action client + TTS) that
plays the two graded interactions end-to-end. It does not require
``interaction_node`` — it talks to the reasoning and navigation nodes directly,
so ``demo.launch.py`` can trigger just this driver.

  1. EASY case:  returning visitor "Mr. Ferrari" asks for the AVAILABLE
                 "Dr. Verdi" (Neurology). The robot recognises him, confirms,
                 and guides to neurology_room.
  2. HARD case:  a visitor asks for "Dr. Bianchi" (Cardiology, UNAVAILABLE). The
                 robot negotiates, offers the available same-department
                 "Dr. Rossi", the visitor accepts, and the robot guides to
                 cardiology_room.

Every robot line is spoken (TTS) and printed so it is legible on the video, with
short pauses between turns for pacing.
"""

from __future__ import annotations

import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from hospital_reception_interfaces.srv import VisitorRequest
from hospital_reception_interfaces.action import GoToLocation

from hospital_reception import tts


# Each demo turn is a pre-parsed (visitor_name, requested_doctor, raw_text) tuple
# plus a follow-up line to speak when the visitor "accepts" an offered alternate.
DEMO_TURNS = [
    {
        'title': 'EASY CASE — available doctor',
        'visitor_name': 'Mr. Ferrari',
        'requested_doctor': 'Dr. Verdi',
        'free_text': "Hello, I'm Mr. Ferrari and I'd like to see Dr. Verdi.",
        'accept_line': None,
    },
    {
        'title': 'HARD CASE — unavailable doctor, negotiate alternate',
        'visitor_name': '',
        'requested_doctor': 'Dr. Bianchi',
        'free_text': "Hi, I need to see Dr. Bianchi in Cardiology.",
        # After the robot offers an alternate, the visitor accepts:
        'accept_line': "Yes, that works for me — please take me to the alternate.",
    },
]

TURN_PAUSE = 2.5   # seconds between turns for legible pacing


class DemoDriver(Node):
    def __init__(self):
        super().__init__('run_demo')
        self._req_client = self.create_client(VisitorRequest, 'visitor_request')
        self._nav_client = ActionClient(self, GoToLocation, 'goto_location')

    # -- one reasoning round-trip ------------------------------------------ #
    def ask(self, visitor_name, requested_doctor, free_text):
        if not self._req_client.wait_for_service(timeout_sec=10.0):
            tts.speak("Reasoning service is not available.")
            return None
        req = VisitorRequest.Request()
        req.visitor_name = visitor_name
        req.requested_doctor = requested_doctor
        req.free_text = free_text
        future = self._req_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    # -- guide via the navigation action ----------------------------------- #
    def guide(self, location_key):
        if not self._nav_client.wait_for_server(timeout_sec=10.0):
            tts.speak("Navigation server is not available.")
            return
        goal = GoToLocation.Goal()
        goal.location_key = location_key

        def _fb(msg):
            self.get_logger().info(
                f"[nav] {msg.feedback.status} "
                f"({msg.feedback.distance_remaining:.2f} m)"
            )

        send_future = self._nav_client.send_goal_async(goal, feedback_callback=_fb)
        rclpy.spin_until_future_complete(self, send_future)
        handle = send_future.result()
        if handle is None or not handle.accepted:
            tts.speak(f"I can't reach {location_key.replace('_', ' ')} right now.")
            return
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        res = result_future.result().result if result_future.result() else None
        if res and res.arrived:
            tts.speak(f"We've arrived at the {location_key.replace('_', ' ')}. "
                      f"Take care!")
        else:
            tts.speak("I'm sorry, we couldn't complete the trip.")

    # -- play the whole script --------------------------------------------- #
    def run(self):
        tts.speak("Starting the hospital reception demonstration.")
        time.sleep(TURN_PAUSE)

        for turn in DEMO_TURNS:
            print(f"\n========== {turn['title']} ==========", flush=True)
            print(f"[Visitor]: {turn['free_text']}", flush=True)

            resp = self.ask(turn['visitor_name'], turn['requested_doctor'],
                            turn['free_text'])
            if resp is None:
                continue
            tts.speak(resp.speech)
            time.sleep(TURN_PAUSE)

            # In the hard case the robot offered an alternate; the visitor accepts.
            if turn['accept_line'] and resp.resolved:
                print(f"[Visitor]: {turn['accept_line']}", flush=True)
                tts.speak("Great, thank you. Let's go.")
                time.sleep(1.0)

            if resp.resolved and resp.goto_location:
                self.guide(resp.goto_location)

            time.sleep(TURN_PAUSE)

        tts.speak("That concludes the demonstration. Thank you for watching.")


def main(args=None):
    rclpy.init(args=args)
    node = DemoDriver()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
