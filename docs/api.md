# API & Routing Reference

The `api.py` module serves as the **Controller** in the MVC architecture. It acts as the central brain of the application, receiving abstract inputs from the hardware layer, executing business logic on the data models, and broadcasting state changes to the UI and Voice components.

## Architectural Workflow

The module is strictly divided into two distinct responsibilities: Business Logic (`LooperAPI`) and Input Translation (`MidiInputRouter`).

### 1. The Facade (`LooperAPI`)
The `LooperAPI` class implements the **Facade Pattern**. It hides the complexity of the underlying `MasterClockEngine` and `Project` models behind a simple, unified interface. 
- It is entirely "dumb" regarding hardware: it does not know what a MIDI controller, joystick, or button is. 
- It exposes clean Python methods like `toggle_record()` or `arm_track(index)`.
- **Event-Driven Decoupling:** When a state changes, the API does not call the voice synthesizer directly. Instead, it uses the **Observer Pattern**, broadcasting events via the `EventBus` (e.g., `events.emit("RECORDING_STOPPED")`). This guarantees that the core logic is never blocked by text-to-speech generation.

### 2. The Input Router (`MidiInputRouter`)
Hardware controllers send a chaotic stream of directional inputs and button presses. The `MidiInputRouter` organizes this chaos using the **Command** and **State** patterns.

When `route_command("ACTION_STRING")` is called, it resolves the action in O(1) time without using long `if/elif` chains:

- **Global Actions (`_action_map`):** Commands that do the same thing regardless of the application state (e.g., `TOGGLE_PLAY`, `BPM_UP`).
- **Contextual Navigation (`_nav_matrix`):** A 2D State Matrix. A command like `NAV_UP` executes entirely different functions depending on whether the system is in `NavMode.TRACK` (moving through the looper tracks) or `NavMode.INSTRUMENT` (scrolling through `.sf2` soundfonts).

### 3. Boundary & Double-Tap Logic
A unique feature of the `MidiInputRouter` is its mathematical boundary handler (`_edge_handlers`).
When cycling through tracks with the joystick, the router calculates if the cursor is hitting the top or bottom edge of the track list. 
- **Hitting an Edge:** Primes a `_pending_edge` state and triggers a voice warning (e.g., "Press up again to save").
- **Double-Tapping:** If the user pushes into the boundary a second time, it executes a macro command (Saving the project at the Top Edge, or appending a New Track at the Bottom Edge). 
- **Canceling:** Any normal navigation instantly clears the pending edge state, preventing accidental macros.

---

## API Reference

::: core.api.LooperAPI

::: core.midi_io.MidiInputRouter

::: core.midi_io.NavMode

::: core.midi_io.BoundaryState