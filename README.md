# HRAI TIAGo Hospital-Reception Robot

A Human-Robot-AI Interaction (HRAI) course project (Sapienza) — a **hospital
reception / guide robot** on the TIAGo platform (ROS 2 Humble + Gazebo + Nav2).
A visitor asks for a doctor; the robot recognises returning visitors, and if the
doctor is unavailable it **negotiates an alternative** (an available colleague in
the same department) instead of refusing, then guides the visitor to the room.

CPU-only / no-GPU friendly (Windows + WSL2, software rendering).

## Packages

| Package | Build type | Contents |
|---|---|---|
| [`hospital_reception`](hospital_reception/) | ament_python | nodes, knowledge base, world, configs, launch, tests |
| [`hospital_reception_interfaces`](hospital_reception_interfaces/) | ament_cmake | `VisitorRequest.srv`, `GoToLocation.action` |

## Quick start (inside the ROS 2 container)

```bash
colcon build --packages-up-to hospital_reception
source install/setup.bash
# guaranteed offline demo (no Gazebo/Nav2/GPU needed):
ros2 launch hospital_reception demo.launch.py use_nav2:=false
```

See [`hospital_reception/README.md`](hospital_reception/README.md) for full build,
mapping, run and demo instructions, and [`hospital_reception/REPORT.md`](hospital_reception/REPORT.md)
for the project report.
