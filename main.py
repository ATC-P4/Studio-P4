import sys
from PySide6.QtWidgets import QApplication

# Import Backend
from core.models import Project
from core.engine import MasterClockEngine
from core.midi_io import MidiIO
from core.api import LooperAPI, MidiInputRouter

# Import Frontend (We will build this next)
from core.voice import VoicePresenter, VoiceService, VoiceType, VoiceService
from core.utils import EventBus, get_resource_path, get_available_instruments
from ui.main_window import MainWindow

# Import the voice model and config from your TTS implementation
from piper import PiperVoice

def main():
    # 1. Initialize the OS GUI Application
    app = QApplication(sys.argv)

    # 2. Instantiate the Backend (Model & Engine)
    print("Initializing Core...")
    project = Project("My Live Session", bpm=120)
    project.add_track("Master") # Add a default track so the UI isn't empty
    
    engine = MasterClockEngine(project)

    # 3. Instantiate the View (UI)
    # We create the window BEFORE the API, so we can pass its update function as the callback
    print("Initializing UI...")
    window = MainWindow()

    event_bus = EventBus() # Create a shared event bus for voice announcements

    available_instruments = get_available_instruments()
    # 4. Instantiate the Hardware Listener
    # We use a lambda to inject the api and window references into the handler later
    midi_io = MidiIO(
        project=project, 
        engine=engine
    )

    voice_path = get_resource_path("fr_FR-siwis-medium.onnx")
    voice_service = VoiceService(PiperVoice.load(voice_path))
    voice_presenter = VoicePresenter(voice_service, event_bus)
  

    # 5. Instantiate the Facade API
    # We pass the window's `update_from_dto` method as the lifeline.
    api = LooperAPI(
        engine=engine, 
        project=project, 
        available_instruments=available_instruments,
        ui_callback=lambda: window.backend_state_changed.emit(api.get_state_dto()),
        event_bus=event_bus,
    )

    # wire the midi commands to the api
    midi_io.on_command_cb = MidiInputRouter(api).handle_midi_action 


    # 6. Wire the UI Signals OUT to the API (The "Qt" way)
    # When the user clicks a button on the screen, it triggers an API method
    window.record_requested.connect(api.toggle_record)
    window.play_requested.connect(api.toggle_playback)
    window.metronome_toggled.connect(api.toggle_metronome)
    window.track_muted.connect(api.mute_track)
    window.track_armed.connect(api.arm_track)
    window.instrument_changed.connect(api.set_track_soundfont)
    window.add_track_requested.connect(lambda: api.add_track(f"Track {len(project.tracks)+1}"))

    # 7. Start the Hardware & Show the Window
    #midi_io.start('MPK mini Plus 0')
    midi_io.start('LoopBe Internal MIDI 0') # auto-detect the controller
    window.show()

    # 8. Force the first UI update to draw the initial state
    window.update_ui(api.get_state_dto())

    # 9. Graceful Shutdown Protocol
    app.aboutToQuit.connect(midi_io.stop)
    app.aboutToQuit.connect(lambda: engine.set_state("STOPPED"))

    # 10. Handover control to the Qt Event Loop (Blocks here until window is closed)
    print("Application Ready.")

    # Trigger a welcome message on launch
    voice_service.speak(VoiceType.WELCOME, "Bienvenue dans le studio P4. Prêt à faire de la musique ?")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()