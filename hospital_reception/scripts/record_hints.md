# Recording the demo video (~3 minutes)

Notes for capturing the deliverable video showing BOTH interactions.

## What to show
1. **Intro (10-15 s):** one terminal, title the scenario ("TIAGo hospital
   reception — social intelligence demo").
2. **Easy case (~1 min):** returning visitor *Mr. Ferrari* asks for the available
   *Dr. Verdi*. Highlight:
   - personalised greeting ("Welcome back, Mr. Ferrari…") = memory,
   - confirmation, and
   - guidance to `neurology_room`.
3. **Hard case (~1.5 min):** a visitor asks for *Dr. Bianchi* (unavailable). Highlight:
   - the robot does NOT just refuse,
   - it negotiates and offers *Dr. Rossi* (same department, available now),
   - the wheelchair-needs phrasing if applicable,
   - visitor accepts → guidance to `cardiology_room`.
4. **Close (10 s):** the "demonstration complete" line.

## Easiest capture path (no GPU needed)
Run the scripted demo with the simulated-motion fallback so nothing is
GPU-heavy and every line is printed as an on-screen caption:

```bash
# Terminal A (inside the TIAGo container, workspace sourced):
ros2 launch hospital_reception demo.launch.py use_nav2:=false
```

That single command starts the reasoning + navigation nodes and the `run_demo`
driver, which plays both interactions with pauses. Screen-record this terminal.

## Full-simulation capture (if the machine can handle Nav2)
```bash
# Terminal A: course sim with our world + Nav2 (see README "Run (full)")
# Terminal B:
ros2 launch hospital_reception reception.launch.py input_mode:=scripted use_nav2:=true
# plus an RViz + Gazebo window to show the robot actually driving room-to-room.
```
Record Gazebo (robot moving), RViz (path + costmap), and the terminal (dialogue)
side by side.

## Tips
- Increase terminal font size so captions are readable at video resolution.
- If TTS audio is captured, great; if not, the printed `[TIAGo]:` lines are the
  captions. `tts.py` prints every line regardless.
- Keep the whole thing under ~3 minutes; the two turns + guidance fit easily.
