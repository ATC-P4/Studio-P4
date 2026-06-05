# Data Models Reference

This section provides the technical API documentation for the core data structures of the application. These classes strictly manage state, memory, and thread locks, following the Single Responsibility Principle.

To help you navigate the data hierarchy:

* **`Project`**: The root container for a session. It manages global settings (like BPM and Time Signature) and holds the master list of all active tracks.
* **`Track`**: The individual timeline container. It stores the currently assigned instrument (`.sf2` file) and the raw, timestamped MIDI events recorded by the user.
* **`Metronome`**: A specialized, lightweight model that calculates and generates synthetic click-track events based on the `Project`'s tempo.

*Note: The detailed documentation below is automatically generated directly from the Python source code docstrings.*

## Session Management
::: core.models.Project

## Timeline Structures
::: core.models.Track

::: core.models.Metronome

## General utilities
::: core.utils

:::core.utils.EventType