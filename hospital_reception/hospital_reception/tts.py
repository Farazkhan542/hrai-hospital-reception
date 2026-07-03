#!/usr/bin/env python3
"""Thin, crash-proof text-to-speech helper.

Report mapping: part of **Social signal generation** — turning the robot's
chosen response into an audible signal. We keep it deliberately minimal and
CPU-light (offline ``pyttsx3``), and we ALWAYS print the line as well so the
demo video has legible captions and the demo never breaks just because a speech
engine is missing on the target machine.

Design rules (from the spec):
  * Try ``pyttsx3`` (offline, no network, low CPU).
  * If it is unavailable or errors, fall back to ``print("[TIAGo]:", text)``.
  * Never raise — a broken TTS must not stop the interaction.
"""

from __future__ import annotations

# We initialise the engine lazily and cache it, so importing this module is
# free and a missing pyttsx3 only matters the first time we actually speak.
_engine = None
_engine_tried = False


def _get_engine():
    """Return a cached pyttsx3 engine, or ``None`` if it cannot be created."""
    global _engine, _engine_tried
    if _engine_tried:
        return _engine
    _engine_tried = True
    try:
        import pyttsx3  # imported lazily; optional dependency
        _engine = pyttsx3.init()
        # Slightly slower rate reads more clearly on a demo video.
        try:
            rate = _engine.getProperty('rate')
            _engine.setProperty('rate', max(120, int(rate) - 25))
        except Exception:
            pass  # property tweaks are best-effort only
    except Exception as exc:  # pyttsx3 missing, no audio device, driver error...
        print(f"[tts] pyttsx3 unavailable ({exc}); falling back to stdout.")
        _engine = None
    return _engine


def speak(text: str) -> None:
    """Speak ``text`` aloud if possible; always echo it to stdout.

    Echoing to stdout is intentional: it is the on-screen caption for the demo
    video and the log line graders can read.
    """
    # Always log — this is the caption/log the spec requires.
    print(f"[TIAGo]: {text}", flush=True)

    engine = _get_engine()
    if engine is None:
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:
        # Speech failed at runtime — degrade silently to the printed line.
        print(f"[tts] speak failed ({exc}); text was printed only.")


if __name__ == '__main__':
    speak("Hello, welcome to the hospital reception. This is a text to speech test.")
