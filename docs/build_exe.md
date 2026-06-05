# Building a Standalone Executable (.exe)

To make Studio P4 truly accessible, you can bundle the Python application and the Piper Text-to-Speech models into a single `.exe` file. This allows users to run the studio without installing Python or using the command line.

We use **PyInstaller** to achieve this.

## 1. Prerequisites

Before building, ensure you are on a Windows machine and that your Python virtual environment is activated. 

```bash
# Activate your environment

# On Windows
venv\Scripts\activate
# On MacOS/Linux
source venv/bin/activate

# Ensure PyInstaller is installed
pip install pyinstaller
```

## 2. The Build Command

Because Studio P4 relies on heavily nested libraries (like PySide6 for the UI, and Piper for voice), we must explicitly tell PyInstaller to collect them, alongside our static voice model assets. 

*Note: We deliberately exclude the `sf2/` folder from this build command so that users can add their own instruments externally without recompiling the app.*

We show here the command that will build a Windows executable (must be run from a Windows machine). To create a MacOS or Linux executable, the process is the same and the command is almost the same (there are some syntax differences), but the app needs to have been built with PyInstaller on that specific OS. Before running the build command though, you will need to find the internal path to the `libfluidsynth` library:

 ```powershell
Get-ChildItem -Path "C:\" -Recurse -Filter "libfluidsynth*.dll" -ErrorAction SilentlyContinue | Select-Object FullName
 ```

 Run the following command from the root of your project directory (formatted for **PowerShell** on Windows), and replace `C:\your\path\to\libfluidsynth-3.dll` by the actual path to the libfluidsynth library:

```powershell
python -m PyInstaller --name "Studio P4" --onefile --hidden-import mido.backends.rtmidi --collect-all PySide6 --collect-all piper --collect-all piper_phonemize --collect-all rtmidi --add-data "sf2\metronome.sf2;sf2" --add-data "fr_FR-siwis-medium.onnx;."  --add-data "fr_FR-siwis-medium.onnx.json;." --add-binary "C:\your\path\to\libfluidsynth-3.dll;." main.py
```

*Note:*

### Command Breakdown:

* `--onefile`: Compresses everything into a single `main.exe`.
* `--hidden-import mido.backends.rtmidi`: Forces PyInstaller to include the C++ MIDI drivers, which Mido loads dynamically.
* `--collect-all`: Ensures that complex C-bindings for the UI and Voice synthesizer are not left behind.
* `--add-data`: Bundles the French voice model and the metronome directly into the executable's temporary runtime folder (bundling `metronome.sf2` is optional though). The ';.' and ';sf2' are not typos, the syntax of the `--add-data` argument is: `"external\path\to\file.format;build_internal\file\path\"`.

## 3. Output & Distribution

Depending on your computer's speed, this process will take a few minutes. 

Once completed, a new folder named **`dist/`** will be created in your project root. Inside, you will find your standalone `main.exe`.

### Preparing the Final Folder for Users
To distribute the app to a user, you must provide them with the `.exe` AND the external instrument folder. The application will create the `Saves` directory itself.

```text
Studio_P4_Release/
├── main.exe      (from your dist/ folder)
└── sf2/          (copy your sf2/ folder here)
```