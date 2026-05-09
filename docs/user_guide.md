# User Manual: Python Live Looper

Welcome to the Python Live Looper (Studio P4). This application is a hardware-first, multi-track MIDI looper designed for live performance. 

While the application features a visual interface on your computer screen, it is built to be controlled entirely from your MIDI keyboard or controller, supported by an interactive Voice Assistant that announces your actions.

---

## 1. Core Concepts

* **The Master Track:** The first track you record acts as the "Master Track". Its length dictates the loop duration for the entire project. All subsequent tracks will automatically loop to match this duration.
* **Armed Tracks:** Only **one** track can be "Armed" at a time. The armed track is the one that currently receives the notes you play on your keyboard.
* **Voice Feedback:** The system includes a Text-to-Speech engine. As you navigate using your MIDI controller, a voice will announce your current track, mode, and system status (in French), allowing for "headless" operation where you don't need to look at the screen.

---

## 2. Hardware MIDI Controls

The looper is designed around a dual-mode navigation system. Your controller's joystick (or directional D-Pad) acts as the primary command center.

### Global Commands
These buttons work regardless of what mode you are in:
* **Record (Toggle):** Arms the engine. If stopped, it triggers a "Count-In" before recording starts. Pressing it again stops recording.
* **Play (Toggle):** Starts or stops playback of the entire loop.
* **Metronome (Toggle):** Turns the click track on or off.
* **BPM Up / Down:** Increases or decreases the project tempo. (Can also be mapped to an endless rotary knob).
* **Volume Roller/Slider:** Adjusts the volume of the **currently armed track**.

### The Joystick: Track Mode (Default)
When the application starts, your joystick is in **Track Mode**. It is used to navigate and manage your tracks.
* **Up / Down:** Moves the "Armed" status up or down your list of tracks.
* **Left:** Toggles **Mute / Unmute** on the currently armed track.
* **Right:** Switches the joystick into **Instrument Mode**.

#### Advanced Track Macros (Double-Taps)
When you reach the edges of your track list, the joystick unlocks special features:
* **Double-Tap UP (Top Edge):** If you are on Track 1 and push UP, the voice will prompt you to save. Push UP again to instantly **Save the Project** to your hard drive.
* **Double-Tap DOWN (Bottom Edge):** If you are on the last track and push DOWN, the voice will prompt you. Push DOWN again to instantly **Add a New Track** to the bottom of the list and arm it.

### The Joystick: Instrument Mode
By pushing **RIGHT** from Track Mode, you enter Instrument Mode. The joystick now controls the sound of your currently armed track.
* **Up / Down:** Cycles through the available `.sf2` SoundFonts in your library. The instrument changes instantly.
* **Left:** Exits Instrument Mode and returns you to **Track Mode**.

---

## 3. The Software Interface (UI)

If you are using the mouse and keyboard, or just monitoring the screen, the UI provides a complete overview of your session.

### The Top Control Bar
* **Transport Buttons:** Visual indicators for Record, Play, and Metronome. The Record button turns **Orange** during the Count-in, and **Red** when actively recording.
* **Status Label:** Displays the current engine state (e.g., `STOPPED`, `RECORDING`, `PLAYING`) and the current BPM.
* **Add Track Button:** A manual button to append a new track to the project.
* **MIDI Mapping:** Buttons to "Learn" new MIDI CC values from your controller, or reset them to factory defaults.

### The Track Rows
Each track in your project is represented by a row:
* **Arm Button (Radio):** Shows which track is currently receiving input. The background of the armed track highlights in dark grey with a blue border.
* **Track Name:** The display name of the track (e.g., "Master", "Track 2").
* **Mute Checkbox:** Shows the mute status of the track.
* **Instrument Dropdown:** A visual list of all available SoundFonts. You can use this dropdown with your mouse to change the instrument, or watch it update automatically as you use the Joystick in Instrument Mode.

---

## 4. Example Workflow: Recording your first loop

1. **Start the App:** The Voice Assistant will welcome you. "Master" track is automatically armed.
2. **Set the Tempo:** Use your MIDI mapped BPM buttons/knob to set your desired tempo.
3. **Turn on Metronome:** Press the Metronome button to hear the click.
4. **Record the Master Loop:** Press **Record**. The system will wait for the downbeat, give you a Count-In, and the Record button will turn Red. Play your chord progression.
5. **Stop Recording:** Press **Record** or **Play**. The engine will mathematically calculate your loop length, lock the Master Loop duration, and begin looping your chords seamlessly.
6. **Add a Track:** Push the joystick **DOWN** past the Master track twice. A new track is created and armed.
7. **Change Instrument:** Push the joystick **RIGHT** to enter Instrument Mode, then push **UP** to select a Bass or Drum soundfont. Push **LEFT** to return to Track Mode.
8. **Overdub:** Press **Record** to overdub your new bassline over the master chord progression.