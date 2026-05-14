# Welcome to Studio P4 🎹

**Studio P4** is an open-source, hardware-first, multi-track MIDI looper designed for pre-studio track creation and built specifically to empower visually impaired musicians. This project was proudly developed as part of the **Assistive Technology Challenge**.

Traditional Digital Audio Workstations (DAWs) rely heavily on complex visual interfaces and mouse-driven workflows. Studio P4 solves this by offering a completely "headless" experience. Controlled entirely via a MIDI keyboard and guided by an integrated Text-to-Speech (TTS) voice assistant, it allows musicians to focus purely on touch, hearing, and creativity.

---

## How to Use This Documentation

Whether you are a musician ready to record your first loop, or a developer looking to contribute to the codebase, this documentation is organized to help you find exactly what you need.

### Musician's Guide
*Are you a user looking to make music? Start here.*
* **[Recording a Loop](recording_loop.md):** Learn how to set the tempo, arm tracks, and lock in your master loop.
* **[Managing Tracks & Sounds](managing_tracks.md):** Navigate the studio and swap instruments using the joystick.
* **[Saving & Loading](saving_projects.md):** Learn how the studio automatically handles your files.

### Developer's Guide
*Are you looking to install, configure, or distribute the application?*
* **[System Setup](setup.md):** A step-by-step guide to installing FluidSynth and Python dependencies.
* **[Remapping MIDI Controls](remap_midi.md):** How to adjust the code if you are not using an AKAI MPK Mini Plus.
* **[Adding SoundFonts](add_soundfonts.md):** How to expand the instrument library.
* **[Building the EXE](build_exe.md):** Instructions for compiling the standalone Windows executable.

### Architecture & Concepts
*Are you curious about how the system is designed?*
* **[Accessibility Philosophy](accessibility_philosophy.md):** The core mission driving our headless, tactile workflow.
* **[System Architecture](architecture.md):** A breakdown of our strict Model-View-Controller (MVC) design.
* **[Data Flow Pipelines](data_flow.md):** Follow a MIDI signal from the physical button press to the speakers.

### API Reference
*Auto-generated technical documentation for the Python codebase.*
* **[Controllers & MIDI](api.md) | [Audio Engine](engine.md) | [Data Models](models.md) | [User Interface](ui.md)**

---

## Open Source
Studio P4 is released under the MIT License. We welcome contributions from developers, musicians, and accessibility advocates to help us make music production a barrier-free experience for everyone.