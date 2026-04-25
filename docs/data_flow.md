Here is the complete MkDocs-ready Markdown file for your data flow documentation. Save this exactly as `docs/data_flow.md`.

This document maps the exact lifecycle of data as it moves through your dual-thread, event-driven MVC architecture. 

```markdown
# Application Data Flow

This document maps the lifecycle of data as it enters, mutates, and exits the Python Live Looper. Understanding these pipelines is critical for maintaining thread safety and adhering to the Single Responsibility Principle.

---

## 1. The Control Flow (Hardware to State)
This pipeline handles how a physical button press alters the internal memory of the application.

1. **Hardware Emission:** A physical MIDI controller sends a raw byte (e.g., `CC 119`).
2. **Listener (`MidiIO`):** The `mido` background thread receives the byte.
3. **Translation:** `MidiIO` checks `Project.midi_mapping` and translates `CC 119` into the string `"TOGGLE_RECORD"`.
4. **Routing (`MidiInputRouter`):** The string is passed to the router. The router looks up `"TOGGLE_RECORD"` in its `_action_map` and invokes `LooperAPI.toggle_record()`.
5. **Business Logic (`LooperAPI`):** The API executes the command, changing `MasterClockEngine.current_state` to `"COUNT_IN"`.
6. **UI Update:** The API triggers `self._ui_callback()`, passing a `get_state_dto()` dictionary to the View (`MainWindow`), which redraws the screen.

```text
[MIDI Hardware] -> (Raw Bytes) -> [MidiIO] -> (Command String) -> [MidiInputRouter] -> (Method Call) -> [LooperAPI] -> (State Change) -> [Models/Engine]
                                                                                                              |
                                                                                                              +-> (DTO) -> [UI MainWindow]
```

---

## 2. The Audio Flow (Time to Sound)
This pipeline handles how recorded MIDI events are scheduled and played back accurately.

1. **The Clock (`MasterClockEngine`):** A daemon thread (`_clock_loop`) continuously calculates the `target_time` (now + 50ms lookahead).
2. **Modulo Arithmetic:** The engine iterates through `Track.midi_events`. It applies modulo math using the `Project.master_loop_beats` to determine when historical notes should play in the *current* loop cycle.
3. **The Priority Queue:** If a note falls within the lookahead window, it is pushed into the `audio_queue` (a thread-safe `heapq`), sorted by its exact future execution timestamp.
4. **The Dispatcher:** A second daemon thread (`_dispatcher_loop`) polls the queue. When the hardware clock matches a note's timestamp, it pops the note.
5. **Synthesis (`Fluidsynth`):** The dispatcher triggers `track.play_note_on()`, sending the instruction to the C-level Fluidsynth driver for immediate audio output.

```text
[Track.midi_events] -> (Modulo Math) -> [Clock Thread] -> (Timestamped Tuples) -> [Priority Queue] -> [Dispatcher Thread] -> [Fluidsynth] -> [Speakers]
```

---

## 3. The Event Flow (Decoupled Feedback)
This pipeline handles how the core backend triggers auxiliary features (like Voice TTS) without blocking audio or business logic.

1. **Action:** The user arms a track. `LooperAPI.arm_track()` executes.
2. **Emission:** The API broadcasts an event: `events.emit("GENERIC_ANNOUNCEMENT", message="Bass armé")`.
3. **The Bus (`EventBus`):** The bus loops through all subscribed listeners.
4. **The Presenter (`VoicePresenter`):** The presenter catches the event and routes it to the `VoiceService`.
5. **Synthesis (`VoiceService`):** The TTS engine (`PiperVoice`) generates an audio waveform on a temporary thread and pushes it to a `BlockingMap` queue.
6. **Playback:** The persistent `_voice_worker` thread pops the waveform and writes it to the `PyAudio` output stream.

```text
[LooperAPI] -> (String Payload) -> [EventBus] -> [VoicePresenter] -> [Piper TTS] -> (WAV Chunks) -> [Blocking Queue] -> [PyAudio Thread] -> [Speakers]
```

---

## 4. The Export Flow (Memory to Disk)
This pipeline handles how volatile RAM is permanently saved to the hard drive.

1. **Trigger:** The user double-taps "Up" on the joystick. `MidiInputRouter` triggers `LooperAPI.save_project_to_disk()`.
2. **Project Delegation:** The API calls `Project.save_project()`, which generates a timestamped directory (e.g., `Saves/project_20260425-112300/`).
3. **Extraction:** The `Project` iterates through its `Tracks` and passes them to the `MidiExporter`.
4. **Conversion (`MidiExporter`):** The exporter converts absolute Python timestamps (seconds) into relative MIDI delta-ticks based on the Project's BPM.
5. **Padding:** The exporter calculates the difference between the last played note and the end of the `master_loop`, appending an `end_of_track` MetaMessage to ensure perfect looping in a DAW.
6. **I/O:** The `mido.MidiFile.save()` method writes the `.mid` files to the hard drive.

```text
[LooperAPI] -> [Project] -> (Track Objects) -> [MidiExporter] -> (Delta-Tick Math & Padding) -> [mido.MidiFile] -> [Hard Drive]
```
```
