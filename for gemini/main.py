import sys
from PySide6.QtWidgets import QApplication

# Import Backend
from core.models import Project
from core.engine import MasterClockEngine
from core.audio_io import AudioIO
from core.api import LooperAPI

# Import Frontend (We will build this next)
from core.voice import VoiceService, VoiceType, VoiceService
from core.utils import get_resource_path
from ui.main_window import MainWindow

# Import the voice model and config from your TTS implementation
from piper import PiperVoice

def main():
    # 1. Initialize the OS GUI Application
    app = QApplication(sys.argv)

    # 2. Instantiate the Backend (Model & Engine)
    print("Initializing Core...")
    project = Project("My Live Session", bpm=120)
    project.add_track("Piano") # Add a default track so the UI isn't empty
    project.add_track("Bass")  # Add a second track to test switching
    project.add_track("Drums")  # Add a third track to test switching
    
    engine = MasterClockEngine(project)

    # 3. Instantiate the View (UI)
    # We create the window BEFORE the API, so we can pass its update function as the callback
    print("Initializing UI...")
    window = MainWindow()

    # 4. Instantiate the Hardware Listener
    # We use a lambda to inject the api and window references into the handler later
    audio_io = AudioIO(
        project=project, 
        engine=engine
    )

    #voice_path = "fr_FR-siwis-medium.onnx"
    voice_path = get_resource_path("fr_FR-siwis-medium.onnx")
    
    voice_service = VoiceService(PiperVoice.load(voice_path))
    # 5. Instantiate the Facade API
    # We pass the window's `update_from_dto` method as the lifeline.
    api = LooperAPI(
        engine=engine, 
        project=project, 
        audio_io=audio_io, 
        voice_service = voice_service,
        ui_callback=lambda: window.backend_state_changed.emit(api.get_state_dto())
    )

    # wire the midi commands to the api
    audio_io.on_command_cb = api.handle_midi_action


    # 6. Wire the UI Signals OUT to the API (The "Qt" way)
    # When the user clicks a button on the screen, it triggers an API method
    window.record_requested.connect(api.toggle_record)
    window.play_requested.connect(api.toggle_playback)
    window.metronome_toggled.connect(api.toggle_metronome)
    window.track_muted.connect(api.mute_track)
    window.track_armed.connect(api.arm_track)
    window.instrument_changed.connect(api.set_track_soundfont)
    window.add_track_requested.connect(lambda: api.add_track(f"Track {len(project.tracks)+1}"))

    # TODO: create a midi learn function
    # window.midi_learn_requested.connect()
    window.midi_reset_requested.connect(api.reset_midi_mapping)
    # 7. Start the Hardware & Show the Window
    audio_io.start('MPK mini Plus 0')
    window.show()

    # 8. Force the first UI update to draw the initial state
    window.update_ui(api.get_state_dto())

    # 9. Graceful Shutdown Protocol
    app.aboutToQuit.connect(audio_io.stop)
    app.aboutToQuit.connect(lambda: engine.set_state("STOPPED"))

    # 10. Handover control to the Qt Event Loop (Blocks here until window is closed)
    print("Application Ready.")

    # Trigger a welcome message on launch
    voice_service.speak(VoiceType.WELCOME, "Bienvenue dans le studio P4. Prêt à faire de la musique ?")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()