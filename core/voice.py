import pyaudio as pa
import threading
from enum import Enum
from piper import SynthesisConfig
from core.utils import EventBus
import time
from typing import Any
from piper import PiperVoice, PiperConfig


class VoiceType(Enum):
    STOP = 0
    BPM_INFO = 1
    BPM_MOD = 2
    REC_STOP = 3
    WELCOME = 4
    METR_TOGGLE = 5
    PROJ_SAVE = 6
    METR_INFO = 7
    PROJ_INFO = 8
    GENERAL_INFO = 9
    TRACK_INFO = 10
    TRACK_NAME = 11


# Your requested BlockingMap from Slack
class BlockingMap(object):
    def __init__(self):
        self.queue = {}
        self.cv = threading.Condition()

    def put(self, key: Any, value: Any) -> None:
        with self.cv:
            self.queue[key] = value
            self.cv.notify()

    def pop(self) -> tuple[Any, Any]:
        with self.cv:
            while not self.queue:
                self.cv.wait()
            # popitem() returns the most recently inserted key-value pair (LIFO)
            return self.queue.popitem()

class VoiceService:

    _vol = 0.5
    _lenscale = 1.2
    _nsscale = 0.667
    _nswscale = 0.8
    _normaudio = True

    def __init__(self, voice_engine: PiperVoice):
        """
        voice_engine: Your text-to-speech synthesizer instance.
        voice_config: Configuration for the voice synthesizer.
        """
        self._voice = voice_engine
        self._voice_queue = BlockingMap()
        self._is_running = True
        
        # Start the persistent audio worker
        threading.Thread(target=self._voice_worker, daemon=True).start()

    def _voice_worker(self):
        """Single persistent thread that owns the audio engine exclusively."""
        sample_rate = getattr(self._voice.config, 'sample_rate', 44100) 

        while self._is_running:
            # This uses your BlockingMap's pop function
            voicetype, audio = self._voice_queue.pop() 
            
            if voicetype == VoiceType.STOP:
                return # clean up after ourselves

            if audio:
                player = None
                stream = None
                try:
                    player = pa.PyAudio()
                    stream = player.open(
                        format=pa.paInt16,
                        channels=1,
                        rate=sample_rate,
                        output=True
                    )
                    
                    for chunk in audio:
                        try:
                            stream.write(chunk.audio_int16_bytes)
                        except AttributeError:
                            stream.write(chunk) 
                            
                except Exception as e:
                    # intercept the sudden disconnection
                    print(f"[Audio] Switching computer sound cards...")
                    time.sleep(0.5) # Give a moment to route the audio!
                    
                finally:
                    if stream:
                        try:
                            stream.stop_stream()
                        except: pass
                        try:
                            stream.close() # If it fails because the headset is no longer there, ignore it
                        except: pass
                        
                    if player:
                        try:
                            player.terminate() # If the termination fails, we ignore it
                        except: pass

    def speak(self, voice_type: VoiceType, text: str):
        """Synthesizes text in the background and queues it for voice."""
        def _add_sentence():
            snt = self._voice.synthesize(text)
            self._voice_queue.put(voice_type, snt)

        # We run the text-generation on a temp thread so the UI never freezes
        threading.Thread(target=_add_sentence, daemon=True).start()

    def shutdown(self):
        """Cleanly closes the audio stream."""
        self._voice_queue.put(VoiceType.STOP, None)
        self._is_running = False
    


class VoicePresenter:
    """Translates backend events into voice synthesizer commands."""
    
    def __init__(self, voice_path: str, event_bus: EventBus):

        voice_service = VoiceService(PiperVoice.load(voice_path))
        self.voice = voice_service
        
        # 1. Wire up the event subscriptions
        event_bus.subscribe("TRACK_ARMED", self.announce_armed_track)
        event_bus.subscribe("PROJECT_SAVED", self.announce_saved)
        event_bus.subscribe("METRONOME_TOGGLED", self.announce_metronome)
        event_bus.subscribe("BPM_CHANGED", self.announce_bpm)
        event_bus.subscribe("RECORDING_STOPPED", self.announce_recording_stopped)
        event_bus.subscribe("TRACK_MUTED", self.announce_track_muted)
        event_bus.subscribe("STATUS_REQUESTED", self.announce_current_state)
        event_bus.subscribe("GENERIC_ANNOUNCEMENT", lambda message: self.voice.speak(VoiceType.GENERAL_INFO, message))

    def shutdown(self) -> None:
        self.voice.shutdown()

    # 2. Define the exact text and voice types for each event
    def announce_armed_track(self, track_name: str) -> None:
        self.voice.speak(VoiceType.TRACK_NAME, f"{track_name} armé")

    def announce_saved(self) -> None:
        self.voice.speak(VoiceType.PROJ_SAVE, "Projet sauvegardé")
        
    def announce_metronome(self, is_on: bool) -> None:
        msg = "Métronome On" if is_on else "Métronome Off"
        self.voice.speak(VoiceType.METR_TOGGLE, msg)

    def announce_bpm(self, bpm: int) -> None:
        self.voice.speak(VoiceType.BPM_MOD, f"B P M {bpm}")
        
    def announce_recording_stopped(self) -> None:
        self.voice.speak(VoiceType.REC_STOP, "Enregistrement arrêté.")

    def announce_track_muted(self, track_name: str, is_muted: bool) -> None:
        status = "muté" if is_muted else "démuté"
        self.voice.speak(VoiceType.TRACK_INFO, f"{track_name} {status}")
    
    def announce_current_state(self, metronome_status: str, bpm: int) -> None:
        """announce current BPM and metronome status on demand"""
        self.voice.speak(VoiceType.METR_INFO, f"Métronome actuellement {metronome_status}.")
        self.voice.speak(VoiceType.BPM_INFO, f"B P M actuel: {bpm}")

    def announce_loading_proj(self, name: str) -> None:
        self.voice.speak(VoiceType.PROJ_INFO, f"Chargement du projet {name}.")

    def announceb_new_proj(self) -> None:
        self.voice.speak(VoiceType.PROJ_INFO, "Nouveau Projet")

    def announce_selected_proj(self, name: str) -> None:
        self.voice.speak(VoiceType.PROJ_INFO, name)

    def announce_started(self) -> None:
        self.voice.speak(VoiceType.WELCOME, "Menu de démarrage. Nouveau projet.")

    def welcome(self) -> None:
        self.voice.speak(VoiceType.WELCOME, "Bienvenue dans le studio.")