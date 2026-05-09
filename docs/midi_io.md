# MIDI I/O Reference

The `MidiIO` module (formerly `AudioIO`) acts as the hardware abstraction layer for the live looper. It is strictly responsible for listening to incoming MIDI bytes, filtering them, and routing them to the appropriate software layers. It enforces the separation of concerns by ensuring the core logic (`api.py`) never interacts directly with hardware ports.

## Architectural Workflow

The module operates entirely via an asynchronous callback triggered by the `mido` library whenever a hardware event occurs.

### 1. Connection and Listening
When `start()` is called, a persistent background listener is opened on the specified MIDI port. Every incoming byte triggers `on_midi_callback(msg)`. 

### 2. The Routing Split
The callback immediately categorizes the incoming message into one of two streams:
- **Control Changes (CC):** Buttons, knobs, and joysticks. The module looks up the CC number in the `Project.midi_mapping` dictionary. If mapped, it translates the raw integer into an abstract string (e.g., `"TOGGLE_RECORD"`) and passes it to the `LooperAPI` via the `handle_command` method.
- **Musical Notes:** `note_on` and `note_off` events. These bypass the API completely for latency reasons. The module finds the currently armed `Track` and directly triggers its Fluidsynth playback methods.

### 3. Recording Injection
If the `MasterClockEngine` is currently in the `"RECORDING"` state, the `MidiIO` module intercepts musical notes, calculates their exact timestamp relative to the engine's `start_time`, and injects them into the armed track's memory (`add_midi_event`). 

### 4. Analog Filtering (Joystick Mapper)
Hardware controllers often send continuous streams of data for analog sticks (e.g., rapidly firing values 50, 60, 80, 127 as you push the stick). If sent directly to the UI, this would cause menus to scroll uncontrollably. 
The `JoystickMapper` acts as a discrete state machine:
- It tracks the analog value against a hardcoded threshold (e.g., `100`).
- It only emits a signal the *exact moment* the threshold is crossed.
- It requires the stick to return below the threshold before it can be triggered again, cleanly converting an analog sweep into a single, digital button press.

---

## API Reference

::: core.midi_io.MidiIO

::: core.midi_io.JoystickMapper