#!/usr/bin/env bash
#
# build_and_test.sh — build + smoke-test the HRAI hospital_reception packages
# in the correct order, inside the TIAGo ROS2 Humble container.
#
# Run it from your colcon WORKSPACE ROOT (the directory from which `colcon build`
# can see the two packages), e.g.:
#
#     bash <path-to>/hospital_reception/scripts/build_and_test.sh
#
# It performs, stopping on the FIRST failure with a clear message:
#   1. colcon build  hospital_reception_interfaces   (must be first)
#   2. colcon build  hospital_reception
#   3. source install/setup.bash
#   4. run the pytest suite (knowledge base, intent parser, LLM fallback)
#
# NB: we do NOT use `set -u` — ROS's own setup.bash references unset variables,
# which would abort under `set -u`. Instead every step's exit code is checked
# explicitly below.

set -o pipefail

# ----------------------------------------------------------------------------
# Pretty PASS/FAIL markers
# ----------------------------------------------------------------------------
step() {
    echo
    echo "=================================================================="
    echo ">>> $*"
    echo "=================================================================="
}
pass() { echo "[PASS] $*"; }
fail() {
    echo
    echo "##################################################################"
    echo "[FAIL] $*"
    echo "Aborting: fix the error above and re-run this script."
    echo "##################################################################"
    exit 1
}

# ----------------------------------------------------------------------------
# 0. Make sure colcon (and ROS) are available.
# ----------------------------------------------------------------------------
if ! command -v colcon >/dev/null 2>&1; then
    # Try to source the ROS underlay, then re-check.
    if [ -f /opt/ros/humble/setup.bash ]; then
        # shellcheck disable=SC1091
        source /opt/ros/humble/setup.bash
    fi
fi
command -v colcon >/dev/null 2>&1 \
    || fail "colcon not found. Source /opt/ros/humble/setup.bash first, then re-run."

if ! python3 -c "import pytest" >/dev/null 2>&1; then
    fail "pytest is not installed. Try: pip install pytest  (or: apt install python3-pytest)"
fi

# ----------------------------------------------------------------------------
# 1. Build the interfaces package FIRST.
#    The python package imports the generated messages, so this must exist and
#    be on the path before step 2.
# ----------------------------------------------------------------------------
step "STEP 1/4  colcon build  hospital_reception_interfaces"
if colcon build --packages-select hospital_reception_interfaces; then
    pass "interfaces built"
else
    fail "interfaces build failed"
fi

# The generated messages must be discoverable before building the python pkg.
# shellcheck disable=SC1091
source install/setup.bash \
    || fail "could not source install/setup.bash after the interfaces build"

# ----------------------------------------------------------------------------
# 2. Build the python package.
# ----------------------------------------------------------------------------
step "STEP 2/4  colcon build  hospital_reception"
if colcon build --packages-select hospital_reception; then
    pass "hospital_reception built"
else
    fail "hospital_reception build failed"
fi

# ----------------------------------------------------------------------------
# 3. Source the overlay so the generated msgs + installed data/ are found.
# ----------------------------------------------------------------------------
step "STEP 3/4  source install/setup.bash"
# shellcheck disable=SC1091
if source install/setup.bash; then
    pass "workspace overlay sourced"
else
    fail "could not source install/setup.bash"
fi

# ----------------------------------------------------------------------------
# 4. Run the pytest suite (pure-Python: no Gazebo / Nav2 needed).
#    We locate the source test/ dir (excluding build/ and install/ copies) and
#    run pytest directly, so we exercise ONLY our unit tests — not the optional
#    ament lint tests, which would add noise.
# ----------------------------------------------------------------------------
step "STEP 4/4  pytest suite"
TEST_DIR=$(find . -type d -path '*/hospital_reception/test' \
    -not -path '*/build/*' -not -path '*/install/*' 2>/dev/null | head -n 1)
[ -n "$TEST_DIR" ] \
    || fail "could not locate the hospital_reception/test directory from $(pwd)"
echo "Running tests in: $TEST_DIR"
if python3 -m pytest "$TEST_DIR" -q; then
    pass "all tests passed"
else
    fail "pytest reported failures (see output above)"
fi

# ----------------------------------------------------------------------------
# Done.
# ----------------------------------------------------------------------------
echo
echo "=================================================================="
echo "[ALL PASS]  build + tests succeeded. You're ready to launch:"
echo "  ros2 launch hospital_reception demo.launch.py            # offline demo"
echo "  ros2 launch hospital_reception reception.launch.py       # interactive"
echo "=================================================================="
