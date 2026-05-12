# System Setup & Installation

Welcome to the Developer's Guide for Studio P4! This document will walk you through setting up the Python development environment from scratch. 

Because Studio P4 interacts directly with low-level audio drivers (FluidSynth) and hardware MIDI controllers, the setup requires a few system-level dependencies before installing the Python packages.

---

## 1. System Requirements

Before touching Python, ensure your machine meets these basic requirements:
* **Python:** Version 3.10 or higher.
* **Git:** To clone the repository.
* **MIDI Keyboard:** An AKAI MPK Mini Plus connected via USB (optional, but highly recommended for testing hardware routing).

---

## 2. Installing FluidSynth (Crucial Step)

Studio P4 uses `pyfluidsynth` to generate audio, which is just a Python wrapper around the C-based FluidSynth library. **You must have FluidSynth installed on your operating system for the app to run.**

### macOS
The easiest way to install FluidSynth on a Mac is using Homebrew:
```bash
brew install fluid-synth
```

### Linux (Debian/Ubuntu)
Use the advanced packaging tool:
```bash
sudo apt update
sudo apt install libfluidsynth-dev
```

### Windows
Windows is slightly more manual since it doesn't have a default package manager. 
1. Download the latest compiled FluidSynth Windows binaries from their official GitHub releases.
2. Extract the `.zip` file.
3. You have two options:
    * **Option A (System-wide):** Add the folder containing `fluidsynth.dll` to your Windows System `PATH` environment variable.
    * **Option B (Local):** Copy `libfluidsynth.dll` directly into the root folder of your `studio-p4` project.

---

## 3. Python Virtual Environment

Once FluidSynth is installed on your OS, you can set up the Python project. Open your terminal and run the following commands:

**1. Clone the repository:**
```bash
git clone [https://github.com/YOUR_USERNAME/studio-p4.git](https://github.com/YOUR_USERNAME/studio-p4.git)
cd studio-p4
```

**2. Create and activate a virtual environment:**
```bash
# On Windows:
python -m venv venv
venv\Scripts\activate

# On macOS/Linux:
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

---

## 4. Downloading Required Assets

Studio P4 requires a few static files to boot successfully. These are not included in the raw Git repository to save space.

### SoundFonts (`.sf2`)
Create a folder named `sf2` in the root of your project. You must have at least these two files inside it:
* `Metronom.sf2` (Used by the `MasterClockEngine` for the click track).
* `basic_piano.sf2` (Or any default instrument, so the app has something to load upon boot).

### Piper Voice Model (`.onnx`)
Download the French Text-to-Speech model. Place these two files directly in the root of your project:
* `fr_FR-siwis-medium.onnx`
* `fr_FR-siwis-medium.onnx.json`

---

## 5. Running the Studio

With your environment activated and your assets in place, plug in your MIDI keyboard and launch the application:

```bash
python main.py
```

**What to expect on a successful boot:**
1. The terminal will print the audio initialization sequence.
2. The PySide6 User Interface will appear.
3. You will hear the Text-to-Speech engine announce: *"Menu de démarrage. Nouveau projet."*
4. If your AKAI MPK Mini Plus is plugged in, it will automatically connect and be ready to receive joystick inputs!

---

## Troubleshooting

* **`OSError: cannot load library 'fluidsynth'`**: This means Python cannot find the FluidSynth C-library. Ensure you completed Step 2 correctly. On Windows, double-check that the `.dll` is either in your PATH or in the exact same folder as `main.py`.
* **No Voice Output**: Ensure the Piper `.onnx` and `.json` files are named exactly as expected and located in the root directory.
* **MIDI Keyboard Not Responding**: By default, `core/midi_io.py` searches for a port containing the string `"MPK mini"`. If you are using a different brand of keyboard, please read the [Remapping MIDI Controls](remap_midi.md) guide.