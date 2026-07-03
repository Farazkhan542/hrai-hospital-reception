#!/usr/bin/env python3
"""Unit tests for the semantic memory (KnowledgeBase).

Pure Python, no ROS required:  run with ``pytest`` from the package root, or
``colcon test``. Exercises doctor/patient/location lookups and, importantly, the
easy-case (available) vs. hard-case (unavailable -> same-dept alternate)
decisions that drive the graded social reasoning.
"""

import pytest

from hospital_reception.knowledge_base import KnowledgeBase


@pytest.fixture(scope='module')
def kb():
    return KnowledgeBase()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_data_loads(kb):
    assert kb.doctors, "no doctors loaded"
    assert kb.patients, "no patients loaded"
    assert kb.locations, "no locations loaded"


# --------------------------------------------------------------------------- #
# Doctor lookup (case / honorific tolerant)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize('query,expected', [
    ('Dr. Verdi', 'Dr. Verdi'),
    ('verdi', 'Dr. Verdi'),         # lower-case, no honorific
    ('BIANCHI', 'Dr. Bianchi'),     # upper-case
    ('Dr Rossi', 'Dr. Rossi'),      # honorific without the dot
])
def test_find_doctor_tolerant(kb, query, expected):
    doc = kb.find_doctor(query)
    assert doc is not None
    assert doc['name'] == expected


def test_find_doctor_unknown_returns_none(kb):
    assert kb.find_doctor('Nobody') is None
    assert kb.find_doctor('') is None


# --------------------------------------------------------------------------- #
# Availability + the easy/hard branch inputs
# --------------------------------------------------------------------------- #
def test_available_doctor_is_available(kb):
    assert kb.doctor_available(kb.find_doctor('Verdi')) is True


def test_unavailable_doctor_is_not_available(kb):
    assert kb.doctor_available(kb.find_doctor('Bianchi')) is False


def test_doctor_available_handles_none(kb):
    assert kb.doctor_available(None) is False


def test_alternatives_prefer_same_department(kb):
    """HARD case core: an unavailable doctor must yield an available same-dept
    alternate as the FIRST option so the robot can negotiate within-department."""
    bianchi = kb.find_doctor('Bianchi')          # Cardiology, unavailable
    alts = kb.alternatives_for(bianchi)
    assert alts, "expected at least one alternative"
    assert alts[0]['department'] == bianchi['department']
    assert alts[0]['name'] == 'Dr. Rossi'        # the available cardiologist
    assert kb.doctor_available(alts[0]) is True
    # The unavailable doctor must never be offered as their own alternate.
    assert all(a['id'] != bianchi['id'] for a in alts)


def test_alternatives_all_available(kb):
    for doc in kb.doctors:
        for alt in kb.alternatives_for(doc):
            assert kb.doctor_available(alt) is True


# --------------------------------------------------------------------------- #
# Location resolution
# --------------------------------------------------------------------------- #
def test_location_for_doctor(kb):
    assert kb.location_for(kb.find_doctor('Verdi')) == 'neurology_room'
    assert kb.location_for(None) == ''


def test_coords_for_known_and_unknown(kb):
    coords = kb.coords_for('cardiology_room')
    assert coords == (3.0, 1.5, 0.0)
    assert kb.coords_for('nowhere') is None


# --------------------------------------------------------------------------- #
# Patient recognition (memory)
# --------------------------------------------------------------------------- #
def test_recognise_returning_patient(kb):
    ferrari = kb.recognise_patient('Ferrari')
    assert ferrari is not None
    assert ferrari['name'] == 'Mr. Ferrari'
    assert ferrari['needs'] == 'wheelchair access'


def test_recognise_unknown_patient(kb):
    assert kb.recognise_patient('Anonymous') is None
    assert kb.recognise_patient('') is None


def test_usual_doctor_resolves(kb):
    ferrari = kb.recognise_patient('Ferrari')
    usual = kb.doctor_by_id(ferrari['usual_doctor'])
    assert usual is not None
    assert usual['name'] == 'Dr. Bianchi'


def test_doctor_by_id_unknown(kb):
    assert kb.doctor_by_id(None) is None
    assert kb.doctor_by_id('does_not_exist') is None
