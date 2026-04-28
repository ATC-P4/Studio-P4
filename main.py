import sys
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
from core.utils import EventBus, get_resource_path, get_available_instruments
from core.project_io import ProjectIO
from core.startup_menu import StartupMenu  # <-- NEW IMPORT

# UI View
from ui.main_window import MainWindow


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
            # search for loopbe port as a fallback
            if "LoopBe" in port:
                found_port = port
                print(f"[STARTUP] Found LoopBe MIDI port for startup menu: {found_port}")
                break
    
    midi_port_name = found_port if found_port else "MPK mini Plus 0"
    startup_menu = StartupMenu(voice_service)
    
    # This completely blocks Python until NAV_RIGHT is pressed
    selected_folder_path = startup_menu.run(port_name=midi_port_name)

    # ==========================================
    # PHASE 3: Instantiate Core Business Logic
    # ==========================================
    project = Project("My Live Session", bpm=120)
    
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
    available_instruments = get_available_instruments()

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

    # ==========================================
    # PHASE 6: Wire the UI Signals
    # ==========================================
    window.record_requested.connect(api.toggle_record)
    window.play_requested.connect(api.toggle_playback)
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
    midi_io.start(midi_port_name) 
    window.show()
    window.update_ui(api.get_state_dto())

    print("Application Ready.")
    voice_service.speak(VoiceType.WELCOME, "Bienvenue dans le studio.")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()