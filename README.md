# Python Live Looper (Studio P4)

A hardware-first, multi-track MIDI looper designed for live performance. 

Built with Python, PySide6, and Fluidsynth, this application allows musicians to record, loop, and overdub MIDI tracks using a connected MIDI controller. It features a completely decoupled architecture, sample-accurate audio thread scheduling, and an interactive Text-to-Speech (TTS) assistant for headless, screen-free operation.

## 🌟 Key Features

* **Master Track Synchronization:** The first recorded track dictates the master loop length. All subsequent tracks automatically loop and sync to this duration.
* **Hardware-First Control:** Designed to be operated entirely via a MIDI controller (keys, pads, and joysticks). No mouse or keyboard required during performance.
* **Voice Assistant:** An integrated Text-to-Speech engine announces system states, armed tracks, and boundaries in French, allowing for eyes-free navigation.
* **SoundFont (.sf2) Support:** Dynamically load and swap instruments on the fly for each track.
* **Enterprise Architecture:** Built on a strict Model-View-Controller (MVC) pattern, utilizing an EventBus to completely decouple the UI and Voice systems from the core audio engine.

---

## 🏗️ Architecture Overview

The system is split into distinct, isolated layers:
* **Core Models & Engine:** The mathematical heart of the looper. Runs on isolated daemon threads utilizing a priority queue for sample-accurate MIDI playback.
* **API & Controllers:** The business logic facade (`LooperAPI`) and hardware state machine (`MidiInputRouter`).
* **UI View:** A "dumb" PySide6 frontend that reacts to backend state changes via Data Transfer Objects (DTOs).
* **Infrastructure:** PyAudio and Piper TTS handle the voice generation, triggered asynchronously via an internal EventBus.

For a deep dive into the data flow and architectural patterns, please consult the Developer Documentation (instructions below).

---

## 🚀 Getting Started

### Prerequisites
You will need Python 3.10+ and the following core libraries:
```bash
python3.10 -m venv venv
venv/Script/activate
pip install -r requirements.txt
```

and for mkdocs
```bash
venv/Script/activate
pip install -r requirements_mkdir.txt
mkdocs serve
```

## Documentation
docs in a website version can be found in site/index.html

## EXE file generation
After creating avenv as shown before run the following line inside the folder where the main.py file and the venv folder are located:
```bash
./venv/Scripts/python -m PyInstaller --clean --onefile `           
>>      --hidden-import mido.backends.rtmidi ` 
>>      --collect-all PySide6 `                
>>      --collect-all piper `
>>      --collect-all piper_phonemize `
>>      --add-data "sf2;sf2" `
>>      --add-data "fr_FR-siwis-medium.onnx;." `
>>      --add-data "fr_FR-siwis-medium.onnx.json;." `
>>      main.py
```

## TODOS
 add the possibility to remove tracks
- Think about a function to learn the controls binding (at the moment we have so many commands that is better to hard code them)
- better understand how fluidsynth and the sf2 work (multiple instruments in one sf2 file and potentially effects with sf2 encoding (metadata))
- group toghether similar sf2 and add one more navigation mode (aka groups), and then enable the option to enter a group (ex. guitars) and loop over the guitars sf2 files
- BPM logic is not connected neither to the playback nor to the save_event_midi, so if we change bpm the recorded notes don't change bpm.
- handle edge case and add the necessary try-catch, error messages, ...
- map get_info to a button (combination of bottons) and make the function more useful.
- Add support to connect the keyboard also once the app is already running
- Create a audio version of the user manual
- ask to our challenger if he needs a delete track button
- change the naming of the saved projects (if a project is reopend and saved again it should add like a version 2.0)
- test the compatibility with jaws, in case detach the listening function of our voiceover and send the messages through jaws.
- create a video for the presentation of 28 mai
- Check the documentation


sound font to download:
- [Free Soundfont Downloads - Music Production - Zanderjaz](https://www.zanderjaz.com/downloads/soundfonts/)
- [All soundfonts | Download free soundfonts](https://www.polyphone.io/en/soundfonts)
