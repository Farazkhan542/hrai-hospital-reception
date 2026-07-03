#!/usr/bin/env python3
"""Social reasoning node — the graded "social intelligence" of the robot.

Report mapping: **Social reasoning**. This node is a ROS2 *service server* for
``VisitorRequest``. It consults the semantic memory (``KnowledgeBase``) and
decides what the robot should say and where (if anywhere) to guide the visitor.

Two contrasting behaviours (the demo's easy vs. hard case):

  EASY  -- requested doctor is AVAILABLE  -> confirm + guide  (``handle_available``)
  HARD  -- requested doctor is UNAVAILABLE -> do NOT just refuse; negotiate an
           alternative (same-department available doctor, or the later slot),
           taking the visitor's needs into account          (``handle_unavailable``)

Returning visitors are personalised (``personalise``) using the patient history
in the knowledge base = the "memory" component of the reference architecture.

The dialogue policy is intentionally small and rule-based (no NLP model) so it
is CPU-light and fully explainable in the report.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node

from hospital_reception_interfaces.srv import VisitorRequest

from hospital_reception.knowledge_base import KnowledgeBase


class ReasoningNode(Node):
    """Service server implementing the hospital-reception dialogue policy."""

    def __init__(self):
        super().__init__('reasoning_node')

        # Load semantic memory once at startup.
        self.kb = KnowledgeBase()
        self.get_logger().info(
            f"Knowledge base loaded: {len(self.kb.doctors)} doctors, "
            f"{len(self.kb.patients)} patients, {len(self.kb.locations)} locations."
        )

        # The single service that the interaction node calls per utterance.
        self._srv = self.create_service(
            VisitorRequest, 'visitor_request', self.handle_request
        )
        self.get_logger().info("Reasoning node ready on service /visitor_request.")

    # ------------------------------------------------------------------ #
    # Service callback: dispatches to the easy / hard case handlers.
    # ------------------------------------------------------------------ #
    def handle_request(self, request, response):
        visitor_name = (request.visitor_name or '').strip()
        requested = (request.requested_doctor or '').strip()
        self.get_logger().info(
            f"Request: visitor='{visitor_name}' doctor='{requested}' "
            f"raw='{request.free_text}'"
        )

        patient = self.kb.recognise_patient(visitor_name) if visitor_name else None
        greeting = self.personalise(patient)

        # No doctor named at all -> ask for clarification (graceful, still helpful).
        if not requested:
            response.speech = (
                f"{greeting} Which doctor would you like to see today?"
            )
            response.goto_location = ''
            response.resolved = False
            return response

        doctor = self.kb.find_doctor(requested)

        # Unknown doctor -> we don't have them; offer any available doctor.
        if doctor is None:
            alts = self.kb.alternatives_for(None)
            if alts:
                alt = alts[0]
                response.speech = (
                    f"{greeting} I'm sorry, I couldn't find a doctor matching "
                    f"'{requested}'. {alt['name']} in {alt['department']} is "
                    f"available now — shall I take you there?"
                )
                response.goto_location = self.kb.location_for(alt)
                response.resolved = True
            else:
                response.speech = (
                    f"{greeting} I'm sorry, I couldn't find that doctor and none "
                    f"are available right now. Please check with the front desk."
                )
                response.goto_location = ''
                response.resolved = False
            return response

        # Known doctor -> branch on availability.
        if self.kb.doctor_available(doctor):
            self.handle_available(doctor, patient, greeting, response)
        else:
            self.handle_unavailable(doctor, patient, greeting, response)
        return response

    # ------------------------------------------------------------------ #
    # Personalisation (memory): recognise returning visitors.
    # ------------------------------------------------------------------ #
    def personalise(self, patient) -> str:
        """Return an opening greeting, personalised if the visitor is known."""
        if not patient:
            return "Welcome to the hospital reception."
        name = patient.get('name', 'there')
        # Recall the usual doctor if we have one on file.
        usual = self.kb.doctor_by_id(patient.get('usual_doctor'))
        if usual:
            return (
                f"Welcome back, {name}! Good to see you again. "
                f"Last time you saw {usual['name']}."
            )
        return f"Welcome back, {name}! Good to see you again."

    # ------------------------------------------------------------------ #
    # EASY CASE: requested doctor is available.
    # ------------------------------------------------------------------ #
    def handle_available(self, doctor, patient, greeting, response):
        """Confirm the appointment and set the navigation goal."""
        needs_note = self._needs_note(patient)
        response.speech = (
            f"{greeting} {doctor['name']} in {doctor['department']} is available "
            f"now.{needs_note} I'll guide you there — please follow me."
        )
        response.goto_location = self.kb.location_for(doctor)
        response.resolved = True
        self.get_logger().info(
            f"[EASY] Available -> guiding to '{response.goto_location}'."
        )

    # ------------------------------------------------------------------ #
    # HARD CASE: requested doctor is unavailable -> negotiate.
    # ------------------------------------------------------------------ #
    def handle_unavailable(self, doctor, patient, greeting, response):
        """Negotiate an alternative rather than simply refusing.

        Policy:
          1. Prefer an AVAILABLE doctor in the SAME department and offer to guide
             there now (the socially intelligent move).
          2. If none, offer the requested doctor's later slot as a fallback.
        For the scripted demo the visitor accepts the alternate, so we already
        set ``goto_location`` to the alternate's room and ``resolved=true``.
        """
        needs_note = self._needs_note(patient)
        busy_until = doctor.get('next_slot', 'later')
        alternates = self.kb.alternatives_for(doctor)
        same_dept = [a for a in alternates
                     if a.get('department') == doctor.get('department')]

        if same_dept:
            alt = same_dept[0]
            response.speech = (
                f"{greeting} {doctor['name']} is busy until {busy_until}, but "
                f"{alt['name']}, also in {doctor['department']}, can see you now."
                f"{needs_note} Shall I take you to {alt['name']} instead? "
                f"I'll guide you there."
            )
            response.goto_location = self.kb.location_for(alt)
            response.resolved = True
            self.get_logger().info(
                f"[HARD] Unavailable -> same-dept alternate {alt['name']} "
                f"at '{response.goto_location}'."
            )
            return

        # No same-department alternate: offer any other available doctor, else
        # fall back to the requested doctor's later slot.
        if alternates:
            alt = alternates[0]
            response.speech = (
                f"{greeting} {doctor['name']} is busy until {busy_until}, and no "
                f"one else is free in {doctor['department']} right now. However "
                f"{alt['name']} in {alt['department']} is available."
                f"{needs_note} Would you like me to take you there?"
            )
            response.goto_location = self.kb.location_for(alt)
            response.resolved = True
            self.get_logger().info(
                f"[HARD] Unavailable -> cross-dept alternate {alt['name']}."
            )
            return

        # Nobody available anywhere -> offer to wait for the requested doctor.
        response.speech = (
            f"{greeting} I'm afraid {doctor['name']} is busy until {busy_until} "
            f"and no other doctor is free at the moment. You're welcome to wait "
            f"in the waiting area — shall I take you there?"
        )
        response.goto_location = 'waiting_area'
        response.resolved = True
        self.get_logger().info("[HARD] Nobody available -> offer waiting_area.")

    # ------------------------------------------------------------------ #
    # Helper: fold the visitor's accessibility needs into the phrasing.
    # ------------------------------------------------------------------ #
    @staticmethod
    def _needs_note(patient) -> str:
        """Return a short clause acknowledging special needs, or ''."""
        if not patient:
            return ''
        needs = patient.get('needs')
        if not needs:
            return ''
        return f" I'll make sure the route is suitable for {needs}."


def main(args=None):
    rclpy.init(args=args)
    node = ReasoningNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        # Guard shutdown so a double Ctrl-C doesn't raise.
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
