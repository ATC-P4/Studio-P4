import pyaudio as pa
import threading
from enum import Enum
from piper import SynthesisConfig
from core.utils import EventBus


class VoiceType(Enum):
    BPM_INFO = 1
    BPM_MOD = 2
    REC_STOP = 3
    WELCOME = 4
    METR_TOGGLE = 5
    TRACK_SAVE = 6
    METR_INFO = 7
    STOP = 0

# Your requested BlockingMap from Slack
class BlockingMap(object):
    def __init__(self):
        self.queue = {}
        self.cv = threading.Condition()

    def put(self, key, value):
        with self.cv:
            self.queue[key] = value
            self.cv.notify()

    def pop(self):
        with self.cv:
            while not self.queue:
                self.cv.wait()
            # popitem() returns the most recently inserted key-value pair (LIFO)
            return self.queue.popitem()

class VoiceService:
    def __init__(self, voice_engine, voice_config = SynthesisConfig(
        volume=0.5,
        length_scale=1.2,
        noise_scale=0.667,
        noise_w_scale=0.8,
            normalize_audio=True
        )):
        """
        voice_engine: Your text-to-speech synthesizer instance.
        voice_config: Configuration for the voice synthesizer.
        """
        self._voice = voice_engine
        self._voice_config = voice_config
        self._voice_queue = BlockingMap()
        self._is_running = True
        
        # Start the persistent audio worker
        threading.Thread(target=self._voice_worker, daemon=True).start()

    def _voice_worker(self):
        """Single persistent thread that owns the audio engine exclusively."""
        player = pa.PyAudio()
        
        # Fallback to 44100 if the engine config doesn't specify a rate
        sample_rate = getattr(self._voice.config, 'sample_rate', 44100) 

        stream = player.open(
            format=pa.paInt16,
            channels=1,
            rate=sample_rate,
            output=True
        )

        while self._is_running:
            # This uses your BlockingMap's pop function
            voicetype, audio = self._voice_queue.pop() 
            
            if voicetype == VoiceType.STOP:
                stream.stop_stream()
                stream.close()
                player.terminate()
                return

            if audio:
                for chunk in audio:
                    # Accommodates your specific chunk architecture
                    try:
                        stream.write(chunk.audio_int16_bytes)
                    except AttributeError:
                        stream.write(chunk) # Fallback for raw byte strings

    def speak(self, voice_type: VoiceType, text: str):
        """Synthesizes text in the background and queues it for voice."""
        def _add_sentence():
            snt = self._voice.synthesize(text)
            self._voice_queue.put(voice_type, snt)

        # We run the text-generation on a temp thread so the UI never freezes
        threading.Thread(target=_add_sentence, daemon=True).start()

    def shutdown(self):
        """Cleanly closes the audio stream."""
        self._is_running = False
        self._voice_queue.put(VoiceType.STOP, None)
    


class VoicePresenter:
    """Translates backend events into voice synthesizer commands."""
    
    def __init__(self, voice_service: VoiceService, event_bus: EventBus):
        self.voice = voice_service
        
        # 1. Wire up the event subscriptions
        event_bus.subscribe("TRACK_ARMED", self.announce_armed_track)
        event_bus.subscribe("PROJECT_SAVED", self.announce_saved)
        event_bus.subscribe("METRONOME_TOGGLED", self.announce_metronome)
        event_bus.subscribe("BPM_CHANGED", self.announce_bpm)
        event_bus.subscribe("RECORDING_STOPPED", self.announce_recording_stopped)
        event_bus.subscribe("TRACK_MUTED", self.announce_track_muted)
        event_bus.subscribe("STATUS_REQUESTED", self.announce_current_state)
        event_bus.subscribe("GENERIC_ANNOUNCEMENT", lambda message: self.voice.speak(VoiceType.METR_INFO, message))

    # 2. Define the exact text and voice types for each event
    def announce_armed_track(self, track_name: str) -> None:
        self.voice.speak(VoiceType.METR_INFO, f"{track_name} armé")

    def announce_saved(self) -> None:
        self.voice.speak(VoiceType.METR_INFO, "Projet sauvegardé")
        
    def announce_metronome(self, is_on: bool) -> None:
        msg = "Metronome On" if is_on else "Metronome Off"
        self.voice.speak(VoiceType.METR_TOGGLE, msg)

    def announce_bpm(self, bpm: int) -> None:
        self.voice.speak(VoiceType.BPM_MOD, f"B P M {bpm}")
        
    def announce_recording_stopped(self) -> None:
        self.voice.speak(VoiceType.REC_STOP, "Enregistrement arrêté.")

    def announce_track_muted(self, track_name: str, is_muted: bool) -> None:
        status = "muté" if is_muted else "démuté"
        self.voice.speak(VoiceType.METR_INFO, f"{track_name} {status}")
    
    def announce_current_state(self, metronome_status: str, bpm: int) -> None:
        """announce current BPM and metronome status on demand"""
        self.voice.speak(VoiceType.METR_INFO, f"Métronome actuellement {metronome_status}.")
        self.voice.speak(VoiceType.BPM_INFO, f"B P M actuel: {bpm}")