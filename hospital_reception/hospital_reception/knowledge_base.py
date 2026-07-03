#!/usr/bin/env python3
"""Semantic memory for the HRAI TIAGo hospital-reception robot.

Report mapping: this file + ``data/*.json`` implement the **Memory / Knowledge
(semantic)** component of the course reference architecture. It is pure Python
(no ROS dependencies) so it is unit-testable and can be reasoned about in the
report. A ``__main__`` smoke test at the bottom confirms the data loads.

The three JSON files:
  * ``doctors.json``   -- doctors, departments, room location keys, availability
  * ``patients.json``  -- known visitors + light history (returning-visitor memory)
  * ``locations.json`` -- named locations -> (x, y, yaw) map poses for Nav2

Path resolution: at runtime inside ROS the files live in the package *share*
directory (installed by ``setup.py``); we resolve that via
``ament_index_python``. When run standalone (smoke test / off-robot), we fall
back to the ``data/`` folder next to the source tree. Both paths degrade
gracefully with clear errors.
"""

from __future__ import annotations

import json
import os
from typing import Optional, Tuple


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
def _find_data_dir() -> str:
    """Return the directory that holds the JSON knowledge-base files.

    Order of preference:
      1. Installed ROS share dir (``<prefix>/share/hospital_reception/data``).
      2. The ``data/`` folder relative to this source file (dev / smoke test).
    """
    # 1) Installed package share directory (only works inside a sourced ws).
    try:
        from ament_index_python.packages import get_package_share_directory
        share = get_package_share_directory('hospital_reception')
        candidate = os.path.join(share, 'data')
        if os.path.isdir(candidate):
            return candidate
    except Exception:
        # ament not available (running standalone) or package not installed.
        pass

    # 2) Source-tree fallback: .../hospital_reception/hospital_reception/kb.py
    #    -> parent of the module package holds the top-level ``data/`` folder.
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(os.path.dirname(here), 'data')
    return candidate


class KnowledgeBase:
    """Loads and queries the JSON semantic memory.

    All lookups are tolerant: partial / case-insensitive name matching, and
    missing data degrades to ``None`` / empty lists rather than raising, so the
    demo keeps running on a weak machine even if an entry is absent.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or _find_data_dir()
        self.doctors = self._load('doctors.json').get('doctors', [])
        self.patients = self._load('patients.json').get('patients', [])
        self.locations = self._load('locations.json').get('locations', {})

    # -- loading ----------------------------------------------------------- #
    def _load(self, filename: str) -> dict:
        path = os.path.join(self.data_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except FileNotFoundError:
            print(f"[KnowledgeBase] WARNING: missing data file: {path}")
            return {}
        except json.JSONDecodeError as exc:
            print(f"[KnowledgeBase] WARNING: bad JSON in {path}: {exc}")
            return {}

    # -- doctor queries ---------------------------------------------------- #
    def find_doctor(self, name_or_partial: str) -> Optional[dict]:
        """Return the first doctor whose name contains the query (case-insensitive).

        Accepts free text like "Dr. Bianchi", "bianchi", or "BIANCHI". Returns
        ``None`` if nothing matches (unknown doctor).
        """
        if not name_or_partial:
            return None
        needle = name_or_partial.strip().lower()
        # Strip a leading honorific so "bianchi" matches "Dr. Bianchi".
        needle = needle.replace('dr.', '').replace('dr ', '').strip()
        if not needle:
            return None
        for doc in self.doctors:
            if needle in doc.get('name', '').lower():
                return doc
        return None

    @staticmethod
    def doctor_available(doctor: Optional[dict]) -> bool:
        """True iff the doctor dict exists and is marked available."""
        return bool(doctor) and bool(doctor.get('available', False))

    def alternatives_for(self, doctor: Optional[dict]) -> list:
        """Available alternate doctors for negotiation.

        Priority: available doctors in the SAME department (excluding the
        requested one), then any other available doctor. This ordering is what
        lets the reasoning node offer "Dr. Rossi in Cardiology can see you now".
        """
        if not doctor:
            return [d for d in self.doctors if self.doctor_available(d)]

        dept = doctor.get('department')
        same_dept = [
            d for d in self.doctors
            if d.get('id') != doctor.get('id')
            and d.get('department') == dept
            and self.doctor_available(d)
        ]
        others = [
            d for d in self.doctors
            if d.get('id') != doctor.get('id')
            and d.get('department') != dept
            and self.doctor_available(d)
        ]
        return same_dept + others

    @staticmethod
    def location_for(doctor: Optional[dict]) -> str:
        """Location key of a doctor's room ("" if unknown)."""
        if not doctor:
            return ''
        return doctor.get('location', '')

    # -- patient queries --------------------------------------------------- #
    def recognise_patient(self, name: str) -> Optional[dict]:
        """Return a known patient by (partial, case-insensitive) name, else None."""
        if not name:
            return None
        needle = name.strip().lower()
        if not needle:
            return None
        for pat in self.patients:
            if needle in pat.get('name', '').lower():
                return pat
        return None

    def doctor_by_id(self, doctor_id: Optional[str]) -> Optional[dict]:
        """Resolve a doctor id (e.g. a patient's ``usual_doctor``) to its dict."""
        if not doctor_id:
            return None
        for doc in self.doctors:
            if doc.get('id') == doctor_id:
                return doc
        return None

    # -- location queries -------------------------------------------------- #
    def coords_for(self, location_key: str) -> Optional[Tuple[float, float, float]]:
        """Return (x, y, yaw) for a location key, or ``None`` if unknown."""
        loc = self.locations.get(location_key)
        if not loc:
            return None
        return (
            float(loc.get('x', 0.0)),
            float(loc.get('y', 0.0)),
            float(loc.get('yaw', 0.0)),
        )


# --------------------------------------------------------------------------- #
# Smoke test (run: python3 knowledge_base.py)
# --------------------------------------------------------------------------- #
def _smoke_test() -> int:
    kb = KnowledgeBase()
    print(f"[smoke] data_dir      = {kb.data_dir}")
    print(f"[smoke] doctors       = {len(kb.doctors)}")
    print(f"[smoke] patients      = {len(kb.patients)}")
    print(f"[smoke] locations     = {len(kb.locations)}")

    assert kb.doctors, "no doctors loaded"
    assert kb.patients, "no patients loaded"
    assert kb.locations, "no locations loaded"

    # Available doctor -> easy case.
    verdi = kb.find_doctor('Verdi')
    assert verdi is not None, "Dr. Verdi not found"
    assert kb.doctor_available(verdi), "Dr. Verdi should be available"
    print(f"[smoke] find_doctor('Verdi')        -> {verdi['name']} "
          f"(available={kb.doctor_available(verdi)})")

    # Unavailable doctor -> hard case; must have a same-dept alternate.
    bianchi = kb.find_doctor('bianchi')  # lower-case + no honorific
    assert bianchi is not None, "Dr. Bianchi not found"
    assert not kb.doctor_available(bianchi), "Dr. Bianchi should be unavailable"
    alts = kb.alternatives_for(bianchi)
    assert alts, "no alternatives for unavailable Dr. Bianchi"
    assert alts[0]['department'] == bianchi['department'], \
        "first alternate should be same-department"
    print(f"[smoke] alternatives_for('Bianchi') -> {[a['name'] for a in alts]}")

    # Patient recognition + usual-doctor resolution (memory).
    ferrari = kb.recognise_patient('Ferrari')
    assert ferrari is not None, "Mr. Ferrari not recognised"
    usual = kb.doctor_by_id(ferrari.get('usual_doctor'))
    print(f"[smoke] recognise_patient('Ferrari')-> {ferrari['name']}, "
          f"usual_doctor={usual['name'] if usual else None}, "
          f"needs={ferrari.get('needs')}")

    # Location resolution.
    coords = kb.coords_for('cardiology_room')
    assert coords is not None, "cardiology_room coords missing"
    print(f"[smoke] coords_for('cardiology_room')-> {coords}")

    # Unknown lookups degrade to None, not exceptions.
    assert kb.find_doctor('Nobody') is None
    assert kb.coords_for('nowhere') is None
    print("[smoke] unknown lookups return None (graceful)  OK")

    print("\n[smoke] ALL CHECKS PASSED")
    return 0


if __name__ == '__main__':
    raise SystemExit(_smoke_test())
