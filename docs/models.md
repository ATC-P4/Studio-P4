# Data Models Reference

The `models.py` module defines the core data structures of the live looper. Following the **Model-View-Controller (MVC)** and **Single Responsibility Principle (SRP)**, these classes are strictly designed to hold state in memory and apply soundfont configurations. 

They do *not* handle hardware routing, user interfaces, or file I/O (which are delegated to the `MidiIO`, `LooperAPI`, and `MidiExporter` respectively).

## Architectural Overview

The application state is organized in a hierarchical tree:

### 1. The `Project` (Root)
The `Project` acts as the master container for the entire session. 
- It holds the global `fluidsynth.Synth` instance to ensure all tracks share the same audio driver and sample rate.
- It manages global musical properties (BPM, Time Signature).
- It acts as an automatic channel manager, maintaining a list of `available_channels` (skipping Channel 0 to prevent hardware feedback loops, and reserving Channel 9 for the metronome) and popping them off as new tracks are created.

### 2. The `Track`
Each `Track` represents a single instrument timeline. It holds fundamental states like `is_armed`, `is_muted`, and its specific `sf2_path`.

**Crucial Architecture Note: Thread Safety**
Because the live looper is highly asynchronous, the `Track.midi_events` list is accessed by three different threads simultaneously:
1. **The Main UI Thread:** Clears the events when restarting a count-in.
2. **The MidiIO Thread:** Appends new events while a user is actively recording.
3. **The Engine Clock Thread:** Iterates over the events to calculate modulo playback times.

To prevent `RuntimeError` crashes, every `Track` contains a `threading.Lock()` named `event_lock`. This lock is automatically acquired whenever notes are added, cleared, or looped.

### 3. The `Metronome`
A simplified class that hardcodes itself to Channel 9 and specifically manages the "Tick" and "Tock" MIDI notes (76 and 77) based on whether a beat is a downbeat.

---

## API Reference

::: core.models.Project

::: core.models.Track

::: core.models.Metronome