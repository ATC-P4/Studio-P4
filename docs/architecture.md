# System Architecture

The Python Live Looper is built on a strict **Model-View-Controller (MVC)** design pattern, augmented with an **Event-Driven Observer** pattern for auxiliary systems. 

The primary goal of this architecture is **Decoupling**: the UI does not know how audio works, the audio engine does not know what a "button" is, and the core business logic does not know how to speak French.

---

## The MVC Layers

### 1. The Model (Data & Execution)
*Files: `core/models.py`, `core/engine.py`*
The lowest layer of the application. It holds the pure state of the session in memory and manages the highly time-sensitive audio threads.
- **`Project` & `Track`:** Act as pure data containers (BPM, Time Signature, MIDI events) and wrappers for the `Fluidsynth` instances.
- **`MasterClockEngine`:** The mathematical heart of the looper. It operates on isolated background threads, reading the `Track` data to schedule sample-accurate audio events regardless of what the UI is doing.

### 2. The View (User Interface)
*Files: `ui/main_window.py`, `ui/track_widget.py`*
Built with PySide6 (Qt). The View is completely "dumb". It contains zero business logic or audio processing.
- **Input:** The UI only emits Qt Signals (e.g., `record_requested.emit()`) when a user clicks a button.
- **Output:** The UI redraws itself blindly by consuming a Data Transfer Object (DTO) — a plain Python dictionary containing the current state of the application.

### 3. The Controller (Routing & Logic)
*Files: `core/api.py`, `core/midi_io.py`*
The brains of the operation. The Controller layer catches inputs from the outside world, updates the Models, and tells the View to redraw.
- **`MidiIO`:** The Hardware Abstraction Layer. It listens to raw bytes from the physical MIDI controller and translates them into abstract command strings (e.g., `"TOGGLE_RECORD"`).
- **`LooperAPI`:** The Business Logic Facade. It provides a clean, unified interface to manipulate the `Project` and `Engine`.
- **`MidiInputRouter`:** A 2D State Machine that connects `MidiIO` commands to specific `LooperAPI` functions based on the current context (e.g., whether the joystick is in Track Mode or Instrument Mode).

---

## High-Level Interactions (Data Flow)

To understand the system, follow these two critical data flow paths:

### Flow A: Hardware MIDI Input -> Data Update
When a user presses a physical button on their MIDI controller:
1. **`MidiIO`** receives a raw MIDI Control Change (e.g., `CC 119`).
2. It looks up `CC 119` in the mapping dictionary and translates it to `"TOGGLE_RECORD"`.
3. It passes `"TOGGLE_RECORD"` to the **`MidiInputRouter`** (living inside `api.py`).
4. The Router looks up `"TOGGLE_RECORD"` in its Action Map and executes `LooperAPI.toggle_record()`.
5. The **`LooperAPI`** tells the **`MasterClockEngine`** to change its state to `"COUNT_IN"`.

### Flow B: Backend Update -> UI Redraw
Once the `LooperAPI` finishes changing the backend state (from Flow A), it must update the screen:
1. The API calls its internal `self._ui_callback()`.
2. This callback triggers the `MainWindow.update_ui(dto)` method, passing in `api.get_state_dto()`.
3. The `get_state_dto()` method packages the entire backend state (current BPM, Engine State, Track Mutes) into a simple dictionary.
4. The **`MainWindow`** receives the dictionary and updates the physical colors of the buttons and text labels to match the new reality.

---

## Event-Driven Decoupling (The EventBus)

To prevent the core `LooperAPI` from becoming a "God Object" that controls everything, auxiliary features are decoupled using an `EventBus` (`core/events.py`).

**Example: Text-to-Speech (Voice)**
If a user arms a track, the API needs to announce it via Text-to-Speech. However, the API does not import the `VoiceService`.
1. The API simply shouts to the void: `events.emit("TRACK_ARMED", track_name="Bass")`.
2. The **`VoicePresenter`** (which was secretly listening to the EventBus) catches this event.
3. The Presenter decides to translate this into the French phrase *"Bass armé"* and sends it to the `VoiceService` to synthesize the audio.

This guarantees that if the Voice Engine crashes, or if the user turns it off, the core Looper logic continues to function perfectly.

---

## Directory Structure Overview

```text
root/
├── main.py                     # Composition Root (wires everything together)
├── docs/                       # MkDocs Markdown Documentation
├── sf2/                        # SoundFont assets
├── core/                       # Backend & Business Logic
│   ├── api.py                  # Controllers (LooperAPI, InputRouter)
│   ├── audio_io.py             # Hardware MIDI Listeners
│   ├── engine.py               # Time & Thread Management
│   ├── models.py               # Pure Data Structures (Project, Track)
│   ├── midi_exporter.py        # Disk I/O service for saving
│   ├── voice.py                # Infrastructure for TTS
│   └── utils.py                # EventBus & Pathing helpers
└── ui/                         # Frontend & Views
    ├── main_window.py          # Master Qt Window
    └── track_widget.py         # Qt Component for individual tracks