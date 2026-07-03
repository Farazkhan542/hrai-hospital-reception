# HRAI TIAGo Hospital Reception Robot

A **Human-Robot-AI Interaction** course project (Sapienza, Prof. Luca Iocchi).
TIAGo acts as a **hospital reception / guide robot**: it greets visitors,
consults a semantic knowledge base (doctors, patients, departments, locations),
performs **social reasoning** to negotiate when a requested doctor is
unavailable, and **guides** visitors to their destination by wrapping Nav2. It
demonstrates "social intelligence" through an easy case (available doctor →
confirm + guide) and a hard case (unavailable doctor → negotiate an alternative
→ guide). Interaction is **typed text in + TTS speech out** (no speech
recognition), which keeps it CPU-light and demo-friendly.

**Target machine:** Windows + WSL2, **no NVIDIA GPU** → CPU / software rendering
(`llvmpipe`). Everything here is kept lightweight; Nav2 is the heaviest allowed
component and can be swapped for a simulated-motion fallback (`use_nav2:=false`).

---

## Packages

This project ships **two** ROS2 packages (drop both into the course `exchange/`):

| Package                            | Build type   | Contents                                   |
|------------------------------------|--------------|--------------------------------------------|
| `hospital_reception_interfaces`    | ament_cmake  | `VisitorRequest.srv`, `GoToLocation.action`|
| `hospital_reception`               | ament_python | nodes, knowledge base, world, configs, launch |

The interfaces live in a **separate ament_cmake package** because ament_python
packages cannot generate `rosidl` interfaces themselves.

---

## Architecture

```
                 ┌────────────────────┐
   visitor text  │  Interaction Node  │  TTS out (speech)
  ───────────────▶  (perception + gen) ├──────────────▶ [speaker / stdout log]
                 └─────────┬──────────┘
                           │ /visitor_request (srv)
                           ▼
                 ┌────────────────────┐      ┌──────────────────┐
                 │  Social Reasoning  │◀────▶│  Knowledge Base  │  (JSON: patients,
                 │       Node         │      │   (semantic mem) │   doctors, depts,
                 └─────────┬──────────┘      └──────────────────┘   locations)
                           │ /goto_location (action)
                           ▼
                 ┌────────────────────┐
                 │  Navigation Node   │  wraps Nav2 (path planning + obstacle avoid)
                 │   (Nav2 client)    │
                 └─────────┬──────────┘
                           ▼
                    TIAGo in Gazebo
```

**Component → code mapping** (keep intact for the report):

| Architecture component        | Node / file                          |
|-------------------------------|--------------------------------------|
| Social signal perception      | `interaction_node.py` (input parsing)|
| Social reasoning              | `reasoning_node.py`                  |
| Social signal generation      | `interaction_node.py` + `tts.py`     |
| Memory / Knowledge (semantic) | `knowledge_base.py` + `data/*.json`  |
| Robot primitives              | `navigation_node.py` (Nav2 wrapper)  |
| Surrounding model             | the SLAM map + `worlds/hospital.world` |

---

## 1. Prerequisites

- The course Docker stack running (ROS2 Humble + Gazebo + TIAGo + Nav2 +
  slam_toolbox), started via `./start_tiago_cpu.sh` (CPU / no-GPU target).
- TIAGo launchable in Gazebo the usual way (`sim.launch.py` / `nav.launch.py`).
- Optional: `pyttsx3` for audible speech (`pip install pyttsx3`). If missing,
  the robot's lines are printed instead — the demo still works.

Both packages go inside the mounted `exchange/` folder (i.e.
`exchange/hospital_reception/` and `exchange/hospital_reception_interfaces/`).

## 2. Build

From the workspace root inside the container (the `exchange` folder is the
workspace `src` in the course setup):

```bash
# interfaces FIRST (the python package depends on the generated messages)
colcon build --packages-select hospital_reception_interfaces
source install/setup.bash
colcon build --packages-select hospital_reception
source install/setup.bash
```

Or build both at once: `colcon build --packages-up-to hospital_reception`.

**One-shot build + test:** from the workspace root, the convenience script does
steps in the right order (interfaces → package → source → pytest) and stops on
the first failure with a clear `[PASS]`/`[FAIL]` marker:

```bash
bash <path-to>/hospital_reception/scripts/build_and_test.sh
```

**Sanity check** the knowledge base loads (pure Python, no ROS needed):

```bash
python3 src/hospital_reception/hospital_reception/knowledge_base.py
# expect: "[smoke] ALL CHECKS PASSED"
```

## 3. Mapping (do this once)

The navigation node needs a map + tuned coordinates. Build the map of our world:

```bash
# 1) Launch the course sim with OUR world (see note below about world placement)
ros2 launch simulation sim.launch.py world_name:=hospital

# 2) In a new terminal, start SLAM with our params
ros2 run slam_toolbox async_slam_toolbox_node \
  --ros-args --params-file \
  install/hospital_reception/share/hospital_reception/config/slam_params.yaml

# 3) In a new terminal, drive TIAGo around to cover the map
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# 4) Save the map into our package's maps/ folder
ros2 run nav2_map_server map_saver_cli -f \
  src/hospital_reception/maps/hospital_map
```

> **World placement:** if the course `sim.launch.py` only looks for worlds in
> `exchange/simulation/worlds/`, copy our world there:
> `cp src/hospital_reception/worlds/hospital.world exchange/simulation/worlds/`.
> Otherwise launch Gazebo with our world directly. Either way the world is a
> plain SDF like the provided `house.world`.

**Then tune coordinates:** open the saved map in RViz, read off the real poses of
each room, and update `data/locations.json` so navigation goals land correctly.
The shipped coordinates are placeholders matched to the world geometry.

## 4. Run (full — with Nav2)

```bash
# Terminal A: course navigation stack with our map + world
ros2 launch simulation nav.launch.py world_name:=hospital
#   (ensure Nav2's map_server points at maps/hospital_map.yaml; our
#    config/nav2_params.yaml is provided as a CPU-tuned reference)

# Terminal B: our three nodes
ros2 launch hospital_reception reception.launch.py
# then type at the prompt, e.g.:
#   I am Mr. Ferrari and I'd like to see Dr. Verdi
```

## 5. Run (lightweight — no Nav2, for a weak CPU)

Skip Gazebo/Nav2 entirely and use the simulated-motion fallback. The dialogue +
social reasoning still run end-to-end:

```bash
ros2 launch hospital_reception reception.launch.py use_nav2:=false
# interactive typing, motion is simulated with a timed countdown
```

## 6. Demo (scripted, for the video)

Plays both interactions automatically with pacing (defaults to `use_nav2:=false`
so it runs anywhere):

```bash
ros2 launch hospital_reception demo.launch.py
# or force real navigation:
ros2 launch hospital_reception demo.launch.py use_nav2:=true
```

See `scripts/record_hints.md` for how to capture the ~3-minute video.

---

## Interfaces

**`VisitorRequest.srv`** — interaction ↔ reasoning
```
string visitor_name        # may be empty if unknown
string requested_doctor    # free text, e.g. "Dr. Bianchi"
string free_text           # raw utterance, for logging
---
string speech              # what the robot should say (spoken via TTS)
string goto_location       # location key to navigate to ("" = none)
bool   resolved            # true if a destination was agreed
```

**`GoToLocation.action`** — interaction → navigation
```
string location_key
---
bool arrived
string message
---
float32 distance_remaining
string status
```

## Knowledge base (`data/`)

- `doctors.json` — doctors, department, room location key, availability. Includes
  available + unavailable + same-department alternates (drives the hard case).
- `patients.json` — known visitors + history (returning-visitor "memory").
- `locations.json` — named locations → (x, y, yaw). **Tune after mapping.**

## The two graded interactions

- **Easy:** returning "Mr. Ferrari" asks for available "Dr. Verdi" (Neurology) →
  personalised greeting → confirm → guide to `neurology_room`.
- **Hard:** someone asks for "Dr. Bianchi" (Cardiology, **unavailable**) → robot
  negotiates → offers "Dr. Rossi" (available, same dept) → visitor accepts →
  guide to `cardiology_room`.

## CPU-friendliness summary

- Primitive-only Gazebo world (no meshes/textures), shadows off.
- `use_nav2:=false` fallback removes the entire Nav2 stack when needed.
- Nav2 params tuned down (low speed, small costmaps, fewer samples/particles) —
  see `config/nav2_params.yaml` (every change is commented with `# CPU:`).
- Rule-based intent parsing + reasoning (no NLP/ML models).
- TTS is offline (`pyttsx3`) and optional; lines always print.
