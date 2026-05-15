# Studio P4: Accessible Python Looper for visually impaired musicians

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-Open%20Source-green.svg)

**Studio P4** is an open-source, hardware-first, multi-track MIDI looper designed for pre-studio track creation and built specifically for visually impaired musicians. This project was developed as part of the **EPFL Assistive Technology Challenge**.

Traditional DAWs are often overly complex and heavily reliant on mouse-driven graphical interfaces. Studio P4 solves this by offering a completely "headless," hardware-first workflow. It is designed to be controlled entirely from a MIDI keyboard, guided by an integrated Text-to-Speech (TTS) voice assistant.

## Key Features

* **Master Track Synchronization:** The first recorded track dictates the master loop length. All subsequent tracks automatically loop and sync to this duration.
* **Hardware-First Control:** Designed to be operated entirely via a MIDI controller (keys, pads, and joysticks). No mouse or keyboard required during performance.
* **Voice Assistant:** An integrated Text-to-Speech engine (Piper) announces system states, armed tracks, and boundaries in French, allowing for eyes-free navigation.
* **SoundFont (.sf2) Support:** Dynamically load and swap instruments on the fly for each track.
* **Enterprise Architecture:** Built on a strict Model-View-Controller (MVC) pattern, utilizing an EventBus to completely decouple the UI and Voice systems from the core audio engine.

---

## Architecture Overview

The system is split into distinct, isolated layers:
* **Core Models & Engine:** The mathematical heart of the looper. Runs on isolated daemon threads utilizing a priority queue for sample-accurate MIDI playback.
* **API & Controllers:** The business logic facade (`LooperAPI`) and hardware state machine (`MidiInputRouter`).
* **UI View:** A "dumb" PySide6 frontend that reacts to backend state changes via Data Transfer Objects (DTOs).
* **Infrastructure:** PyAudio and Piper TTS handle the voice generation, triggered asynchronously via an internal EventBus.

---

## Repository Structure 📂

```text
studio-p4/
├── core/                        # Backend business logic, audio engine, and models
│   ├── api.py                   # Looper API facade
│   ├── engine.py                # Master clock and audio thread dispatcher
│   ├── midi_io.py               # Hardware MIDI abstraction layer
│   ├── models.py                # Data structures (Project, Track)
│   ├── project_io.py            # Logic for saving/loading project files
│   ├── startup_menu.py          # Headless MIDI-controlled startup interface
│   ├── utils.py                 # Helper functions, Pathing, and EventBus
│   └── voice.py                 # Piper TTS integration and VoicePresenter
├── docs/                        # MkDocs markdown documentation files
├── sf2/                         # SoundFont assets (e.g., basic_piano.sf2)
├── site/                        # Generated static HTML documentation (after build)
├── tests/                       # Project test suite
├── ui/                          # PySide6 graphical user interface
│   ├── main_window.py           # Main application window
│   ├── startup_dialog.py        # Mouse-driven startup interface
│   ├── track_widget.py          # Individual track UI component
│   └── voice_settings.py        # Voice settings dialogue
├── .gitignore                   # Git ignore rules
├── Music Helper.spec            # PyInstaller build specification file
├── README.md                    # Project description and instructions
├── fr_FR-siwis-medium.onnx      # Piper TTS voice model
├── fr_FR-siwis-medium.onnx.json # Piper TTS voice model configuration
├── main.py                      # Main application entry point
├── mkdocs.yml                   # MkDocs configuration file
├── README.md                    # That would be the current file :)
├── requirements.txt             # Core Python dependencies
├── requirements_loose.txt       # Unpinned Python dependencies
├── requirements_mkdocs.txt      # Dependencies for building the documentation
└── virtual_akai.py              # Virtual MIDI controller testing script
```

---

## Getting Started

### 1. System Prerequisites
Before installing the Python packages, your operating system must have **FluidSynth** installed:
* **macOS:** `brew install fluid-synth`
* **Linux:** `sudo apt install libfluidsynth-dev`
* **Windows:** Ensure the FluidSynth DLLs are downloaded and available on your system path (or bundled using the PyInstaller method below).

### 2. Python Installation
Clone the repository and set up your virtual environment (Python 3.10+ required):

```bash
git clone [https://github.com/YOUR_USERNAME/studio-p4.git](https://github.com/YOUR_USERNAME/studio-p4.git)
cd studio-p4
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Studio
Ensure your `.sf2` files (like `basic_piano.sf2` and `Metronom.sf2`) are placed in the `sf2/` directory, and the voice model (`fr_FR-siwis-medium.onnx` and its `.json`) are in the root directory. Then launch the app:

```bash
python main.py
```
### 4. Hardware Requirements

This application is officially mapped and tested for the **AKAI MPK Mini Plus**. 

While other MIDI controllers can be used, the automatic port connection and default MIDI CC mappings (e.g., joystick navigation on CC 2, 3, 12, 13 and transport controls on CC 117-119) are hardcoded for the MPK Mini Plus. If you are using a different controller, you will need to manually adjust the `DEFAULT_MIDI_MAPPING` in `core/midi_io.py` to match your hardware's output.

*Note: Don't have a physical controller? You can use the included `virtual_akai.py` script to simulate the exact hardware inputs on your screen!*

---

## EXE File Generation (Windows)

If you want to build a standalone executable file so users don't need to install Python, you can use PyInstaller. 

After creating and activating your virtual environment as shown above, run the following command in the root folder (formatted for PowerShell):

```powershell
./venv/Scripts/python -m PyInstaller --clean --onefile `
    --hidden-import mido.backends.rtmidi `
    --collect-all PySide6 `
    --collect-all piper `
    --collect-all piper_phonemize `
    --add-data "sf2;sf2" `
    --add-data "fr_FR-siwis-medium.onnx;." `
    --add-data "fr_FR-siwis-medium.onnx.json;." `
    main.py
```
*Note: This will generate a standalone `.exe` inside a newly created `dist/` folder.*

---

## Documentation 📚

The complete documentation—including detailed user guides, architectural breakdowns, and developer API references—can be found here:

👉 **[Project documentation](https://danthepol.github.io/Music-Helper-2026/)**

*(For developers: You can also build and view the documentation locally by running `pip install -r requirements_mkdocs.txt` followed by `mkdocs serve`, then navigating to `http://127.0.0.1:8000`).*

---

## SoundFont Resources 🎹

Looking for more instruments to add to your `sf2/` folder? Here are some great free resources to download SoundFonts:
- [Zanderjaz Free Soundfont Downloads](https://www.zanderjaz.com/downloads/soundfonts/)
- [Polyphone Soundfont Repository](https://www.polyphone.io/en/soundfonts)

---

## Contributors 👥

This project was built for the EPFL Assistive Technology Challenge by:
* **[Filippo Tognina](https://github.com/FTognina)**
* **[Daniel Polka](https://github.com/DanThePol)**
* **[Romain Frossard](https://github.com/frossardr)**
* **[Eloi Bressaud](https://github.com/eloibressaud)**


## License 📄
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
This software uses PySide6 and FluidSynth, which are licensed under the LGPL.