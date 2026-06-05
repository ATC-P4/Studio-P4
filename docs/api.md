# API & Routing Reference

This section provides the technical API documentation for the **Controller layer** of Studio P4. 

While the conceptual explanation of how these modules interact can be found in the [Data Flow Pipelines](data_flow.md) guide, this page serves as a direct code reference for the three core routing components:

* **`LooperAPI`**: The central business logic facade. Look here for the core methods that alter the studio's state (e.g., `toggle_record()`, `add_track()`).
* **`MidiIO`**: The hardware abstraction layer. Look here for how raw bytes from the physical keyboard are captured and translated.
* **`MidiInputRouter`**: The state machine. Look here to see how translated hardware inputs are mapped to specific `LooperAPI` actions based on the user's current navigation mode.

*Note: The detailed documentation below is automatically generated directly from the Python source code docstrings.*

## Business Logic
::: core.api.LooperAPI

## Hardware Abstraction
::: core.midi_io.MidiIO

## Input Routing
::: core.midi_io.MidiInputRouter

::: core.midi_io.JoystickMapper

::: core.midi_io.NavMode

::: core.midi_io.NavType

::: core.midi_io.BoundaryState

## Project file IO

::: core.project_io.ProjectIO