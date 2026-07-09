# A Hospital-Reception Guide Robot with Social-Reasoning Intelligence

**Human-Robot-AI Interaction (HRAI) — Elective in Artificial Intelligence (AI & Robotics)**
Sapienza University of Rome · Prof. Luca Iocchi, Vincenzo Suriani · A.Y. 2025–26

**Project by:**
_[FILL IN: Student 1 — Full Name, matricola]_
_[FILL IN: Student 2 — Full Name, matricola]_

**Platform:** PAL Robotics TIAGo (simulated, Gazebo) · ROS 2 Humble
**Deliverables:** this report · ~3-min video · code ZIP (`hospital_reception`, `hospital_reception_interfaces`)

> **Note to authors.** This report is structured to match the course *Project
> guidelines* (Introduction · Related Work · Design · Solution · Implementation ·
> Results · Experimental Evaluation · Conclusions). Passages marked
> **_[FILL IN: …]_** need a value only your live run supplies (names, screenshots,
> the SLAM map, tuned coordinates, demo transcript). Target length: 20–30 pages.

---

## Declaration

Following the ethical principles of fairness and transparency, we, the two
project partners, declare that each of us contributed equally and with shared
dedication to the development and execution of this project — including its
design, programming, testing, and documentation.

> *(Optional — if you prefer to itemize instead of equal contribution, replace the
> paragraph above with, e.g.: "Student A led the reasoning and knowledge base;
> Student B led navigation and the world/configuration; both contributed equally
> to integration, testing, the report and the video.")*

---

## Contents

1. Introduction
2. Related Work
3. HRAI Design (the ideal robot)
4. Solution Architecture
5. Implementation
6. Results
7. Experimental Evaluation
8. Conclusions
9. References

---

## 1. Introduction

**The idea.** We built a **hospital reception / guide robot** on the TIAGo
platform. A visitor arrives and types a request (which doctor they want to see);
the robot recognises returning visitors, consults a semantic knowledge base of
doctors, patients and rooms, decides how best to help, speaks its answer, and
physically guides the visitor to the right room.

**Purpose.** The purpose is to demonstrate *social intelligence* in a service
setting: not merely answering queries, but reasoning about the visitor's
underlying goal and **negotiating** a good outcome when the ideal option is
unavailable. This mirrors the course's "good example" of a restaurant robot that
must offer an alternative dish when a child's preferred dish is unavailable — we
transpose it to a hospital, where accessibility needs make the social reasoning
even more meaningful.

**What we actually developed.** A complete ROS 2 package with three cooperating
nodes (interaction, reasoning, navigation), a JSON semantic memory, custom
service/action interfaces, a lightweight Gazebo world, and CPU-tuned Nav2
configuration. Interaction is typed text in and spoken text-to-speech out. The
system runs on a CPU-only Windows/WSL2 machine with software rendering (no GPU).

**Why the problem matters.** Hospital reception combines everything HRAI cares
about: knowledge (who works where, who is available), memory (recognising
returning patients and their needs), reasoning (what to do when the requested
doctor is busy), generation (speaking clearly and empathetically), and navigation
(guiding through a shared space with obstacles). A robot that simply says
"unavailable" fails the person; a robot that proposes a suitable alternative —
considering wheelchair access, the same medical department, and the next free slot
— genuinely helps. Getting this right is the core challenge of social service
robotics.

**Motivation for the selected techniques.** We use **symbolic AI**: an explicit
semantic knowledge base (knowledge representation) plus a deterministic,
rule-based dialogue policy (reasoning). This keeps the robot's decisions **safe
and fully explainable** — a requirement for a hospital, where the robot must never
invent a doctor, a room, or an availability. Navigation is delegated to the ROS 2
Nav2 planner (search-based path planning + reactive obstacle avoidance),
connecting high-level social reasoning to low-level robot primitives.

---

## 2. Related Work

Our work builds directly on the course lectures and on established HRI literature.

- **Course reference model (Iocchi, Suriani — HRAI lectures).** The lecture
  slides define a functional model of social interaction: *social signal
  perception → social reasoning → social signal generation*, supported by
  *memory*, *mental models*, *knowledge*, a *surrounding model* and *robot
  primitives*. Our architecture instantiates this model one-to-one (Section 4).
- **Knowledge representation and reasoning (symbolic AI / GOFAI).** Our semantic
  knowledge base and rule-based dialogue policy follow the classical
  knowledge-based-system tradition, where behaviour is derived from an explicit,
  inspectable representation rather than learned weights. This is what makes the
  robot's decisions explainable — essential in a medical setting.
- **Task and motion planning.** Guidance is delegated to the ROS 2 **Nav2** stack
  (global path planning + local obstacle avoidance via the DWB controller),
  connecting social reasoning to robot primitives — the separation the course
  promotes.
- **Prior course projects.** Earlier HRI projects (e.g. the *NAO Soccer
  Companion*: a quiz bot with user memory + a PDDL soccer-playing reasoning agent)
  demonstrate the expected combination of interaction, memory and reasoning. Our
  project follows the same spirit — memory-driven personalisation plus explicit
  reasoning — but targets a mobile service scenario with real navigation.

_[FILL IN: add 2–4 real citations you read — e.g. a survey on social service
robots, a paper on robot dialogue/negotiation, and a Nav2 / TIAGo reference — and
one line each on how it relates to your project.]_

---

## 3. HRAI Design (the ideal robot)

Following the guidelines, we first design the *ideal* robot assuming infinite time
and resources, then note what we actually used.

**Ideal hardware.** A TIAGo-class mobile manipulator with: a differential base for
smooth indoor motion; a 360° lidar plus RGB-D cameras for robust mapping,
localisation and people detection; a microphone array for far-field speech
recognition; a touchscreen and speaker for multimodal output; and an arm for
pointing gestures ("the cardiology room is that way").

**Ideal software / functionalities.**
- **Perception:** speech recognition, face recognition (to identify returning
  patients automatically), and emotion/affect estimation to gauge stress.
- **Memory & knowledge:** a live hospital database (doctors, real-time
  availability, appointments), a per-visitor profile (history, accessibility
  needs, preferred language), and a semantic map of the building.
- **Social reasoning:** multi-turn negotiation, empathy-aware phrasing, and
  proactive suggestions (e.g. offering a wheelchair, warning about wait times).
- **Generation:** natural multilingual speech with matching gestures.
- **Navigation:** dynamic obstacle avoidance among moving crowds, elevator use,
  and door opening.

**What we actually built (discussion).** Given limited time and a CPU-only,
no-GPU target, we scoped the ideal design down while preserving its *social*
core:
- Input is **typed text** (not ASR) — this keeps the system CPU-light and the
  demo robust, while the interesting reasoning is unchanged.
- Memory is a **static JSON knowledge base** rather than a live database.
- Reasoning is a focused **rule-based negotiation policy** (offer → accept),
  which fully covers the easy/hard cases the guidelines ask for.
- Generation is **templated speech + offline TTS** (`pyttsx3`, always printed).
- Navigation uses the real **Nav2** stack (path planning + obstacle avoidance),
  with a simulated-motion fallback for machines that cannot run it.
These choices retain every graded capability — memory, social reasoning,
negotiation, generation, navigation — while fitting the hardware budget.

---

## 4. Solution Architecture

The solution is a set of ROS 2 nodes communicating over one service and one
action, mapped directly onto the course reference model.

```
                 ┌────────────────────┐
   visitor text  │  Interaction Node  │  TTS out (speech)
  ───────────────▶  (perception + gen) ├──────────────▶ [speaker / stdout log]
                 └─────────┬──────────┘
                           │ /visitor_request (srv)
                           ▼
                 ┌────────────────────┐      ┌──────────────────┐
                 │  Social Reasoning  │◀────▶│  Knowledge Base  │  (JSON: patients,
                 │       Node         │      │   (semantic mem) │   doctors, rooms)
                 └─────────┬──────────┘      └──────────────────┘
                           │ /goto_location (action)
                           ▼
                 ┌────────────────────┐
                 │  Navigation Node   │  wraps Nav2 (path planning + obstacle avoid)
                 └─────────┬──────────┘
                           ▼
                    TIAGo in Gazebo
```
*Figure 1 — Functional architecture.*

**Components we developed** (shown in the boxes above):
`interaction_node`, `reasoning_node`, `navigation_node`, `knowledge_base`,
`intent_parser`, `tts`, the custom `VisitorRequest.srv` / `GoToLocation.action`,
the Gazebo world, and the configs.

**Existing components we integrated:** ROS 2 Humble (middleware, services,
actions), the **Nav2** navigation stack, `slam_toolbox` (mapping), and Gazebo
(simulation).

**Mapping to the reference model.**

| Reference-model component        | Our component                              |
|----------------------------------|--------------------------------------------|
| Social signal perception         | `interaction_node` + `intent_parser`       |
| Social reasoning                 | `reasoning_node`                           |
| Social signal generation         | `interaction_node` + `tts`                 |
| Memory / knowledge (semantic)    | `knowledge_base` + `data/*.json`           |
| Robot primitives                 | `navigation_node` (Nav2 wrapper)           |
| Surrounding model                | SLAM map + `worlds/hospital.world`         |

**Why services and an action.** The interaction↔reasoning exchange is a *service*
(single request/response). Guidance is an *action* because it is long-running,
streams feedback (distance remaining) and must be cancellable — matching ROS 2
semantics and the reference model (reasoning *requests* a primitive, which reports
progress).

---

## 5. Implementation

**Language / framework.** ROS 2 Humble, Python 3.10, `rclpy`, `ament_python`
(logic) + `ament_cmake` (interfaces, because `ament_python` cannot generate
`rosidl` types).

**Perception — `intent_parser.py`.** Rule-based (regex + matching against known
KB names), so it is CPU-light and explainable. It extracts a visitor name (via
self-introduction patterns or known-patient matching) and a requested doctor. A
scoped case-insensitive regex avoids a subtle bug where `[A-Z]` under
`IGNORECASE` would wrongly capture lowercase words as names.

**Memory — `knowledge_base.py` + `data/*.json`.** A pure-Python class loads three
JSON files (doctors, patients, locations) resolved through the installed package
*share* directory. Key method `alternatives_for(doctor)` returns available
same-department colleagues first — this ordering is what enables negotiation.

**Social reasoning — `reasoning_node.py`.** A ROS 2 service server. It
personalises the greeting for known patients, then applies a small, explicit
policy: available doctor → confirm + guide (*easy case*); unavailable doctor →
negotiate a same-department alternate, else another available doctor, else the
waiting area (*hard case*). Accessibility needs are folded into the phrasing. The
policy lives in clearly named functions (`handle_available`, `handle_unavailable`,
`personalise`) so it can be explained line-by-line.

**Generation — `interaction_node.py` + `tts.py`.** The reasoning node composes the
response text; the interaction node speaks it via `tts.speak()`, which uses the
offline `pyttsx3` engine and always prints the line as `[TIAGo]: …` (so the demo
never breaks if TTS is unavailable, and the printed line is a legible caption).

**Robot primitives — `navigation_node.py`.** A ROS 2 action server. It converts a
location key to a pose (via the KB) and forwards a `NavigateToPose` goal to Nav2,
relaying feedback. A `use_nav2:=false` fallback simulates motion so the demo runs
without Gazebo/Nav2 on weak machines.

**Environment.** `worlds/hospital.world` is primitive-only (boxes/cylinders, no
meshes, shadows off) for software rendering. `config/nav2_params.yaml` is tuned
for CPU (DWB, low `max_vel_x`, small costmaps, fewer samples/particles), each
change annotated `# CPU:`.

**Putting it together.** `launch/reception.launch.py` starts the three nodes with
parameters (`input_mode`, `use_nav2`); `demo.launch.py` runs the scripted
two-interaction demo. Helper: `build_and_test.sh`. Libraries used: `rclpy`,
`nav2_msgs`, `pyttsx3` (optional), `pytest`.

_[FILL IN: screenshot of the running system (Gazebo + terminal).]_

---

## 6. Results

We demonstrate two interactions that showcase different reasoning under different
situations (the guidelines' key requirement).

### 6.1 Easy case — available doctor (personalisation + guidance)
A returning visitor, **Mr. Ferrari**, asks for **Dr. Verdi** (Neurology, free).
The robot recognises him, greets him by name, recalls his wheelchair need,
confirms Dr. Verdi's availability, and guides him to the neurology room. This
shows *memory* and *robot primitives* working together.

The exact dialogue produced by the system (the reasoning is deterministic, so
this is the verbatim output):

```
[Visitor]: Hello, I'm Mr. Ferrari and I'd like to see Dr. Verdi.
[TIAGo]:   Welcome back, Mr. Ferrari! Good to see you again. Last time you saw
           Dr. Bianchi. Dr. Verdi in Neurology is available now. I'll make sure
           the route is suitable for wheelchair access. I'll guide you there —
           please follow me.
[TIAGo]:   We've arrived at the neurology room. Take care!
```

Note how the robot recalls the previous visit and the wheelchair need — the
*memory* component in action.

_[FILL IN: add a screenshot / video timestamp of this interaction from your run.]_

### 6.2 Hard case — unavailable doctor (social negotiation)
A visitor asks for **Dr. Bianchi** (Cardiology, busy until 15:30). Instead of
refusing, the robot **negotiates**: it offers **Dr. Rossi**, an available
cardiologist in the same department; the visitor accepts; the robot guides them
to the cardiology room. This is the graded *social reasoning*.

The exact dialogue produced by the system:

```
[Visitor]: Hi, I need to see Dr. Bianchi in Cardiology.
[TIAGo]:   Welcome to the hospital reception. Dr. Bianchi is busy until 15:30,
           but Dr. Rossi, also in Cardiology, can see you now. Shall I take you
           to Dr. Rossi instead? I'll guide you there.
[Visitor]: Yes, that works for me — please take me to the alternate.
[TIAGo]:   Great, thank you. Let's go.
[TIAGo]:   We've arrived at the cardiology room. Take care!
```

The robot does not refuse: it proposes a same-department, available alternative
and only proceeds once the visitor accepts — the negotiation that is the heart of
the project's social intelligence.

_[FILL IN: add a screenshot / video timestamp of this interaction from your run.]_

### 6.3 Inner representation
The robot's inner representation is the explicit **semantic knowledge base**
(doctors, patients with needs, rooms) and the **decision policy** that operates
over it. The console logs make this observable: the perceived
`(visitor_name, requested_doctor)`, the chosen branch (`[EASY]` / `[HARD]`), the
selected alternate doctor, and the resulting `goto_location`. The same request
produces different behaviour depending on the knowledge-base state (available vs
unavailable), demonstrating genuine reasoning rather than a fixed script.

### 6.4 Modalities
Two input modes (interactive typing / scripted playback) and two navigation modes
(real Nav2 / simulated motion) illustrate different modalities of interaction and
how the robot degrades gracefully on weak hardware.

### 6.5 Demo video
A ~3-minute screen recording (`HRAI_demo_3min.mp4`, 3:02, 1280×720) captures the
complete scripted demo running live on ROS 2 Humble inside a container, via a
virtual display: an intro describing the robot's capabilities, both interactions
(Sections 6.1–6.2) produced live by the running nodes — including the navigation
feedback stream during guidance — and a closing summary of the easy and hard
cases. The video is published with the code:
https://github.com/Farazkhan542/hrai-hospital-reception/releases/tag/v1.0

### 6.6 SLAM map of the hospital world
A real occupancy-grid map of `hospital.world` was produced with `slam_toolbox`
running against **TIAGo simulated headlessly in Gazebo** (Xvfb virtual display,
software rendering, `arm_type:=no-arm` to fit the CPU budget). The laser
(`/scan_raw`) published real ranges under software rendering, and a scripted
exploration routine drove the base (`/key_vel`) while the map was built, then
saved with `nav2_map_server` (`maps/hospital_map.pgm/.yaml`, 139×92 cells @ 5 cm,
origin `[-0.5, -1.61, 0]`). The map clearly shows the reception walls and the
central partition doorway of the world. Coverage of the far rooms is partial —
the scripted run is short; driving longer (e.g. by teleop in the course
container) extends the map. Because TIAGo spawns at the world origin
(reception), the map frame coincides with the world frame and the
`locations.json` coordinates are used unchanged.

---

## 7. Experimental Evaluation

We design an experiment to evaluate whether the robot's **negotiation** and
**personalisation** improve the interaction, as required by the guidelines.

**Research questions.**
- **RQ1.** Does offering a negotiated alternative (vs. simply reporting
  unavailability) increase task success and user satisfaction?
- **RQ2.** Does personalisation (recognising a returning visitor and their needs)
  increase perceived helpfulness/trust?

**Hypotheses.**
- **H1.** Users interacting with the *negotiating* robot report higher
  satisfaction and complete their goal more often than users with a
  *non-negotiating* (plain-refusal) robot.
- **H2.** Users greeted with *personalised* recognition rate the robot as more
  helpful and trustworthy than users given a *generic* greeting.

**Independent variables (manipulated).**
- *Reasoning strategy*: {negotiation, plain-refusal} (for H1).
- *Greeting*: {personalised, generic} (for H2).

**Dependent variables (measured).**
- *Task success* (binary: did the visitor reach a suitable doctor?).
- *User satisfaction* (Likert 1–7).
- *Perceived helpfulness / trust / likeability* (Godspeed questionnaire).
- *Interaction time* (seconds).

**Null hypotheses.**
- **H1₀.** No difference in task success or satisfaction between negotiation and
  plain-refusal conditions.
- **H2₀.** No difference in perceived helpfulness/trust between personalised and
  generic greetings.

**Experimental protocol.**
- *Design:* between-subjects for reasoning strategy (to avoid learning effects);
  greeting counterbalanced.
- *Participants:* a target of **N = 24** recruited from students, balanced across
  conditions (12 per reasoning-strategy group). _[FILL IN: adjust N to what you
  can realistically recruit.]_
- *Task:* each participant plays a visitor asking for a doctor who turns out to be
  unavailable, then completes a short questionnaire.
- *Scenarios:* fixed knowledge base so all participants face the same
  unavailability, ensuring comparability.
- *Measures:* task-success logging by the system + post-interaction questionnaires.
- *Analysis:* independent-samples t-test / Mann–Whitney for H1; t-test / Wilcoxon
  for H2; report effect sizes; α = 0.05.
- *Threats to validity:* text-only input (no ASR), simulated environment, and a
  static knowledge base; discussed as limitations.

_[FILL IN: if you run even a small pilot (e.g. 4–6 classmates), report the numbers
here; otherwise present this as the proposed evaluation, which is what the
guidelines ask for.]_

---

## 8. Conclusions

**What we built.** A functioning, socially intelligent hospital-reception robot
that recognises returning visitors, reasons about doctor availability, negotiates
alternatives considering the visitor's needs, speaks its answer, and guides via
Nav2 — all within a CPU-only budget.

**What we learned.** Mapping the course reference model
(perception/reasoning/generation + memory/knowledge/primitives) onto ROS 2
services and actions clarified the design. We learned that keeping reasoning
**symbolic and explicit** makes the robot's behaviour easy to test, explain and
trust — important properties for a hospital setting.

**What was harder than expected.** Tuning Nav2 to run under software rendering
(no GPU) required many conservative parameter choices; building a lightweight but
convincing world took iteration; and making perception robust with simple rules
(rather than a language model) needed careful handling of edge cases.

**Strengths.** Explainable, safe reasoning; graceful degradation (no-Nav2, no-GPU
both work via `use_nav2:=false`); a clear architecture mapped to the course model;
and an automated test suite (29 tests).

**Limitations.** Keyword-based perception; a static knowledge base; a fixed
two-step negotiation; and text (not speech) input.

**Future improvements.** Speech recognition and face recognition; a live hospital
database; richer multi-turn negotiation; crowd-aware navigation; and a formal user
study following Section 7.

---

## 9. References

The following are real, relevant references you can read and cite. **Please skim
each and keep only the ones you actually use**, then format them consistently
(e.g. IEEE). Add the exact HRAI lecture-slide titles/dates from your course page.

1. L. Iocchi, V. Suriani. *Human-Robot-AI Interaction — course lecture slides.*
   Elective in Artificial Intelligence (AI & Robotics), Sapienza University of
   Rome, A.Y. 2025–26.
2. T. Fong, I. Nourbakhsh, K. Dautenhahn. "A survey of socially interactive
   robots." *Robotics and Autonomous Systems*, 42(3–4):143–166, 2003.
3. C. Bartneck, D. Kulić, E. Croft, S. Zoghbi. "Measurement instruments for the
   anthropomorphism, animacy, likeability, perceived intelligence, and safety of
   robots" (the *Godspeed* questionnaire). *International Journal of Social
   Robotics*, 1(1):71–81, 2009.
4. S. Macenski, F. Martín, R. White, J. Ginés Clavero. "The Marathon 2: A
   Navigation System" (Nav2). *IEEE/RSJ IROS*, 2020.
5. S. Macenski, T. Foote, B. Gerkey, C. Lalancette, W. Woodall. "Robot Operating
   System 2: Design, architecture, and uses in the wild." *Science Robotics*,
   7(66), 2022.
6. PAL Robotics. *TIAGo mobile manipulator — technical documentation.*
   https://pal-robotics.com/robots/tiago/

_[FILL IN: add 1–2 papers specific to service-robot dialogue or negotiation that
you read, and remove any of the above you did not use.]_

---

## Appendix A — How to build, run and demo

See `README.md`. In brief (inside the container):
```bash
colcon build --packages-up-to hospital_reception && source install/setup.bash
# guaranteed offline demo (no Gazebo/Nav2/GPU needed):
ros2 launch hospital_reception demo.launch.py use_nav2:=false
# interactive typing:
ros2 launch hospital_reception reception.launch.py use_nav2:=false
```

## Appendix B — Repository layout & tests

Two packages: `hospital_reception` (nodes, KB, world, configs, launch, scripts,
tests) and `hospital_reception_interfaces` (srv + action). Automated tests:
**29 pytest cases** (knowledge base + intent parser), all passing:

```
$ python3 -m pytest test/ -q
.............................                                            [100%]
29 passed
```

**Container build & run (verified).** Both packages build cleanly with `colcon`
on ROS 2 Humble, and the scripted demo runs end-to-end in a ROS 2 Humble
container (`ros:humble-ros-base`):

```
$ colcon build --packages-up-to hospital_reception
Starting >>> hospital_reception_interfaces
Finished <<< hospital_reception_interfaces [39.9s]
Starting >>> hospital_reception
Finished <<< hospital_reception [2.27s]
Summary: 2 packages finished [43.9s]
```

The service (`/visitor_request`) and the action (`/goto_location`) are exercised
by the demo; the reasoning node logs confirm the two branches firing:
`[EASY] Available -> guiding to 'neurology_room'` and `[HARD] Unavailable ->
same-dept alternate Dr. Rossi at 'cardiology_room'`. The verbatim dialogue is in
Section 6. (The full Gazebo/TIAGo visual simulation and the ~3-minute demo video
are produced separately, inside the course container.)

---

*Prepared for the HRAI 2025–26 project submission.*
