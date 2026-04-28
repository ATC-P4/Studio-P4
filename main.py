import sys
from PySide6.QtWidgets import QApplication
from piper import PiperVoice

# Core & Models
from core.models import Project
from core.engine import MasterClockEngine
from core.api import LooperAPI
from core.midi_io import MidiIO, MidiInputRouter

# Infrastructure & Utilities
from core.voice import VoicePresenter, VoiceService, VoiceType
from core.utils import EventBus, get_resource_path, get_available_instruments

# UI View
from ui.main_window import MainWindow


def main() -> None:
    # ==========================================
    # PHASE 1: Initialize Application Foundation
    # ==========================================
    app = QApplication(sys.argv)
    print("Initializing Application...")
    event_bus = EventBus()
    
    # ==========================================
    # PHASE 2: Start Audio & Voice Infrastructure
    # ==========================================
    voice_path = get_resource_path("fr_FR-siwis-medium.onnx")
    voice_service = VoiceService(PiperVoice.load(voice_path))
    voice_presenter = VoicePresenter(voice_service, event_bus)
    
    available_instruments = get_available_instruments()

    # ==========================================
    # PHASE 3: Instantiate Core Business Logic
    # ==========================================
    project = Project("My Live Session", bpm=120)
    project.add_track("Master") 
    
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
    
    # Depending on your final api.py, use handle_midi_action or route_command
    midi_io.on_command_cb = midi_router.handle_midi_action 

    # ==========================================
    # PHASE 6: Wire the UI Signals to the Backend
    # ==========================================
    window.record_requested.connect(api.toggle_record)
    window.play_requested.connect(api.toggle_playback)
    window.metronome_toggled.connect(api.toggle_metronome)
    window.track_muted.connect(api.mute_track)
    window.track_armed.connect(api.arm_track)
    window.instrument_changed.connect(api.set_track_soundfont)
    window.add_track_requested.connect(lambda: api.add_track(f"Track {len(project.tracks)+1}"))

    # ==========================================
    # PHASE 7: Shutdown Protocol
    # ==========================================
    app.aboutToQuit.connect(midi_io.stop)
    app.aboutToQuit.connect(lambda: engine.set_state("STOPPED"))
    app.aboutToQuit.connect(voice_service.shutdown) # CRITICAL FIX: Close PyAudio

    # ==========================================
    # PHASE 8: Launch
    # ==========================================
    midi_io.start("MPK mini Plus 0")  # Start MIDI I/O before showing the UI to ensure responsiveness
    #midi_io.start('LoopBe Internal MIDI 0') 
    window.show()
    window.update_ui(api.get_state_dto())

    print("Application Ready.")
    voice_service.speak(VoiceType.WELCOME, "Bienvenue dans le studio P4. Prêt à faire de la musique ?")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()