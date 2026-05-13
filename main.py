import os, sys, subprocess, platform

def find_and_register_fluidsynth():
    
    system = platform.system()
    print("Searching for fluidsynth library")

    if getattr(sys, 'frozen', False):
        print("PyInstaller build")
        # Running as PyInstaller bundle — DLL/dylib/so is extracted to _MEIPASS
        dll_dir = sys._MEIPASS
        if system == "Windows":
            os.environ["PATH"] += ";" + dll_dir
        else:  # macOS and Linux both use colon-separated PATH
            os.environ["PATH"] += ":" + dll_dir

    else:

        print("Terminal launch from python script")

        if system == "Windows":
            # PowerShell equivalent of your Get-ChildItem command
            result = subprocess.run(
                [
                    "powershell", "-Command",
                    "Get-ChildItem -Path 'C:\\' -Recurse -Filter 'libfluidsynth*.dll'"
                    " -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName"
                ],
                capture_output=True, text=True
            )
            paths = result.stdout.strip().splitlines()
            if not paths:
                raise FileNotFoundError("FluidSynth DLL not found. Is it installed?")
            # Take the first result and get its containing folder
            dll_dir = os.path.dirname(paths[0])
            print(f"(Windows) path: {dll_dir}")
            os.environ["PATH"] += ";" + dll_dir

        elif system == "Darwin":  # macOS
            # Homebrew puts it here on both Intel and Apple Silicon
            for brew_path in ["/usr/local/lib", "/opt/homebrew/lib"]:
                if os.path.exists(os.path.join(brew_path, "libfluidsynth.dylib")):
                    os.environ["PATH"] += ":" + brew_path
                    print(f"(MacOS) path: {brew_path}")
                    break
            else:
                raise FileNotFoundError("FluidSynth not found. Try: brew install fluid-synth")

        elif system == "Linux":
            # ldconfig knows where all shared libraries are
            result = subprocess.run(
                ["ldconfig", "-p"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if "libfluidsynth" in line and "=>" in line:
                    lib_path = line.split("=>")[-1].strip()
                    os.environ["PATH"] += ":" + os.path.dirname(lib_path)
                    print(f"(Linux) path: {lib_path}")
                    break
            else:
                raise FileNotFoundError("FluidSynth not found. Try: sudo apt install libfluidsynth-dev")
find_and_register_fluidsynth()

import faulthandler
faulthandler.enable() # Catches C++ Segfaults!

from PySide6.QtWidgets import QApplication
from piper import PiperVoice
import mido


# Core & Models
from core.models import Project
from core.engine import MasterClockEngine
from core.api import LooperAPI
from core.midi_io import MidiIO, MidiInputRouter

# Infrastructure & Utilities
from core.voice import VoicePresenter, VoiceService, VoiceType
from core.utils import EventBus, get_resource_path, get_available_instruments, get_default_instrument
from core.project_io import ProjectIO
from core.startup_menu import StartupMenu 

# UI View
from ui.main_window import MainWindow
import time


def main() -> None:
    # ==========================================
    # PHASE 1: Application Foundation & Voice
    # ==========================================
    app = QApplication(sys.argv)
    print("Initializing Application...")
    event_bus = EventBus()
    
    # We MUST boot Voice first so the Startup Menu can speak
    voice_path = get_resource_path("fr_FR-siwis-medium.onnx")
    voice_service = VoiceService(PiperVoice.load(voice_path))
    voice_presenter = VoicePresenter(voice_service, event_bus)

    # ==========================================
    # PHASE 2: Headless Hardware Startup Menu
    # ==========================================
    # We use the same port the main app uses. 
    #midi_port_name = 'LoopBe Internal MIDI 0' # Change to 'MPK mini Plus 0' for hardware
    # find a port name that contains "MPK mini" (case-insensitive) but doesn't contain MIDIIN
    found_port = None
    for port in mido.get_input_names():
        if "MPK mini" in port and "MIDIIN" not in port:
            found_port = port
            print(f"[STARTUP] Found MIDI port for startup menu: {found_port}")
            break
    else:
        for port in mido.get_input_names():
            # search for loopbe port as a fallback
            if "LoopBe" in port or "IAC" in port:
                found_port = port
                print(f"[STARTUP] Found LoopBe MIDI port for startup menu: {found_port}")
                break
    
    midi_port_name = found_port if found_port else "MPK mini Plus 0"
    startup_menu = StartupMenu(voice_service)
    
    # This completely blocks Python until NAV_RIGHT is pressed
    selected_folder_path = startup_menu.run(port_name=midi_port_name)

    time.sleep(1.5)
    # ==========================================
    # PHASE 3: Instantiate Core Business Logic
    # ==========================================

    available_instruments = get_available_instruments()    
    while not available_instruments :
        voice_service.speak(VoiceType.WELCOME, "Pas d'instrument détecté. Veuiller placer des fichier soundfont dans le dossier S F 2. Appuyez sur entrée pour scanner à nouveau")
        input()
        available_instruments = get_available_instruments()



    project = Project("My Live Session", bpm=120, default_instrument = get_default_instrument(available_instruments))
    
    if selected_folder_path is None:
        print("Creating new project...")
        project.add_track("Master") 
    else:
        print(f"Loading project from {selected_folder_path}...")
        try:
            ProjectIO.load_into_project(project, selected_folder_path)
        except Exception as e:
            print(f"CRITICAL: Failed to load project. {e}")
            sys.exit(1)

    engine = MasterClockEngine(project)
    




    # ==========================================
    # PHASE 4: Instantiate Views & Controllers
    # ==========================================
    window = MainWindow()

    api = LooperAPI(
        engine=engine, 
        project=project, 
        available_instruments=available_instruments,
        ui_callback=lambda: window.backend_state_changed.emit(api.get_state_dto()),
        event_bus=event_bus,
    )

    # ==========================================
    # PHASE 5: Hardware & Input Routing
    # ==========================================
    midi_io = MidiIO(project=project, engine=engine)
    midi_router = MidiInputRouter(api)
    midi_io.on_command_cb = midi_router.handle_midi_action 
    midi_io.start_auto_connection() # Keyboard connection
    # ==========================================
    # PHASE 6: Wire the UI Signals
    # ==========================================
    window.record_requested.connect(api.toggle_record)
    window.play_requested.connect(api.toggle_playback)
    window.save_requested.connect(api.saveproject_to_disk)
    window.metronome_toggled.connect(api.toggle_metronome)
    window.track_muted.connect(api.mute_track)
    window.track_armed.connect(api.arm_track)
    window.instrument_changed.connect(api.set_track_soundfont)
    window.add_track_requested.connect(lambda: api.add_track(f"Track {len(project.tracks)+1}"))

    # ==========================================
    # PHASE 7: Graceful Shutdown
    # ==========================================
    app.aboutToQuit.connect(midi_io.stop)
    app.aboutToQuit.connect(lambda: engine.set_state("STOPPED"))
    app.aboutToQuit.connect(voice_service.shutdown) 

    # ==========================================
    # PHASE 8: Launch Main App
    # ==========================================
    window.show()
    window.update_ui(api.get_state_dto())

    print("Application Ready.")
    voice_service.speak(VoiceType.WELCOME, "Bienvenue dans le studio.")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()