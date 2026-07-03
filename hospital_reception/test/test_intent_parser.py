#!/usr/bin/env python3
"""Unit tests for the ROS-free intent parser (perception).

Confirms that visitor names and requested doctors are extracted correctly from
free text, including the tricky case-sensitivity edge cases that a naive
``re.IGNORECASE`` regex gets wrong.
"""

import pytest

from hospital_reception.knowledge_base import KnowledgeBase
from hospital_reception.intent_parser import parse_utterance


@pytest.fixture(scope='module')
def kb():
    return KnowledgeBase()


# --------------------------------------------------------------------------- #
# The two demo utterances
# --------------------------------------------------------------------------- #
def test_easy_case_utterance(kb):
    name, doctor = parse_utterance(
        "Hello, I am Mr. Ferrari and I would like to see Dr. Verdi please.", kb)
    assert name == 'Mr. Ferrari'      # exact match -> feeds patient recognition
    assert doctor == 'Dr. Verdi'


def test_hard_case_utterance(kb):
    name, doctor = parse_utterance(
        "Hi, I need to see Dr. Bianchi in Cardiology.", kb)
    assert name == ''                 # no self-introduction
    assert doctor == 'Dr. Bianchi'


# --------------------------------------------------------------------------- #
# Name recognition paths
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize('text,expected_name', [
    ("I am Mr. Ferrari.", 'Mr. Ferrari'),
    ("my name is Costa", 'Costa'),
    ("this is Mrs. Romano speaking", 'Mrs. Romano'),
    ("Ferrari here to see someone.", 'Mr. Ferrari'),  # KB surname fallback
])
def test_visitor_name_extraction(kb, text, expected_name):
    name, _ = parse_utterance(text, kb)
    assert name == expected_name


def test_no_false_name_from_im_looking(kb):
    """Regression: 'I'm looking for...' must NOT capture 'looking' as a name.

    A global re.IGNORECASE makes [A-Z] match lowercase, which is exactly the bug
    this guards against.
    """
    name, doctor = parse_utterance("I'm looking for Dr. Nobody.", kb)
    assert name == ''
    assert doctor == 'Dr. Nobody'


# --------------------------------------------------------------------------- #
# Doctor extraction paths
# --------------------------------------------------------------------------- #
def test_known_doctor_surname_only(kb):
    _, doctor = parse_utterance("Can I see Rossi?", kb)
    assert doctor == 'Dr. Rossi'


def test_unknown_doctor_via_bare_pattern(kb):
    _, doctor = parse_utterance("I need Dr. Nobody urgently.", kb)
    assert doctor == 'Dr. Nobody'


def test_no_false_doctor_from_generic_word(kb):
    """'see the doctor now' must not capture 'now' as a doctor name."""
    _, doctor = parse_utterance("I want to see the doctor now.", kb)
    assert doctor == ''


def test_empty_and_none_input(kb):
    assert parse_utterance('', kb) == ('', '')
    assert parse_utterance(None, kb) == ('', '')


# --------------------------------------------------------------------------- #
# Parser works against a lightweight fake KB (no coupling to real data)
# --------------------------------------------------------------------------- #
class _FakeKB:
    patients = [{'name': 'Mr. Smith'}]
    doctors = [{'name': 'Dr. Jones'}]


def test_parser_uses_injected_kb():
    kb = _FakeKB()
    name, doctor = parse_utterance("Smith wants Dr. Jones", kb)
    assert name == 'Mr. Smith'
    assert doctor == 'Dr. Jones'
