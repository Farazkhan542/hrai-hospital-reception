#!/usr/bin/env python3
"""Pure (ROS-free) intent parsing for the interaction node.

Report mapping: the perception half of **Social signal perception** — turning a
raw typed utterance into a structured intent (visitor name + requested doctor).
Kept in its own module with NO ROS dependency so it is unit-testable off-robot
and reusable. ``interaction_node`` delegates to :func:`parse_utterance`.

The approach is deliberately rule-based (regex + matching against known KB
names) — no NLP model, so it stays CPU-light and fully explainable.
"""

from __future__ import annotations

import re
from typing import Tuple


def parse_utterance(text: str, kb) -> Tuple[str, str]:
    """Extract ``(visitor_name, requested_doctor)`` from free text.

    Args:
        text: the raw visitor utterance.
        kb:   a ``KnowledgeBase`` (or anything exposing ``.patients`` and
              ``.doctors`` lists of dicts with a ``name`` field).

    Strategy (CPU-light, no NLP):
      * visitor name: try an explicit self-introduction ("I am X",
        "my name is X", ...), else match a known patient surname in the text.
      * requested doctor: match a known doctor surname, else a bare "Dr. Xxx".

    Case handling: the trigger phrases / honorifics are matched
    case-INSENSITIVELY via scoped ``(?i:...)`` groups, but the name token stays
    case-SENSITIVE so a real capitalised name is required. (A global
    ``re.IGNORECASE`` would make ``[A-Z]`` match lowercase too, so
    "I'm looking for..." would wrongly capture "looking" as the name.)
    """
    text = text or ''
    visitor_name = ''
    requested_doctor = ''

    # -- visitor name via explicit self-introduction ----------------------
    m = re.search(
        r"(?i:\b(?:i am|i'm|my name is|this is)\s+"
        r"((?:mr|mrs|ms|dr|miss)\.?\s+)?)"
        r"([A-Z][a-z]+)",
        text,
    )
    if m:
        honorific = (m.group(1) or '').strip()
        surname = m.group(2).strip()
        visitor_name = f"{honorific} {surname}".strip()

    # -- visitor name via known-patient match (memory) --------------------
    if not visitor_name:
        for pat in getattr(kb, 'patients', []):
            name = pat.get('name', '')
            surname = name.split()[-1] if name else ''
            if surname and re.search(rf"\b{re.escape(surname)}\b", text,
                                     flags=re.IGNORECASE):
                visitor_name = name
                break

    # -- requested doctor via known-doctor match --------------------------
    for doc in getattr(kb, 'doctors', []):
        name = doc.get('name', '')
        surname = name.split()[-1] if name else ''
        if surname and re.search(rf"\b{re.escape(surname)}\b", text,
                                 flags=re.IGNORECASE):
            requested_doctor = name
            break

    # -- fallback: bare "Dr. Xxx" (possibly an unknown doctor) ------------
    if not requested_doctor:
        m = re.search(r"(?i:\b(?:dr|doctor)\.?\s+)([A-Z][a-z]+)", text)
        if m:
            requested_doctor = f"Dr. {m.group(1).capitalize()}"

    return visitor_name, requested_doctor
