# Audio Engine Reference

The `MasterClockEngine` is the timing and execution heart of the live looper. It operates independently of the UI and hardware input layers, ensuring that audio playback and recording remain sample-accurate and immune to UI thread freezing.

## Architectural Workflow

The engine utilizes a **Dual-Thread Producer-Consumer Architecture** to handle time synchronization and audio dispatching. 

### 1. The Timeline Calculator (Producer Thread)
The `_clock_loop` thread runs continuously in the background. Its job is to look slightly ahead into the future (the "lookahead window," typically 50ms) and calculate what audio events *should* happen.
- It calculates the absolute playback time using modulo arithmetic based on the master loop duration.
- It iterates over all active tracks.
- If it finds MIDI notes that fall within the current lookahead window, it packages them into a tuple with an exact future timestamp and pushes them into the `audio_queue`.

### 2. The Audio Dispatcher (Consumer Thread)
The `_dispatcher_loop` thread runs as fast as possible (sleeping for only 1ms). It constantly checks the `audio_queue`.
- The queue is a Python `heapq` (Priority Queue) sorted by exact execution time.
- When the hardware clock (`time.perf_counter()`) matches or exceeds the timestamp of the first item in the queue, it pops the item and immediately executes the Fluidsynth audio trigger (`noteon`, `noteoff`, or metronome click).

### 3. Priority Tie-Breaking
To prevent "stuck notes" or audio glitches when multiple events happen at the exact same microsecond (e.g., a loop restarting), the engine enforces strict tie-breaking priorities when pushing to the queue:
1. **Priority 0 (Highest):** `NOTE_OFF` events. (Always stop old notes before playing new ones).
2. **Priority 1:** `METRO` clicks.
3. **Priority 2:** `NOTE_ON` events.

## State Machine Workflow
The engine relies on `set_state()` to handle complex transitions.
- **RECORDING -> PLAYING:** The engine locks the Master Loop length mathematically by rounding the elapsed time to the nearest downbeat based on the time signature. It also fires `_sanitize_open_notes()` to inject fake `note_off` events for any keys the user was holding down when they stopped recording.
- **COUNT_IN -> RECORDING:** This transition happens *automatically* inside the `_clock_loop` once the calculated count-in beats elapse. The timeline is mathematically shifted back to `0.0`, and the armed track is wiped clean exactly on the downbeat to prevent count-in bleed.

---

## API Reference

*The documentation below is automatically generated from the Python source code docstrings.*

::: core.engine.MasterClockEngine