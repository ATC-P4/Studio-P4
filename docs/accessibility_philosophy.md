# Accessibility Philosophy: The "Why"

Studio P4 was developed as part of the **EPFL Assistive Technology Challenge**. From the very first line of code, the architecture was driven by a single question: *How do we make music production truly accessible for visually impaired musicians?*

To answer this, we had to rethink the modern Digital Audio Workstation (DAW).

## The Problem with Traditional DAWs

Modern DAWs (like Ableton, Logic, or FL Studio) are incredibly powerful, but they are designed as visual labyrinths. They rely heavily on:

1.  **Mouse-driven workflows:** Clicking tiny icons to arm tracks, open plugins, or adjust panning.
2.  **Visual feedback:** Relying on screen colors to know if you are recording, or looking at a grid to align loops.
3.  **Nested Menus:** Forcing screen-reader software to navigate through dozens of irrelevant UI elements just to change an instrument.

For a visually impaired user, this visual-first approach creates a massive barrier to entry. The technology gets in the way of the music.

## The Studio P4 Solution: "Headless" Design

We designed Studio P4 to be entirely **"headless"**. While a visual interface exists for sighted collaborators, the application does not require a screen, a mouse, or a computer keyboard to function. 

### 1. Hardware-First Navigation
The MIDI keyboard is the only interface the musician needs to touch. By utilizing the tactile feedback of physical buttons and a joystick (e.g., on the AKAI MPK Mini Plus), muscle memory replaces visual navigation. Pushing the joystick "Down" to add a track feels physical and immediate.

### 2. Auditory Feedback (Text-to-Speech)
To replace visual cues (like a red recording light), we integrated an offline, low-latency Text-to-Speech engine (Piper). The system announces boundaries, states, and changes in real-time. 

### 3. Asynchronous Decoupling
Audio processing requires exact, microsecond precision. If the computer pauses the music to generate a voice announcement, the loop is ruined. 
To solve this, our accessibility features are entirely decoupled from the audio engine using an **EventBus**. The core audio engine simply shouts *"Recording Stopped!"* into the void, and a completely separate background thread catches that event and synthesizes the voice. This guarantees that accessibility never compromises audio performance.